"""Trusted snapshot and transport failure tests; no model sessions."""
import base64
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

_REAL_POPEN = subprocess.Popen


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    return importlib.import_module("isolated_runtime")


def file_record(name, content="value", mode=0o644):
    return {"path": name, "mode": mode, "content": base64.b64encode(content.encode()).decode()}


def test_export_rejects_unsafe_paths_modes_and_conflicts_before_publish(runtime, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    runtime.git(repo, "init", "-q")
    (repo / "retained").write_text("previous")
    invalid = [
        [file_record("../escape")], [file_record("/absolute")], [file_record(".git/config")],
        [file_record("src//code.py")], [file_record("bad\nname")],
        [file_record("\ud800")],
        [file_record("src/file", mode=0o777)], [file_record("a"), file_record("a/b")],
        [file_record("src/a"), file_record("src/a")],
        [{"path": "bad", "mode": 0o644, "content": "not-base64!"}],
    ]
    for files in invalid:
        with pytest.raises(runtime.StudyError):
            runtime.replace_tree(repo, files)
        assert (repo / "retained").read_text() == "previous"
    assert not (tmp_path / "escape").exists()


def test_safe_publish_keeps_private_git_and_roundtrips_executable_files(runtime, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    runtime.git(repo, "init", "-q")
    marker = repo / ".git/private-marker"
    marker.write_text("trusted-only")
    (repo / "obsolete").write_text("old")
    files = [file_record("src/code.py", "print('x')\n"), file_record("tcr", "#!/bin/sh\n", 0o755)]
    runtime.replace_tree(repo, files)
    assert runtime.regular_files(repo) == files
    assert not (repo / "obsolete").exists()
    assert marker.read_text() == "trusted-only"


def test_trusted_git_ignores_personal_hooks_and_inherited_git_overrides(runtime, tmp_path, monkeypatch):
    repo, hooks = tmp_path / "repo", tmp_path / "hooks"
    repo.mkdir()
    hooks.mkdir()
    marker = tmp_path / "executed"
    hook = hooks / "post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    config = tmp_path / "global"
    config.write_text(f"[core]\n\thooksPath = {hooks}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-the-owned-repository"))
    runtime.git(repo, "init", "-q")
    runtime.git(repo, "config", "user.name", "test")
    runtime.git(repo, "config", "user.email", "test@example.invalid")
    runtime.git(repo, "commit", "--allow-empty", "-qm", "test")
    runtime.git(repo, "checkout", "-q", "-b", "second")
    assert not marker.exists()


def fake_bridge(runtime, monkeypatch, program):
    monkeypatch.setattr(runtime.subprocess, "Popen",
                        lambda *args, **kwargs: _REAL_POPEN([sys.executable, "-c", program], **kwargs))


def test_bridge_journals_correlated_events_before_accepting_completion(runtime, tmp_path, monkeypatch):
    fake_bridge(runtime, monkeypatch, """
import json, sys
json.loads(sys.stdin.readline())
print(json.dumps({"type":"event","sessionId":"owned","event":{"type":"assistant.usage"}}), flush=True)
print(json.dumps({"type":"complete","receipt":{"session_id":"owned","usage":{"credits_complete":False}}}), flush=True)
""")
    result = runtime.run_bridge({"remainingSeconds": 5}, tmp_path, lambda *args: pytest.fail("No tool expected"))
    assert result["receipt"]["usage"]["credits_complete"] is False
    records = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert len(records) == 2 and records[0]["sessionId"] == "owned"


def test_bridge_evidence_cap_and_bad_correlation_never_yield_receipts(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "JOURNAL_LIMIT", 250)
    programs = [
        'import sys; sys.stdin.readline(); print("x"*1000, flush=True)',
        '''import json,sys
sys.stdin.readline()
for session in ("first","other"):
 print(json.dumps({"type":"event","sessionId":session}),flush=True)
''',
        '''import json,sys
sys.stdin.readline()
for _ in range(20):
 print(json.dumps({"type":"event","sessionId":"owned"}),flush=True)
''',
        '''import json,sys
sys.stdin.readline()
print(json.dumps({"type":"event","sessionId":"owned"}),flush=True)
print(json.dumps({"type":"complete","receipt":{"session_id":"other"}}),flush=True)
''',
    ]
    for index, program in enumerate(programs):
        fake_bridge(runtime, monkeypatch, program)
        with pytest.raises(runtime.StudyError):
            runtime.run_bridge({"remainingSeconds": 5}, tmp_path / str(index), lambda *args: None)
        assert (tmp_path / str(index) / "events.jsonl").stat().st_size <= 250


def test_fingerprint_ignores_only_generated_sdk_tree_not_its_pin(runtime, tmp_path):
    study = importlib.import_module("study")
    sdk = tmp_path / "harness/copilot-sdk"
    installed = sdk / "node_modules"
    installed.mkdir(parents=True)
    manifest = sdk / "package-lock.json"
    manifest.write_text('{"version":"pinned"}')
    before = study.fingerprint(tmp_path)
    (installed / "unused-link").symlink_to(tmp_path / "not-present")
    (installed / "generated").write_text("not a protocol source file")
    assert study.fingerprint(tmp_path) == before
    manifest.write_text('{"version":"different"}')
    assert study.fingerprint(tmp_path) != before


def test_runtime_gate_rejects_missing_checks_stale_source_and_wrong_frozen_image(runtime, tmp_path):
    study = importlib.import_module("study")
    names = ("Dockerfile.isolated", "isolation.py", "isolation_helper.py",
             "isolation_canary.py", "tests/test_isolation.py")
    for name in names:
        path = tmp_path / "harness" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("offline metadata fixture\n")
    package = tmp_path / "harness/copilot-sdk/node_modules/@github/copilot-sdk/package.json"
    runtime.atomic_json(package, {"version": "1.0.28"})
    sources = {name: hashlib.sha256((tmp_path / "harness" / name).read_bytes()).hexdigest() for name in names}
    receipt = {"schema": "isolated-runtime-canary/v1", "success": True, "image": "sha256:" + "0" * 64,
               "checks": dict.fromkeys(runtime.CANARY_CHECKS, True), "source_inputs": sources,
               "image_helper_sha256": sources["isolation_helper.py"], "inputs_sha256": study.fingerprint(tmp_path)}
    receipt_path = tmp_path / ".study/runtime-canary.json"
    runtime.atomic_json(receipt_path, receipt)
    freeze_path = tmp_path / "protocol/freeze.json"
    freeze = {"runtime_image": receipt["image"],
              "runtime_canary_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    runtime.atomic_json(freeze_path, freeze)
    cfg = {"freeze_manifest": "protocol/freeze.json"}
    assert runtime.runtime_errors(cfg, tmp_path) == []
    for key, value in (("checks", {}), ("inputs_sha256", "stale"), ("image_helper_sha256", "wrong"),
                       ("success", False), ("schema", "unsupported")):
        runtime.atomic_json(receipt_path, dict(receipt, **{key: value}))
        assert runtime.runtime_errors(cfg, tmp_path)
    runtime.atomic_json(receipt_path, receipt)
    runtime.atomic_json(freeze_path, dict(freeze, runtime_image="sha256:" + "1" * 64))
    assert runtime.runtime_errors(cfg, tmp_path)


def trusted_repo(runtime, root):
    repo = root / "repo"
    repo.mkdir()
    runtime.git(repo, "init", "-q")
    runtime.git(repo, "config", "user.name", "test")
    runtime.git(repo, "config", "user.email", "test@example.invalid")
    runtime.replace_tree(repo, [file_record("src/code.py", "VALUE = 1\n")])
    runtime.git(repo, "add", "-A")
    runtime.git(repo, "commit", "-qm", "seed")
    return repo


def test_changed_head_equal_tree_preserves_delivery_but_wip_never_becomes_a_commit(runtime, tmp_path):
    repo = trusted_repo(runtime, tmp_path)
    live = object.__new__(runtime.LiveRuntime)
    live.run = SimpleNamespace(repo=repo)
    live.last_checkpoint = None
    before = runtime.head(repo)
    files = runtime.regular_files(repo)
    live.publish_committed({"head_changed": False, "files": files})
    assert runtime.head(repo) == before
    live.publish_committed({"head_changed": True, "files": files})
    assert runtime.head(repo) != before
    assert runtime.git(repo, "diff", "--numstat", before, "HEAD").stdout == ""
    with pytest.raises(runtime.StudyError, match="inconsistent committed content"):
        live.publish_committed({"head_changed": False, "files": [file_record("src/code.py", "uncommitted")]})
    assert (repo / "src/code.py").read_text() == "VALUE = 1\n"


def test_committed_import_preserves_ignored_blob_bytes_without_attribute_filters(runtime, tmp_path):
    repo = trusted_repo(runtime, tmp_path)
    live = object.__new__(runtime.LiveRuntime)
    live.run = SimpleNamespace(repo=repo)
    content = "VALUE = 'literal bytes'\r\n"
    files = [file_record(".gitignore", "*\n"), file_record(".gitattributes", "* text eol=lf\n"),
             file_record("src/code.py", content), file_record('ignored/with,"quotes"', "retained", 0o755)]
    live.publish_committed({"head_changed": True, "files": files})
    expected_hash = hashlib.sha1(f"blob {len(content.encode())}\0".encode() + content.encode(),
                                usedforsecurity=False).hexdigest()
    assert runtime.git(repo, "rev-parse", "HEAD:src/code.py").stdout.strip() == expected_hash
    tracked = runtime.git(repo, "ls-files", "-z").stdout.split("\0")
    assert set(tracked) - {""} == {item["path"] for item in files}
    assert runtime.git(repo, "status", "--porcelain").stdout == ""
    assert (repo / 'ignored/with,"quotes"').stat().st_mode & 0o777 == 0o755


def test_c_review_keeps_uncommitted_review_and_reports_other_edits_without_import(runtime, tmp_path):
    repo = trusted_repo(runtime, tmp_path)
    live = object.__new__(runtime.LiveRuntime)
    records = []
    live.run = SimpleNamespace(
        repo=repo, dir=str(tmp_path), budgets={"post": 900},
        measure=lambda *args: {"head": runtime.head(repo)}, record=records.append)
    live.last_export = {
        "review": file_record("REVIEW.md", "Current review\r\n")["content"],
        "changed_paths": ["REVIEW.md", "src/code.py"],
        "files": [file_record("src/code.py", "must not enter trusted staging")],
    }
    live.run_agent = lambda *args: {"usage": {"credits_complete": True, "totalNanoAiu": 0}}
    live.review_step(1)
    assert (repo / "src/code.py").read_text() == "VALUE = 1\n"
    assert (repo / "REVIEW.md").read_bytes() == b"Current review\n"
    assert records[0]["commits"] == 1
    assert records[0]["violations"] == ["review step changed other files: src/code.py"]


def test_live_controller_uses_registered_budgets_and_external_metrics(runtime, tmp_path):
    study = importlib.import_module("study")
    config = dict(study.read_json(study.ROOT / "harness/study-config.json"), prior_credits=14.54324)
    current = study.Controller(tmp_path, config, smoke=False, phase="first", study_id="offline-plan")
    selected = study.read_json(current.runtime_config)
    assert selected["budgets_seconds"] == {"feature": 1800, "post": 900, "change_request": 2700}
    assert selected["measure"] == {
        "test_runner": "pytest", "complexity": "lizard", "duplication": "jscpd", "lint": "ruff"}


def test_ambiguous_broker_failure_stops_admission_even_after_usage_is_known(runtime):
    from isolation import IsolationError

    def failed_export(*args, **kwargs):
        raise IsolationError("ambiguous owned container")

    live = object.__new__(runtime.LiveRuntime)
    persisted = []
    controller = SimpleNamespace(state={}, save=lambda: persisted.append(True))
    live.run = SimpleNamespace(controller=controller)
    live.broker = SimpleNamespace(export=failed_export)
    with pytest.raises(runtime.StudyError, match="reconcile exact owned resources"):
        live.broker_call("export", "opaque-state")
    assert controller.state["oracle_halt"] is True and persisted


@pytest.mark.parametrize("outcome", ["complete", "unknown", "wrong_model", "bad_export"])
def test_live_attempt_reserves_before_transport_and_preserves_charge_on_failure(
    runtime, tmp_path, monkeypatch, outcome,
):
    study = importlib.import_module("study")
    config = dict(study.read_json(study.ROOT / "harness/study-config.json"), prior_credits=14.54324)
    current = study.Controller(tmp_path / "private", config,
                               smoke=False, phase="first", study_id="offline-transport-fixture")
    cell = current.state["cells"][0]
    repo = trusted_repo(runtime, tmp_path)
    live = object.__new__(runtime.LiveRuntime)
    live.run = SimpleNamespace(
        controller=current, cell=cell, current_step="f01-feature", repo=repo,
        dir=str(current.directory / "fixture"), assigned_model=cell["assigned_model"],
        remaining_allowance=lambda budget: (budget, 270 * runtime.NANO))
    live.receipt = {"image": "sha256:" + "0" * 64}
    live.last_checkpoint = None
    monkeypatch.setattr(runtime, "runtime_errors", lambda cfg: [])

    def seed(files, *, git_bundle):
        stored = runtime.read_json(current.path)["ledger"]["entries"]
        assert next(iter(stored.values()))["reserved_nano"] == 300 * runtime.NANO
        assert git_bundle and files
        return "opaque-fixture-state"

    live.broker = SimpleNamespace(
        seed=seed, export=lambda *args, **kwargs: {
            "head_changed": True, "files": [file_record(
                ".git/config" if outcome == "bad_export" else "src/code.py", "VALUE = 2\n")]})

    def bridge(request, directory, tool, **callbacks):
        assert request["maxAiCredits"] == 270 and 0 < request["remainingSeconds"] <= 900
        assert runtime.read_json(directory.parent / "request.json")["prompt"] == "offline fixture prompt"
        callbacks["on_start"](123)
        callbacks["on_stop"]()
        return {"exit_code": 0, "receipt": {
            "sdk_version": "1.0.28", "cli_version": "1.0.105", "protocol_version": 3,
            "protocol_error": None, "actual_models": ["other"] if outcome == "wrong_model" else [cell["assigned_model"]],
            "actual_reasoning_efforts": ["medium"],
            "usage": {"credits_complete": outcome != "unknown", "totalNanoAiu": 2 * runtime.NANO},
        }}

    monkeypatch.setattr(runtime, "run_bridge", bridge)
    if outcome == "complete":
        live.run_agent("offline fixture prompt", str(tmp_path / "steps"), 900)
        assert (repo / "src/code.py").read_text() == "VALUE = 2\n"
    else:
        with pytest.raises(runtime.StudyError):
            live.run_agent("offline fixture prompt", str(tmp_path / "steps"), 900)
        assert (repo / "src/code.py").read_text() == "VALUE = 1\n"
    entry = next(iter(current.state["ledger"]["entries"].values()))
    if outcome == "unknown":
        assert entry["status"] == "unknown" and entry["actual_nano"] is None
        with pytest.raises(runtime.StudyError, match="Unknown usage"):
            current.new_attempt(cell, "f02-feature")
    else:
        assert entry["status"] == "complete" and entry["actual_nano"] == 2 * runtime.NANO
    if outcome in ("wrong_model", "bad_export"):
        assert current.state["oracle_halt"] is True
    assert current.state["writer_pid"] is None and not current.state["writer_pending"]


@pytest.mark.skipif(not os.environ.get("MVE_TEST_ISOLATED_IMAGE"), reason="explicit offline Docker image required")
@pytest.mark.parametrize("stage,k,cr", [("f01", 1, False), ("f10", 10, False), ("cr1", 10, True)])
def test_real_isolated_evaluation_matches_frozen_reference_without_snapshot_writeback(
    runtime, tmp_path, stage, k, cr,
):
    from isolation import SandboxBroker

    image = os.environ["MVE_TEST_ISOLATED_IMAGE"]
    source = runtime.ROOT
    suite_dir = source / "suites/s1-retrofit"
    suite = runtime.read_json(suite_dir / "suite.json")
    repo = tmp_path / "repo"
    shutil.copytree(source / "skeleton", repo)
    runtime.git(repo, "init", "-q")
    runtime.git(repo, "config", "user.name", "offline fixture")
    runtime.git(repo, "config", "user.email", "fixture@example.invalid")
    runtime.git(repo, "add", "-A")
    runtime.git(repo, "commit", "-qm", "offline fixture seed")
    runtime.git(repo, "update-ref", "refs/heads/feature-start", "HEAD")
    shutil.copytree(suite_dir / "reference" / stage, repo / "src", dirs_exist_ok=True)
    items = [(feature, "features") for feature in suite["features"][:k]]
    if cr:
        items.append((suite["change_request"], ""))
    for item, prefix in items:
        for path in (suite_dir / prefix / item["id"] / "examples").glob("*.py"):
            shutil.copyfile(path, repo / "tests/examples" / path.name)
    runtime.git(repo, "add", "-A")
    runtime.git(repo, "commit", "-qm", "offline frozen reference")
    before = runtime.head(repo)
    live = object.__new__(runtime.LiveRuntime)
    live.receipt = runtime.read_json(runtime.CANARY)
    assert live.receipt["image"] == image
    live.broker = SandboxBroker(image, tmp_path / "isolation")
    live.run = SimpleNamespace(
        dir=str(tmp_path), repo=repo, suite=suite, suite_dir=suite_dir,
        cfg={"measure": {"test_runner": "pytest"}}, cell={"attempts": [{"id": "offline-fixture"}]},
        controller=SimpleNamespace(state={"deadline": time.time() + 180}, save=lambda: None))
    assert live.visible()
    result = live.measure(k, str(tmp_path / "steps/offline-fixture"), "feature-start", cr)
    assert result["hidden_passed"] == result["hidden_total"] > 0
    panel = runtime.read_json(source / "protocol/contract-panel.json")["contracts"]
    expected = {item["id"] for item in panel if item["from_cycle"] <= k or (cr and item["role"] == "cr1")}
    assert set(result["hidden"]) == expected
    assert result["metrics"]["mean_ccn"] > 0
    assert runtime.head(repo) == before and not runtime.git(repo, "status", "--porcelain").stdout
