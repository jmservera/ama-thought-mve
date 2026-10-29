"""Focused tests for the opaque state and exact-ownership boundary."""
import base64
import io
import json
import shutil
import struct
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import isolation
import isolation_helper as helper


@pytest.fixture
def tmp_path():
    """Keep these test workspaces inside the project, not system temp."""
    root = Path(__file__).resolve().parents[2] / ".study/isolation-test-workspaces"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir(mode=0o700)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def test_framing_rejects_truncation_trailing_corruption_and_oversize():
    valid = helper.frame({"op": "execute"}, b"opaque")
    assert helper.unframe(io.BytesIO(valid))[1] == b"opaque"
    for bad in (valid[:-1], valid + b"x", valid[:-1] + b"x",
                helper.MAGIC + struct.pack(">I", helper.HEADER_LIMIT + 1)):
        with pytest.raises((ValueError, EOFError)):
            helper.unframe(io.BytesIO(bad))


def test_regular_exports_reject_unsafe_paths_modes_duplicates_and_size():
    def entry(path="ok", mode=0o644, content=b"ok"):
        return {"path": path, "mode": mode, "content": base64.b64encode(content).decode()}
    for files in (
        [entry("../escape")], [entry("/escape")], [entry("a//b")], [entry(".git/config")],
        [entry("nested/.git/config")],
        [entry(mode=0o4755)], [entry(mode=420.0)], [entry(), entry()], [entry("a"), entry("a/b")],
        [entry(content=b"x" * (helper.FILE_LIMIT + 1))],
    ):
        with pytest.raises(helper.ProtocolError):
            helper.regular_files(files)


def test_state_roundtrip_preserves_git_and_executable_uncommitted_files(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / ".git").mkdir()
    (source / "empty").mkdir()
    (source / ".git/config").write_bytes(b"hostile but opaque")
    (source / "tcr").write_bytes(b"#!/bin/sh\nexit 0\n")
    (source / "tcr").chmod(0o755)
    state = helper.pack_tree(source)
    helper.restore_tree(state, target)
    assert (target / ".git/config").read_bytes() == b"hostile but opaque"
    assert (target / "empty").is_dir()
    assert (target / "tcr").stat().st_mode & 0o777 == 0o755
    with pytest.raises(helper.ProtocolError):
        helper.restore_tree(state + b"x", tmp_path / "other")


def test_state_rejects_symlink_hardlink_and_special_files(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "plain").write_bytes(b"ok")
    (root / "link").symlink_to("plain")
    with pytest.raises(helper.ProtocolError):
        helper.pack_tree(root)
    (root / "link").unlink()
    import os
    os.link(root / "plain", root / "link")
    with pytest.raises(helper.ProtocolError):
        helper.pack_tree(root)
    (root / "link").unlink()
    os.mkfifo(root / "fifo")
    with pytest.raises(helper.ProtocolError):
        helper.pack_tree(root)


def test_state_parser_rejects_duplicate_and_unsafe_records_before_writes(tmp_path):
    for entries in (
        [["../escape", 0o644, 0]],
        [["same", 0o644, 0], ["same", 0o644, 0]],
        [["suid", 0o4755, 0]],
        [["large", 0o644, helper.FILE_LIMIT + 1]],
    ):
        index = helper.canonical(entries)
        raw = helper.STATE_MAGIC + struct.pack(">I", len(index)) + index
        with pytest.raises(helper.ProtocolError):
            helper.restore_tree(raw, tmp_path)
    assert not list(tmp_path.iterdir())


def test_pending_launch_without_identity_blocks_replacement(tmp_path, monkeypatch):
    image = "sha256:" + "a" * 64
    broker = isolation.SandboxBroker(image, tmp_path)
    record = {
        "status": "intent", "name": "mve-isolated-unique", "image": image,
        "labels": {"mve.owner": broker.owner}, "cidfile": str(tmp_path / "container.cid"),
    }
    broker._record(record)
    monkeypatch.setattr(broker, "_inspect", lambda target: None)
    with pytest.raises(isolation.IsolationError, match="provable"):
        broker.recover()
    assert json.loads(broker.journal.read_bytes())["status"] == "ambiguous"
    with pytest.raises(isolation.IsolationError, match="blocks"):
        broker.recover()


