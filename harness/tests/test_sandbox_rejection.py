"""Focused tests for the execute-only authenticated candidate-state rejection.

Covers the narrow contract added around links/special-file candidate changes:
SandboxBroker._accept must authenticate and translate exactly one rejection
shape for the execute operation (SandboxBroker.StateRejected, caught only by
SandboxBroker.execute), while every forged/malformed variant, every rejection
claimed outside execute, and every success-shaped variant must still fail
closed as IsolationError. isolation_helper.supervisor's execute branch is the
only site permitted to catch CandidateArtifactRejected from pack_tree.
"""
import hashlib
import io
import shutil
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import isolation
import isolation_helper as helper

IMAGE = "sha256:" + "a" * 64
EXECUTE_REQUEST = {"op": "execute", "command": "ln -s x y", "timeout": 5}


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


def _identity(*, supervisor):
    uid = 0 if supervisor else helper.UID
    expected_caps = helper.SUPERVISOR_CAPS if supervisor else 0
    return {
        "uid": [uid, uid, uid], "gid": [uid, uid, uid], "dumpability": 0, "no_new_privileges": 1,
        "thread_count": 1,
        "capabilities": {"CapEff": expected_caps, "CapPrm": expected_caps, "CapInh": 0, "CapAmb": 0,
                         "CapBnd": helper.SUPERVISOR_CAPS},
    }


def _valid_rejection_header(**overrides):
    header = {
        "ok": False, "state_rejection": isolation.STATE_REJECTION_LINKS_OR_SPECIAL,
        "exit_code": 1, "stdout": "",
        "stderr": "Command changes were rejected; prior state is retained.",
        "child_setup": _identity(supervisor=False),
        "supervisor": {"before": _identity(supervisor=True), "after": _identity(supervisor=True)},
    }
    header.update(overrides)
    return header


def _success_header(**overrides):
    header = {
        "ok": True, "exit_code": 0, "stdout": "ok\n", "stderr": "",
        "child_setup": _identity(supervisor=False),
        "supervisor": {"before": _identity(supervisor=True), "after": _identity(supervisor=True)},
    }
    header.update(overrides)
    return header


def test_accept_raises_state_rejected_for_authenticated_execute_rejection(tmp_path):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    header = _valid_rejection_header()
    with pytest.raises(isolation.StateRejected) as excinfo:
        broker._accept(EXECUTE_REQUEST, header, b"")
    assert excinfo.value.code == isolation.STATE_REJECTION_LINKS_OR_SPECIAL
    assert excinfo.value.message == header["stderr"]
    assert broker.last_supervisor == header["supervisor"]
    assert broker.last_child_setup == header["child_setup"]


_MUTATIONS = [
    ("forged_code", lambda h: h.update(state_rejection="links_allowed")),
    ("wrong_exit_code", lambda h: h.update(exit_code=0)),
    # bool is an int subtype in Python/JSON and True == 1; the schema must check
    # type(exit_code) is int, not merely its value, or a forged True slips through.
    ("bool_exit_code_true", lambda h: h.update(exit_code=True)),
    ("nonempty_stdout", lambda h: h.update(stdout="leaked")),
    ("empty_stderr", lambda h: h.update(stderr="")),
    ("oversize_stderr", lambda h: h.update(stderr="x" * 8193)),
    # 5000 chars (<= the 8192 character bound) but 10000 encoded UTF-8 bytes
    # (> the 8192 byte bound): a short-looking string that is oversize on the wire.
    ("unicode_overflow_stderr", lambda h: h.update(stderr="\u00e9" * 5000)),
    # A lone surrogate is a valid Python str but cannot be UTF-8 encoded at all.
    ("unencodable_surrogate_stderr", lambda h: h.update(stderr="\ud800")),
    ("non_string_stderr", lambda h: h.update(stderr=None)),
    ("missing_child_setup", lambda h: h.pop("child_setup")),
    ("child_setup_not_dict", lambda h: h.update(child_setup=["uid", 1001])),
    ("extra_key", lambda h: h.update(extra="unexpected")),
    ("supervisor_not_dict", lambda h: h.update(supervisor=["before", "after"])),
    ("supervisor_extra_key", lambda h: h["supervisor"].update(extra="spoofed")),
    ("supervisor_missing_after", lambda h: h["supervisor"].pop("after")),
    ("supervisor_before_not_dict", lambda h: h["supervisor"].update(before="not-a-dict")),
]