def test_exact_owner_mismatch_never_removes_container(tmp_path, monkeypatch):
    image = "sha256:" + "a" * 64
    broker = isolation.SandboxBroker(image, tmp_path)
    record = {
        "status": "created", "name": "mve-isolated-unique", "image": image,
        "labels": {"mve.owner": broker.owner}, "cidfile": str(tmp_path / "container.cid"),
        "id": "b" * 64,
    }
    broker._record(record)
    monkeypatch.setattr(broker, "_inspect", lambda target: {
        "Id": record["id"], "Image": image, "Name": "/" + record["name"],
        "Config": {"Labels": {"mve.owner": "somebody-else"}},
    })
    monkeypatch.setattr(broker, "_docker", lambda *a, **k: pytest.fail("Must not remove mismatch"))
    with pytest.raises(isolation.IsolationError, match="ownership"):
        broker.recover()


def test_invalid_profile_and_stale_state_do_not_launch(tmp_path, monkeypatch):
    broker = isolation.SandboxBroker("sha256:" + "a" * 64, tmp_path)
    monkeypatch.setattr(broker, "_launch", lambda *a, **k: pytest.fail("Must not launch"))
    with pytest.raises(isolation.IsolationError):
        broker.execute("x", "true", timeoutSeconds=float("nan"))
    with pytest.raises(isolation.IsolationError):
        broker.evaluate(["/bin/true"], mounts={"/work": tmp_path, "/etc": tmp_path})
    isolation.atomic(broker.state_path, b"opaque")
    isolation.atomic(broker.metadata, helper.canonical({"token": "new", "sha256": "bad"}))
    with pytest.raises(isolation.IsolationError, match="Stale"):
        broker.execute("old", "true")
    with pytest.raises(isolation.IsolationError, match="integrity"):
        broker.execute("new", "true")


def test_interrupted_publication_keeps_previous_opaque_state(tmp_path, monkeypatch):
    broker = isolation.SandboxBroker("sha256:" + "a" * 64, tmp_path)
    token = broker._publish(b"old opaque", {"seed_head": "seed", "seed_manifest": {}})
    real_atomic = isolation.atomic

    def fail_metadata(path, content):
        if path == broker.metadata:
            raise OSError("interrupted metadata publication")
        real_atomic(path, content)

    monkeypatch.setattr(isolation, "atomic", fail_metadata)
    with pytest.raises(OSError):
        broker._publish(b"new opaque", {"seed_head": "seed", "seed_manifest": {}})
    assert broker._state(token)[1] == b"old opaque"
    assert sum(path.stat().st_size for path in tmp_path.glob("*.state")) == len(b"old opaque") + len(b"new opaque")


def test_trusted_evaluator_bound_and_parent_output_contract(tmp_path, monkeypatch):
    broker = isolation.SandboxBroker("sha256:" + "a" * 64, tmp_path)
    observed = {}

    def launch(request, *, mounts):
        observed.update(request=request, mounts=mounts)
        return {
            "stdout": "", "stderr": "", "exit_code": 0,
            "result": base64.b64encode(b'{"measurement":1}\n').decode(),
        }, b""

    monkeypatch.setattr(broker, "_launch", launch)
    result = broker.evaluate(
        ["/usr/local/bin/python3", "-I", "/kit/harness/evaluate.py"],
        mounts={tmp_path: "/work"}, timeout=600, env={"MVE_COMPLEXITY": "lizard"},
        output_file="/tmp/measurement.json",
    )
    assert result["output"] == '{"measurement":1}\n'
    assert observed["request"]["timeout"] == 600
    assert observed["mounts"] == {"/work": tmp_path}
    with pytest.raises(isolation.IsolationError, match="deadline"):
        broker.evaluate(["/usr/bin/make"], mounts={tmp_path: "/work"}, timeout=601)
    with pytest.raises(isolation.IsolationError):
        broker.execute("unused", "true", timeout=301)
    with pytest.raises(isolation.IsolationError, match="environment"):
        broker.evaluate(
            ["/usr/bin/make"], mounts={tmp_path: "/work"}, env={"GH_TOKEN": "must-not-inherit"},
        )
    with pytest.raises(isolation.IsolationError, match="FileNotFoundError"):
        broker.execute("missing-state", "true", timeout=1)


def test_supervisor_refuses_threaded_credential_transition(monkeypatch):
    monkeypatch.setattr(helper.os, "listdir", lambda path: ["main-thread", "foreign-thread"])
    monkeypatch.setattr(
        helper.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Threaded supervisor must not fork"),
    )
    with pytest.raises(helper.ProtocolError, match="single-threaded"):
        helper.run_child(["/bin/true"], 1)