@pytest.mark.parametrize("mutate", [fn for _, fn in _MUTATIONS], ids=[name for name, _ in _MUTATIONS])
def test_accept_rejects_malformed_execute_rejection_headers(tmp_path, mutate):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    header = _valid_rejection_header()
    mutate(header)
    with pytest.raises(isolation.IsolationError):
        broker._accept(EXECUTE_REQUEST, header, b"")


def test_accept_rejects_execute_rejection_with_unexpected_state_blob(tmp_path):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    header = _valid_rejection_header()
    with pytest.raises(isolation.IsolationError):
        broker._accept(EXECUTE_REQUEST, header, b"unexpected opaque bytes")


@pytest.mark.parametrize("op", ["seed", "export", "evaluate", None])
def test_accept_rejects_rejection_schema_outside_execute(tmp_path, op):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    header = _valid_rejection_header()
    with pytest.raises(isolation.IsolationError):
        broker._accept({"op": op}, header, b"")


def test_accept_rejects_success_shaped_variant_carrying_rejection_code(tmp_path):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    header = _valid_rejection_header(ok=True)
    with pytest.raises(isolation.IsolationError):
        broker._accept(EXECUTE_REQUEST, header, b"")


def test_accept_still_verifies_and_returns_genuine_success(tmp_path):
    """The _accept refactor must not weaken or bypass the pre-existing success path."""
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    header = _success_header()
    result, state = broker._accept(EXECUTE_REQUEST, header, b"opaque-state-bytes")
    assert result is header and state == b"opaque-state-bytes"
    assert broker.last_supervisor == header["supervisor"]
    assert broker.last_child_setup == header["child_setup"]


def test_accept_fails_closed_for_forged_identity_in_genuine_success(tmp_path):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    header = _success_header()
    header["child_setup"]["uid"] = [0, 0, 0]
    with pytest.raises(helper.ProtocolError):
        broker._accept(EXECUTE_REQUEST, header, b"opaque-state-bytes")


def test_execute_returns_explicit_failed_result_without_publishing(tmp_path, monkeypatch):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    token = broker._publish(b"prior opaque state", {"seed_head": "f" * 40, "seed_manifest": {}})
    header = _valid_rejection_header()
    monkeypatch.setattr(
        broker, "_launch", lambda request, blob=b"", mounts=None: broker._accept(request, header, b""),
    )
    result = broker.execute(token, "ln -s /etc/passwd bad-link", 5)
    assert result == {
        "state": token, "stdout": "", "stderr": header["stderr"], "exit_code": 1,
        "timed_out": False, "state_rejection": isolation.STATE_REJECTION_LINKS_OR_SPECIAL,
    }
    metadata, blob = broker._state(token)
    assert blob == b"prior opaque state" and metadata["seed_head"] == "f" * 40
    # Continued safe execution: the retained token still resolves, future calls are unaffected.
    assert broker._state(token)[0]["slot"] in ("latest.state", "pending.state")


def test_execute_fails_closed_for_forged_identity_proof_and_preserves_state(tmp_path, monkeypatch):
    broker = isolation.SandboxBroker(IMAGE, tmp_path)
    token = broker._publish(b"prior opaque state", {"seed_head": "f" * 40, "seed_manifest": {}})
    header = _valid_rejection_header()
    header["child_setup"]["uid"] = [0, 0, 0]
    monkeypatch.setattr(
        broker, "_launch", lambda request, blob=b"", mounts=None: broker._accept(request, header, b""),
    )
    with pytest.raises(isolation.IsolationError):
        broker.execute(token, "ln -s /etc/passwd bad-link", 5)
    _metadata, blob = broker._state(token)
    assert blob == b"prior opaque state"


def test_strip_transport_metadata_removes_exactly_the_two_verified_keys():
    """Real frame()/unframe() output always carries blob_length/blob_sha256; this is
    the exact bug a real image build hit -- _accept's 7-key schema rejected real
    wire headers because unframe() never stripped its own framing fields."""
    logical = {"ok": True, "exit_code": 0, "stdout": "x", "stderr": "", "child_setup": {"a": 1},
               "supervisor": {"before": {}, "after": {}}}
    wire = helper.frame(logical, b"some opaque state bytes")
    parsed_header, blob = helper.unframe(io.BytesIO(wire))
    assert {"blob_length", "blob_sha256"} <= set(parsed_header)
    assert set(parsed_header) - {"blob_length", "blob_sha256"} == set(logical)
    stripped = isolation._strip_transport_metadata(parsed_header, blob)
    assert stripped == logical


@pytest.mark.parametrize("header", [
    {"ok": True},  # both transport keys missing entirely
    {"ok": True, "blob_length": 0},  # blob_sha256 missing
    {"ok": True, "blob_length": 5, "blob_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    {"ok": True, "blob_length": 0, "blob_sha256": "not-the-real-digest"},
    {"ok": True, "blob_length": False, "blob_sha256": hashlib.sha256(b"").hexdigest()},
    {"ok": True, "blob_length": 0.0, "blob_sha256": hashlib.sha256(b"").hexdigest()},
], ids=["both_missing", "sha256_missing", "length_mismatch", "sha256_mismatch", "boolean_length", "float_length"])
def test_strip_transport_metadata_rejects_missing_or_mismatched_keys(header):
    with pytest.raises(isolation.IsolationError):
        isolation._strip_transport_metadata(header, b"")


def test_real_frame_unframe_accept_round_trip_for_execute_rejection(tmp_path, monkeypatch):
    """Full real pipeline: pack_tree/supervisor() -> frame() -> unframe() ->
    _strip_transport_metadata() -> _accept() -> execute(), exactly as _launch calls
    them in order, driven by bytes a real helper image would actually emit."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "plain").write_bytes(b"ok")
    (work / "bad-link").symlink_to("plain")
    monkeypatch.setattr(helper, "WORK", work)
    monkeypatch.setattr(helper, "run_child", lambda *a, **k: {
        "exit_code": 0, "stdout": "", "stderr": "", "child_setup": _identity(supervisor=False),
    })
    request = {"op": "execute", "command": "ln -s plain bad-link", "timeout": 5}
    result, state = helper.supervisor(request, b"")
    assert state == b""
    # Mirror main()'s own ok computation and frame header assembly exactly.
    ok = "state_rejection" not in result
    logical_header = {"ok": ok, **result,
                       "supervisor": {"before": _identity(supervisor=True), "after": _identity(supervisor=True)}}

    # Real wire round trip -- this is exactly what main() writes and _launch reads.
    wire = helper.frame(logical_header, state)
    parsed_header, parsed_blob = helper.unframe(io.BytesIO(wire))
    assert sorted(parsed_header) == sorted(
        ["blob_length", "blob_sha256", "child_setup", "exit_code", "ok", "state_rejection", "stderr",
         "stdout", "supervisor"],
    )

    broker = isolation.SandboxBroker(IMAGE, tmp_path / "broker")
    token = broker._publish(b"prior opaque state", {"seed_head": "f" * 40, "seed_manifest": {}})

    def fake_launch(req, blob=b"", mounts=None):
        # Mirrors _launch's own tail exactly, from real unframe() output onward.
        header = isolation._strip_transport_metadata(parsed_header, parsed_blob)
        return broker._accept(req, header, parsed_blob)

    monkeypatch.setattr(broker, "_launch", fake_launch)
    outcome = broker.execute(token, request["command"], 5)
    assert outcome["state"] == token
    assert outcome["state_rejection"] == helper.STATE_REJECTION_LINKS_OR_SPECIAL
    assert outcome["state_rejection"] == isolation.STATE_REJECTION_LINKS_OR_SPECIAL
    assert outcome["exit_code"] == 1 and outcome["stdout"] == "" and not outcome["timed_out"]
    assert "prior state is retained" in outcome["stderr"].lower()
    _metadata, blob = broker._state(token)
    assert blob == b"prior opaque state"
