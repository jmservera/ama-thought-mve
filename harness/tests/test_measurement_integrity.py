"""Synthetic regressions for local evaluation and measurement integrity."""

import importlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


KIT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def measure_module(monkeypatch):
    monkeypatch.syspath_prepend(str(KIT_ROOT / "harness"))
    return importlib.import_module("measure")


@pytest.fixture
def synthetic_evaluation_parent(tmp_path, monkeypatch):
    environment = {
        "PATH": str(Path(sys.executable).parent) + os.pathsep + str(tmp_path / "local-tools"),
        "LD_LIBRARY_PATH": str(tmp_path / "libraries"),
        "HOME": str(tmp_path / "parent-home"),
        "COPILOT_GITHUB_TOKEN": "synthetic-review-marker",
        "GITHUB_TOKEN": "synthetic-parent-token",
        "UNLISTED_CREDENTIAL": "synthetic-unlisted-credential",
        "PYTHONPATH": "synthetic-startup-path",
        "PYTHONSTARTUP": "synthetic-startup-hook",
        "PYTEST_ADDOPTS": "synthetic-pytest-options",
        "BASH_ENV": "synthetic-shell-hook",
        "LD_PRELOAD": "synthetic-loader-hook",
        "NODE_OPTIONS": "synthetic-node-hook",
        "TEST_CMD": "synthetic-offline-test-command",
        "MVE_COMPLEXITY": "internal",
        "MVE_DUPLICATION": "internal",
        "MVE_LINT": "none",
    }
    monkeypatch.setattr(os, "environ", environment)
    return environment


def assert_minimal_evaluation_environment(environment, parent):
    assert environment is not None
    assert not {
        "COPILOT_GITHUB_TOKEN", "GITHUB_TOKEN", "UNLISTED_CREDENTIAL", "AGENT_EXTRA",
        "PYTHONPATH", "PYTHONSTARTUP", "PYTEST_ADDOPTS", "BASH_ENV", "LD_PRELOAD", "NODE_OPTIONS",
    } & environment.keys()
    for name in ("LD_LIBRARY_PATH", "TEST_CMD", "MVE_COMPLEXITY", "MVE_DUPLICATION", "MVE_LINT"):
        assert environment[name] == parent[name]
    assert environment["PATH"].split(os.pathsep)[-1] == parent["PATH"].split(os.pathsep)[-1]
    assert environment["HOME"] != parent["HOME"]
    owned_paths = [Path(environment[name]) for name in (
        "HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TMPDIR",
    )]
    assert all(path.is_dir() for path in owned_paths)
    assert len({path.parent for path in owned_paths}) == 1
    return owned_paths


def test_given_synthetic_credentials_when_evaluator_entry_is_launched_then_environment_is_credential_minimal(
    tmp_path, measure_module, monkeypatch, synthetic_evaluation_parent
):
    runner_module = importlib.import_module("runner")
    run = runner_module.Run.__new__(runner_module.Run)
    run.cfg = {"measure": {
        "test_runner": "stdlib", "complexity": "internal", "duplication": "internal", "lint": "none",
    }}
    run.repo = run.suite_dir = str(tmp_path)
    run.env_extra = {"GITHUB_TOKEN": "synthetic-agent-token", "AGENT_EXTRA": "synthetic-agent-value"}
    owned_paths = []

    def fake_run(command, **kwargs):
        owned_paths.extend(assert_minimal_evaluation_environment(kwargs.get("env"), synthetic_evaluation_parent))
        for flag, value in (("--runner", "stdlib"), ("--complexity", "internal"),
                            ("--duplication", "internal"), ("--lint", "none")):
            assert command[command.index(flag) + 1] == value
        return subprocess.CompletedProcess(command, 1, "", "synthetic stop")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="measure failed: synthetic stop"):
        run.measure(1, str(tmp_path), None)

    assert owned_paths
    assert all(not path.exists() for path in owned_paths)
    assert run.env()["COPILOT_GITHUB_TOKEN"] == "synthetic-review-marker"
    assert run.env()["GITHUB_TOKEN"] == "synthetic-agent-token"
    assert run.env()["AGENT_EXTRA"] == "synthetic-agent-value"


@pytest.mark.parametrize("tool", ["ruff", "jscpd"])
def test_given_synthetic_credentials_when_metric_children_are_launched_then_environments_are_credential_minimal(
    tmp_path, metrics_module, monkeypatch, synthetic_evaluation_parent, tool
):
    owned_paths = []
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: f"/synthetic/{name}")

    def fake_run(command, **kwargs):
        owned_paths.extend(assert_minimal_evaluation_environment(kwargs.get("env"), synthetic_evaluation_parent))
        if tool == "jscpd":
            report = Path(command[command.index("--output") + 1]) / "jscpd-report.json"
            report.write_text(json.dumps({
                "statistics": {"total": {"duplicatedLines": 0, "lines": 1, "percentage": 0}}, "duplicates": [],
            }), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(metrics_module.subprocess, "run", fake_run)

    if tool == "ruff":
        result = metrics_module.lint(str(tmp_path), "ruff")
    else:
        result = metrics_module.duplication(str(tmp_path), [], "jscpd")

    assert result["backend"] == tool
    assert owned_paths
    assert all(not path.exists() for path in owned_paths)
    assert os.environ["COPILOT_GITHUB_TOKEN"] == "synthetic-review-marker"


@pytest.mark.parametrize("source", ["parent", "config"])
def test_given_safe_test_command_override_when_green_check_runs_then_only_test_command_is_forwarded(
    tmp_path, measure_module, monkeypatch, synthetic_evaluation_parent, source
):
    runner_module = importlib.import_module("runner")
    run = runner_module.Run.__new__(runner_module.Run)
    run.repo = str(tmp_path)
    run.env_extra = {"PATH": "/synthetic/agent-path", "GITHUB_TOKEN": "synthetic-agent-token"}
    expected_settings = dict(synthetic_evaluation_parent)
    if source == "config":
        run.env_extra["TEST_CMD"] = expected_settings["TEST_CMD"] = "synthetic-config-test-command"
    owned_paths = []

    def fake_run(command, **kwargs):
        assert command == ["make", "-s", "test"]
        owned_paths.extend(assert_minimal_evaluation_environment(kwargs.get("env"), expected_settings))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    assert run.is_green() is True

    assert owned_paths
    assert all(not path.exists() for path in owned_paths)


def test_given_agent_authentication_when_agent_command_is_launched_then_its_environment_is_unchanged(
    tmp_path, measure_module, monkeypatch, synthetic_evaluation_parent
):
    runner_module = importlib.import_module("runner")
    run = runner_module.Run.__new__(runner_module.Run)
    run.repo = run.suite_dir = str(tmp_path)
    run.cfg = {
        "agent_command": ["synthetic-agent", "--repo", "{repo}"],
        "agent_env": {"AGENT_TEMPLATE": "{repo}", "COPILOT_GITHUB_TOKEN": "synthetic-agent-override"},
    }
    run.env_extra = {"GITHUB_TOKEN": "synthetic-agent-token", "PATH": "/synthetic/agent-path"}
    expected_environment = {**synthetic_evaluation_parent, **run.env_extra,
                            "AGENT_TEMPLATE": str(tmp_path), "COPILOT_GITHUB_TOKEN": "synthetic-agent-override"}
    launched_environments = []

    class SyntheticAgent:
        returncode = 0

        def wait(self, timeout):
            assert timeout == 60

    def fake_launch(command, **kwargs):
        assert command == ["synthetic-agent", "--repo", str(tmp_path)]
        launched_environments.append(kwargs["env"])
        return SyntheticAgent()

    monkeypatch.setattr(runner_module.subprocess, "Popen", fake_launch)
    monkeypatch.setattr(run, "leak_check", lambda step_dir: False)

    result = run.run_agent("synthetic prompt", str(tmp_path / "agent-step"), 60)

    assert result["exit_code"] == 0
    assert launched_environments == [expected_environment]
    assert os.environ["COPILOT_GITHUB_TOKEN"] == "synthetic-review-marker"


def test_given_candidate_module_collision_when_environment_helper_loads_then_only_kit_source_is_used(
    tmp_path, monkeypatch, synthetic_evaluation_parent
):
    tmp_path.joinpath("metrics_core.py").write_text("raise AssertionError('candidate module imported')\n",
                                                 encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(sys.modules, "metrics_core", None)
    module_spec = importlib.util.spec_from_file_location("synthetic_evaluation_helper",
                                                       KIT_ROOT / "harness" / "evaluation_env.py")
    environment_module = importlib.util.module_from_spec(module_spec)

    module_spec.loader.exec_module(environment_module)

    with environment_module.evaluation_environment() as environment:
        owned_paths = assert_minimal_evaluation_environment(environment, synthetic_evaluation_parent)
    assert all(not path.exists() for path in owned_paths)


def test_given_standalone_metrics_when_harness_imports_are_unavailable_then_internal_backends_still_work(
    tmp_path, monkeypatch, synthetic_evaluation_parent
):
    monkeypatch.setitem(sys.modules, "harness", None)
    monkeypatch.setitem(sys.modules, "evaluation_env", None)
    module_spec = importlib.util.spec_from_file_location("synthetic_standalone_metrics",
                                                       KIT_ROOT / "skeleton" / "tools" / "metrics_core.py")
    metrics = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(metrics)
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("src", "source.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = metrics.measure(str(tmp_path))

    assert result["backends"] == {"complexity": "internal", "duplication": "internal", "lint": "none"}
    with metrics.evaluation_environment() as environment:
        owned_paths = assert_minimal_evaluation_environment(environment, synthetic_evaluation_parent)
    assert all(not path.exists() for path in owned_paths)


@pytest.mark.parametrize("tool", ["ruff", "jscpd"])
def test_given_interpreter_and_local_tool_paths_when_metric_lookup_runs_then_both_remain_available(
    tmp_path, metrics_module, monkeypatch, synthetic_evaluation_parent, tool
):
    synthetic_evaluation_parent["PATH"] = str(tmp_path / "local-tools")
    paths = []

    def fake_which(name, path=None):
        paths.append(path)
        assert path.split(os.pathsep) == [str(Path(sys.executable).parent), str(tmp_path / "local-tools")]
        return None

    monkeypatch.setattr(metrics_module.shutil, "which", fake_which)

    with pytest.raises(RuntimeError, match="not on PATH|not available"):
        if tool == "ruff":
            metrics_module.lint(str(tmp_path), "ruff")
        else:
            metrics_module.duplication(str(tmp_path), [], "jscpd")

    assert len(paths) == 1


def test_given_missing_later_feature_when_hidden_tests_run_then_prior_feature_still_passes(
    tmp_path, measure_module, runner
):
    repo = tmp_path / "candidate"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "prior.py").write_text("VALUE = 1\n", encoding="utf-8")
    suite = tmp_path / "suite"
    prior_tests = suite / "features" / "f1" / "hidden"
    prior_tests.mkdir(parents=True)
    (prior_tests / "test_prior.py").write_text(
        "from prior import VALUE\n\ndef test_prior():\n    assert VALUE == 1\n",
        encoding="utf-8",
    )
    later_tests = suite / "features" / "f2" / "hidden"
    later_tests.mkdir(parents=True)
    (later_tests / "test_later.py").write_text(
        "from missing_later_feature import VALUE\n\ndef test_later():\n    assert VALUE == 2\n",
        encoding="utf-8",
    )

    result = measure_module.run_hidden(str(repo), str(suite), ["f1", "f2"], runner)

    assert result == {"test_prior::test_prior": "passed", "test_later::test_later": "error"}


@pytest.fixture(params=["pytest", "stdlib"])
def runner(request):
    return request.param


@pytest.fixture
def hidden_candidate(tmp_path):
    repo = tmp_path / "candidate"
    (repo / "src").mkdir(parents=True)
    suite = tmp_path / "suite"
    hidden = suite / "features" / "f1" / "hidden"
    hidden.mkdir(parents=True)
    test = hidden / "test_feature.py"
    test.write_text("def test_feature():\n    assert True\n", encoding="utf-8")
    return repo, suite, test


def test_given_parent_credentials_and_startup_hooks_when_hidden_tests_run_then_child_does_not_inherit_them(
    hidden_candidate, measure_module, monkeypatch, runner
):
    repo, suite, test = hidden_candidate
    parent_names = (
        "COPILOT_GITHUB_TOKEN", "AZURE_CLIENT_SECRET", "GITHUB_TOKEN", "UNLISTED_CREDENTIAL",
        "PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONHOME", "PYTHONINSPECT",
        "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "BASH_ENV", "LD_PRELOAD", "NODE_OPTIONS",
    )
    for name in parent_names:
        monkeypatch.setenv(name, "synthetic-parent-value")
    test.write_text(
        "import os\nfrom pathlib import Path\n\ndef test_feature():\n"
        f"    assert not set({parent_names!r}) & os.environ.keys()\n"
        "    assert Path(os.environ['HOME']).is_dir()\n"
        "    assert Path(os.environ['XDG_CONFIG_HOME']).is_dir()\n"
        "    assert Path(os.environ['HOME']).parent == Path(os.environ['TMPDIR']).parent\n",
        encoding="utf-8",
    )
    (repo / "src" / "sitecustomize.py").write_text(
        "raise RuntimeError('candidate startup hook must not execute')\n", encoding="utf-8"
    )

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)

    assert result == {"test_feature::test_feature": "passed"}


def test_given_local_tool_paths_when_environment_is_built_then_paths_survive_and_owned_home_is_removed(
    monkeypatch, tmp_path, measure_module
):
    from evaluation_env import evaluation_environment

    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("LD_LIBRARY_PATH", str(tmp_path / "libraries"))

    with evaluation_environment() as env:
        home = Path(env["HOME"])
        assert env["PATH"].split(os.pathsep)[-1] == str(tmp_path)
        assert env["LD_LIBRARY_PATH"] == str(tmp_path / "libraries")
        assert home.is_dir()

    assert not home.exists()


@pytest.mark.parametrize("returncode", [2, 3, 4, 5, -9])
def test_given_runner_process_failure_when_hidden_tests_run_then_measurement_fails_explicitly(
    hidden_candidate, measure_module, monkeypatch, runner, returncode
):
    repo, suite, _ = hidden_candidate
    monkeypatch.setattr(
        measure_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, "", "synthetic failure"),
    )

    with pytest.raises(RuntimeError, match="exited with code"):
        measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)


@pytest.mark.parametrize("failure", [OSError("synthetic spawn failure"), subprocess.TimeoutExpired("pytest", 1)])
def test_given_spawn_failure_or_timeout_when_hidden_tests_run_then_measurement_fails_explicitly(
    hidden_candidate, measure_module, monkeypatch, runner, failure
):
    repo, suite, _ = hidden_candidate

    def fail(command, **kwargs):
        raise failure

    monkeypatch.setattr(measure_module.subprocess, "run", fail)

    with pytest.raises(RuntimeError, match="subprocess failed"):
        measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)


@pytest.mark.parametrize("report", [None, "not XML", "<unrelated />", "<testsuites />"])
def test_given_missing_or_invalid_junit_when_hidden_tests_run_then_measurement_fails_explicitly(
    hidden_candidate, measure_module, monkeypatch, report
):
    repo, suite, _ = hidden_candidate

    def fake_run(command, **kwargs):
        if report is not None:
            path = next(argument.split("=", 1)[1] for argument in command if argument.startswith("--junit-xml="))
            Path(path).write_text(report, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(measure_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="report|results"):
        measure_module.run_hidden(str(repo), str(suite), ["f1"], "pytest")


@pytest.mark.parametrize("report", [None, "", "[]", "{}", '{"tests": {}}', '{"tests": {"x": "passed"}}'])
def test_given_missing_or_invalid_json_when_hidden_tests_run_then_measurement_fails_explicitly(
    hidden_candidate, measure_module, monkeypatch, report
):
    repo, suite, _ = hidden_candidate

    def fake_run(command, **kwargs):
        if report is not None:
            Path(command[command.index("--json") + 1]).write_text(report, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(measure_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="report|results|identity"):
        measure_module.run_hidden(str(repo), str(suite), ["f1"], "stdlib")


def test_given_empty_later_hidden_contribution_when_evaluating_then_prior_tests_do_not_hide_it(
    hidden_candidate, measure_module, runner
):
    repo, suite, _ = hidden_candidate
    hidden = suite / "features" / "f2" / "hidden"
    hidden.mkdir(parents=True)
    (hidden / "test_empty.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="f2: no discovered hidden tests"):
        measure_module.run_hidden(str(repo), str(suite), ["f1", "f2"], runner)


@pytest.mark.parametrize("decorator", ["@unittest.skip('x')", "@unittest.expectedFailure"])
def test_given_skipped_unittest_when_stdlib_hidden_tests_run_then_not_recorded_as_passed(
    hidden_candidate, measure_module, decorator
):
    repo, suite, test = hidden_candidate
    test.write_text(
        "import unittest\n\nclass T(unittest.TestCase):\n"
        f"    {decorator}\n    def test_it(self):\n        self.fail('never')\n",
        encoding="utf-8",
    )

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], "stdlib")

    assert result == {"test_feature::T::test_it": "skipped"}


@pytest.mark.parametrize("missing_implementation", [False, True])
def test_given_inherited_tests_when_hidden_tests_run_then_denominator_matches_execution(
    hidden_candidate, measure_module, runner, missing_implementation
):
    repo, suite, test = hidden_candidate
    test.write_text(
        "import unittest\n"
        + ("import missing_implementation\n" if missing_implementation else "")
        + "\nclass SharedMixin:\n"
        "    def test_mixin(self):\n        assert True\n"
        "\nclass BaseCase(unittest.TestCase):\n"
        "    def test_base(self):\n        assert True\n"
        "\nclass TestDerived(BaseCase, SharedMixin):\n"
        "    def test_own(self):\n        assert True\n"
        "    def test_base(self):\n        assert True\n"
        "\nclass LeafCase(TestDerived):\n    pass\n",
        encoding="utf-8",
    )
    expected = {
        "test_feature::BaseCase::test_base",
        *(f"test_feature::{name}::{method}" for name in ("TestDerived", "LeafCase")
          for method in ("test_base", "test_mixin", "test_own")),
    }
    discovered = measure_module.expected_tests([str(test)])
    assert set(discovered) == expected
    assert len(discovered) == len(set(discovered))
    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)

    outcomes = {identity: "error" if missing_implementation else "passed" for identity in expected}
    assert result == outcomes


@pytest.fixture
def validator_module(monkeypatch):
    monkeypatch.syspath_prepend(str(KIT_ROOT / "harness"))
    return importlib.import_module("validate_suite")


@pytest.fixture
def suite_candidate(tmp_path):
    suite = tmp_path / "suite"
    data = {
        "features": [{"id": "f1", "status": "ready"}, {"id": "f2", "status": "ready"}],
        "change_request": {"id": "cr1", "status": "ready"},
    }
    for index, item_id in enumerate(("f1", "f2", "cr1"), 1):
        package = suite / "reference" / item_id / "workbench"
        package.mkdir(parents=True)
        package.joinpath("__init__.py").write_text(
            "FIRST = 1\n" + ("SECOND = 2\n" if index >= 2 else "") + ("CHANGED = 3\n" if index == 3 else ""),
            encoding="utf-8",
        )
        base = suite / ("features" if item_id != "cr1" else "") / item_id
        field = ("FIRST", "SECOND", "CHANGED")[index - 1]
        for audience in ("examples", "hidden"):
            folder = base / audience
            folder.mkdir(parents=True)
            text = f"def test_{item_id}_{audience}():\n    from workbench import {field}\n    assert {field} == {index}\n"
            if item_id == "f2" and audience == "hidden":
                text += "\ndef test_prior_edge_case():\n    assert 1 == 1\n"
            folder.joinpath(f"test_{item_id}_{audience}.py").write_text(text, encoding="utf-8")
    suite.joinpath("suite.json").write_text(json.dumps(data), encoding="utf-8")
    return suite, data


def test_given_complete_suite_and_valid_prior_edge_case_when_validating_then_cr1_and_features_pass(
    suite_candidate, validator_module, monkeypatch, capsys
):
    suite, _ = suite_candidate
    monkeypatch.setattr(sys, "argv", ["validate_suite.py", str(suite)])

    with pytest.raises(SystemExit) as outcome:
        validator_module.main()

    output = capsys.readouterr().out
    assert outcome.value.code == 0
    assert "cr1: 7/7 tests" in output
    assert "1/2 new hidden tests already pass" in output
    assert "coverage diagnostic only" in output


@pytest.mark.parametrize("item_id", ["f1", "f2", "cr1"])
@pytest.mark.parametrize("audience", ["examples", "hidden"])
@pytest.mark.parametrize("empty_kind", ["missing", "no_functions", "undiscovered_name"])
def test_given_empty_individual_contribution_when_full_suite_is_validated_then_prior_tests_cannot_hide_it(
    suite_candidate, validator_module, monkeypatch, capsys, item_id, audience, empty_kind
):
    suite, _ = suite_candidate
    base = suite / ("features" if item_id != "cr1" else "") / item_id / audience
    test = base / f"test_{item_id}_{audience}.py"
    if empty_kind == "missing":
        test.unlink()
    elif empty_kind == "no_functions":
        test.write_text("VALUE = 1\n", encoding="utf-8")
    else:
        test.rename(base / "support.py")
    monkeypatch.setattr(sys, "argv", ["validate_suite.py", str(suite)])

    with pytest.raises(SystemExit) as outcome:
        validator_module.main()

    output = capsys.readouterr().out
    label = "visible" if audience == "examples" else "hidden"
    assert outcome.value.code == 1
    assert f"{item_id}: no discovered {label} tests" in output
    assert "[OK]" not in output


@pytest.mark.parametrize("item_id", ["f1", "f2", "cr1"])
@pytest.mark.parametrize("status", ["draft", None])
def test_given_unready_item_when_full_suite_is_validated_then_validation_fails(
    suite_candidate, validator_module, monkeypatch, capsys, item_id, status
):
    suite, data = suite_candidate
    items = data["features"] + [data["change_request"]]
    next(item for item in items if item["id"] == item_id)["status"] = status
    suite.joinpath("suite.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validate_suite.py", str(suite)])

    with pytest.raises(SystemExit) as outcome:
        validator_module.main()

    assert outcome.value.code == 1
    assert f"{item_id}: not ready" in capsys.readouterr().out


@pytest.mark.parametrize("item_id", ["f1", "f2", "cr1"])
def test_given_missing_reference_when_full_suite_is_validated_then_validation_fails(
    suite_candidate, validator_module, monkeypatch, capsys, item_id
):
    suite, _ = suite_candidate
    reference = suite / "reference" / item_id / "workbench"
    reference.rename(reference.with_name("not_the_reference"))
    monkeypatch.setattr(sys, "argv", ["validate_suite.py", str(suite)])

    with pytest.raises(SystemExit) as outcome:
        validator_module.main()

    assert outcome.value.code == 1
    assert f"{item_id}: reference package is missing" in capsys.readouterr().out


def test_given_no_features_when_full_suite_is_validated_then_validation_fails(
    suite_candidate, validator_module, monkeypatch, capsys
):
    suite, data = suite_candidate
    data["features"] = []
    suite.joinpath("suite.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validate_suite.py", str(suite)])

    with pytest.raises(SystemExit) as outcome:
        validator_module.main()

    assert outcome.value.code == 1
    assert "requires features" in capsys.readouterr().out


def test_given_no_discovered_tests_when_reference_subprocess_is_requested_then_it_is_rejected(
    validator_module
):
    with pytest.raises(ValueError, match="No discovered tests"):
        validator_module.run_isolated([], None)


def test_given_parent_credentials_when_reference_tests_run_then_the_child_environment_is_minimal(
    suite_candidate, validator_module, monkeypatch
):
    suite, _ = suite_candidate
    test = suite / "features" / "f1" / "hidden" / "test_f1_hidden.py"
    test.write_text(
        "import os\nfrom pathlib import Path\n\ndef test_f1_hidden():\n"
        "    assert 'GITHUB_TOKEN' not in os.environ\n"
        "    assert 'PYTHONPATH' not in os.environ\n"
        "    assert Path(os.environ['HOME']).is_dir()\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-parent-credential")
    monkeypatch.setenv("PYTHONPATH", "synthetic-parent-startup-path")

    result = validator_module.run_isolated([str(test)], str(suite / "reference" / "f1" / "workbench"))

    assert result == {"test_f1_hidden::test_f1_hidden": "passed"}


def test_given_inherited_tests_when_reference_is_validated_then_all_identities_pass(
    suite_candidate, validator_module
):
    suite, _ = suite_candidate
    test = suite / "features" / "f1" / "hidden" / "test_f1_hidden.py"
    test.write_text(
        "import unittest\nfrom workbench import FIRST\n"
        "\nclass BaseCase(unittest.TestCase):\n"
        "    def test_first(self):\n        self.assertEqual(FIRST, 1)\n"
        "\nclass TestDerived(BaseCase):\n    pass\n"
        "\nclass LeafCase(TestDerived):\n    pass\n",
        encoding="utf-8",
    )

    result = validator_module.run_isolated([str(test)], str(suite / "reference" / "f1" / "workbench"))

    assert result == {f"test_f1_hidden::{name}::test_first": "passed"
                      for name in ("BaseCase", "TestDerived", "LeafCase")}


@pytest.mark.parametrize("report", [None, "not JSON", "[]", '{"tests": {}}'])
def test_given_broken_reference_report_when_validating_then_failure_is_explicit(
    suite_candidate, validator_module, monkeypatch, report
):
    suite, _ = suite_candidate
    test = suite / "features" / "f1" / "hidden" / "test_f1_hidden.py"

    def fake_run(command, **kwargs):
        if report is not None:
            Path(command[command.index("--json") + 1]).write_text(report, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(validator_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="report|results"):
        validator_module.run_isolated([str(test)], str(suite / "reference" / "f1" / "workbench"))


@pytest.mark.parametrize("returncode", [2, -9])
def test_given_reference_process_failure_when_validating_then_failure_is_explicit(
    suite_candidate, validator_module, monkeypatch, returncode
):
    suite, _ = suite_candidate
    test = suite / "features" / "f1" / "hidden" / "test_f1_hidden.py"
    monkeypatch.setattr(
        validator_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, "", ""),
    )

    with pytest.raises(RuntimeError, match="exited with code"):
        validator_module.run_isolated([str(test)], str(suite / "reference" / "f1" / "workbench"))


def test_given_credentials_and_arbitrary_agent_environment_when_green_checks_run_then_only_evaluation_env_is_used(
    tmp_path, monkeypatch, measure_module
):
    runner_module = importlib.import_module("runner")
    run = runner_module.Run.__new__(runner_module.Run)
    run.repo = str(tmp_path)
    run.env_extra = {"PATH": "/not/a/tool/path", "GITHUB_TOKEN": "synthetic-agent-token", "AGENT_EXTRA": "synthetic"}
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "synthetic-parent-token")
    script = (
        "import os, sys; from pathlib import Path; "
        "assert not {'COPILOT_GITHUB_TOKEN', 'GITHUB_TOKEN', 'AGENT_EXTRA', 'PYTHONPATH'} & os.environ.keys(); "
        f"assert sys.prefix == {sys.prefix!r}; "
        "assert Path(os.environ['HOME']).is_dir()"
    )
    tmp_path.joinpath("Makefile").write_text(
        "test:\n\t@python3 -I -B -c " + shlex.quote(script) + "\n", encoding="utf-8"
    )

    result = run.is_green()

    assert result is True
    assert run.env()["COPILOT_GITHUB_TOKEN"] == "synthetic-parent-token"
    assert run.env()["GITHUB_TOKEN"] == "synthetic-agent-token"


@pytest.fixture
def metrics_module(monkeypatch):
    monkeypatch.syspath_prepend(str(KIT_ROOT / "skeleton" / "tools"))
    return importlib.import_module("metrics_core")


def test_given_empty_ruff_stdout_when_lint_is_measured_then_measurement_fails(
    tmp_path, metrics_module, monkeypatch
):
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: "/synthetic/ruff")
    monkeypatch.setattr(
        metrics_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )

    with pytest.raises(RuntimeError, match="JSON"):
        metrics_module.lint(str(tmp_path), "ruff")


@pytest.mark.parametrize("stdout", [
    "not JSON", "null", "{}", '"not a list"', "[1]", "[null]", "[{}]",
    '[{"code": null}]', '[{"code": "F401"}]',
    '[{"code": "F401", "message": "unused", "filename": "source.py", "location": null}]',
    '[{"code": "F401", "message": "unused", "filename": "source.py", "location": {"row": true, "column": 1}}]',
])
def test_given_invalid_ruff_json_when_lint_is_measured_then_measurement_fails(
    tmp_path, metrics_module, monkeypatch, stdout
):
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: "/synthetic/ruff")
    monkeypatch.setattr(
        metrics_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout, ""),
    )

    with pytest.raises(RuntimeError, match="JSON"):
        metrics_module.lint(str(tmp_path), "ruff")


@pytest.mark.parametrize("returncode", [1, 2, 137, -9])
def test_given_ruff_failure_even_with_json_when_lint_is_measured_then_measurement_fails(
    tmp_path, metrics_module, monkeypatch, returncode
):
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: "/synthetic/ruff")
    monkeypatch.setattr(
        metrics_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, "[]", "synthetic failure"),
    )

    with pytest.raises(RuntimeError, match="ruff exited with code"):
        metrics_module.lint(str(tmp_path), "ruff")


@pytest.mark.parametrize("backend", ["ruff", "auto"])
def test_given_missing_ruff_when_lint_is_requested_then_measurement_fails(
    tmp_path, metrics_module, monkeypatch, backend
):
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: None)

    with pytest.raises(RuntimeError, match="ruff requested but not on PATH"):
        metrics_module.lint(str(tmp_path), backend)


def test_given_explicit_no_lint_backend_when_measuring_then_missing_lint_remains_unknown_not_zero(
    tmp_path, metrics_module, monkeypatch
):
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: None)

    result = metrics_module.lint(str(tmp_path), "none")

    assert result == {"backend": "none", "warnings": None, "by_code": {}}


def test_given_normal_ruff_findings_with_exit_zero_when_measuring_then_findings_are_counted(
    tmp_path, metrics_module, monkeypatch
):
    diagnostic = {
        "code": "F401", "message": "unused import", "filename": "source.py", "location": {"row": 1, "column": 1},
    }
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: "/synthetic/ruff")

    def fake_run(command, **kwargs):
        assert "--exit-zero" in command
        assert "--isolated" in command
        return subprocess.CompletedProcess(command, 0, json.dumps([diagnostic, diagnostic]), "")

    monkeypatch.setattr(metrics_module.subprocess, "run", fake_run)

    result = metrics_module.lint(str(tmp_path), "ruff")

    assert result == {"backend": "ruff", "warnings": 2, "by_code": {"F401": 2}}


@pytest.mark.parametrize("source, expected", [("VALUE = 1\n", 0), ("import os\n", 1)])
def test_given_real_ruff_on_synthetic_source_when_measuring_then_clean_and_normal_findings_are_valid(
    tmp_path, metrics_module, monkeypatch, source, expected
):
    tmp_path.joinpath("source.py").write_text(source, encoding="utf-8")
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", os.defpath))

    result = metrics_module.lint(str(tmp_path), "ruff")

    assert result["backend"] == "ruff"
    assert result["warnings"] == expected


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_given_authored_docs_and_generated_reports_when_measuring_each_arm_then_only_generated_tree_is_excluded(
    tmp_path, metrics_module, arm
):
    repo = tmp_path / arm
    repo.joinpath("src").mkdir(parents=True)
    repo.joinpath("src", "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    documents = {
        "README.md": "one two",
        "DESIGN.md": "design three words",
        "REVIEW.md": "review four words here",
        "docs/reports/notes.md": "kept two",
        "reports/quality.md": "generated " * 100,
        "reports/nested/other.md": "generated " * 100,
        ".hidden/ignored.md": "hidden " * 100,
    }
    for name, text in documents.items():
        document = repo / name
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(text, encoding="utf-8")

    result = metrics_module.measure(str(repo), "internal", "internal", "none")

    assert result["md_words"] == 11


def test_given_invalid_document_encoding_when_measuring_then_file_parse_failure_is_explicit(
    tmp_path, metrics_module
):
    tmp_path.joinpath("src").mkdir()
    tmp_path.joinpath("DESIGN.md").write_bytes(b"invalid UTF-8: \xff")

    with pytest.raises(UnicodeDecodeError):
        metrics_module.measure(str(tmp_path), "internal", "internal", "none")


def test_given_invalid_python_when_measuring_internal_complexity_then_failure_is_not_reported_as_no_functions(
    tmp_path, metrics_module
):
    source = tmp_path / "source.py"
    source.write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid Python source"):
        metrics_module.complexity([str(source)], "internal")


def test_given_failed_jscpd_with_a_report_when_measuring_then_failure_is_not_accepted(
    tmp_path, metrics_module, monkeypatch
):
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: "/synthetic/jscpd")

    def fake_run(command, **kwargs):
        report = Path(command[command.index("--output") + 1]) / "jscpd-report.json"
        report.write_text(
            '{"statistics": {"total": {"duplicatedLines": 0, "lines": 1, "percentage": 0}}, "duplicates": []}',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 2, "", "synthetic failure")

    monkeypatch.setattr(metrics_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="jscpd exited with code"):
        metrics_module.duplication(str(tmp_path), [], "jscpd")


def test_given_successful_jscpd_report_when_measuring_then_existing_percentage_and_counts_are_preserved(
    tmp_path, metrics_module, monkeypatch
):
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: "/synthetic/jscpd")

    def fake_run(command, **kwargs):
        report = Path(command[command.index("--output") + 1]) / "jscpd-report.json"
        report.write_text(
            '{"statistics": {"total": {"duplicatedLines": 4, "lines": 20, "percentage": 20}}, "duplicates": []}',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(metrics_module.subprocess, "run", fake_run)

    result = metrics_module.duplication(str(tmp_path), [], "jscpd")

    assert result == {"backend": "jscpd", "duplicated_lines": 4, "lines": 20, "percentage": 20, "blocks": []}


def test_given_invalid_tests_when_counting_then_they_are_not_silently_reported_as_zero(
    tmp_path, measure_module
):
    tests = tmp_path / "tests"
    tests.mkdir()
    tests.joinpath("test_invalid.py").write_text("def test_broken(:\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid Python tests"):
        measure_module.test_counts(str(tmp_path))


@pytest.mark.parametrize("returncode, stdout", [(128, ""), (0, "malformed numstat")])
def test_given_failed_or_malformed_git_diff_when_measuring_then_empty_diff_is_not_assumed(
    tmp_path, measure_module, monkeypatch, returncode, stdout
):
    monkeypatch.setattr(
        measure_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, stdout, ""),
    )

    with pytest.raises(RuntimeError, match="git diff"):
        measure_module.diff_stats(str(tmp_path), "synthetic-reference")


@pytest.fixture
def measurement_command(tmp_path, measure_module, metrics_module, monkeypatch):
    output = tmp_path / "measurement.json"
    monkeypatch.setattr(sys, "argv", [
        "measure.py", "--repo", str(tmp_path), "--suite", str(tmp_path), "--k", "1", "--out", str(output),
    ])
    monkeypatch.setattr(measure_module, "suite_items", lambda *args: ["f1"])
    monkeypatch.setattr(measure_module, "run_hidden", lambda *args: {"test_feature::test_feature": "passed"})
    monkeypatch.setattr(metrics_module, "measure", lambda *args: {"mean_ccn": 1, "dup_pct": 0, "lint_warnings": 0})
    monkeypatch.setattr(measure_module, "integrity", lambda *args: {"modified": [], "missing": []})
    monkeypatch.setattr(measure_module, "test_counts", lambda *args: {"tests": 1, "asserts": 1})
    monkeypatch.setattr(measure_module, "diff_stats", lambda *args: None)
    return output


def test_given_local_evaluation_when_measurement_is_recorded_then_absence_of_os_and_network_isolation_is_explicit(
    measurement_command, measure_module, monkeypatch
):
    monkeypatch.setattr(
        measure_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "a" * 40, ""),
    )

    measure_module.main()

    result = json.loads(measurement_command.read_text(encoding="utf-8"))
    assert result["evaluation"] == {
        "execution": "local_subprocess", "environment": "allowlisted_subprocesses",
        "os_isolated": False, "network_isolated": False,
    }


def test_given_direct_measure_cli_when_metric_and_git_children_run_then_metadata_describes_the_actual_boundary(
    tmp_path, hidden_candidate, measure_module, metrics_module, monkeypatch, synthetic_evaluation_parent
):
    repo, suite, _ = hidden_candidate
    repo.joinpath("src", "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    suite.joinpath("suite.json").write_text(json.dumps({"features": [{"id": "f1"}]}), encoding="utf-8")
    output = tmp_path / "direct-measurement.json"
    monkeypatch.setattr(sys, "argv", [
        "measure.py", "--repo", str(repo), "--suite", str(suite), "--k", "1", "--out", str(output),
        "--runner", "stdlib", "--complexity", "internal", "--duplication", "jscpd", "--lint", "ruff",
        "--prev-ref", "synthetic-reference",
    ])
    monkeypatch.setattr(measure_module, "run_hidden", lambda *args: {"test_feature::test_feature": "passed"})
    monkeypatch.setattr(metrics_module.shutil, "which", lambda name, **kwargs: f"/synthetic/{name}")
    owned_paths = []
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        owned_paths.extend(assert_minimal_evaluation_environment(kwargs.get("env"), synthetic_evaluation_parent))
        if command[0] == "/synthetic/jscpd":
            report = Path(command[command.index("--output") + 1]) / "jscpd-report.json"
            report.write_text(json.dumps({
                "statistics": {"total": {"duplicatedLines": 0, "lines": 1, "percentage": 0}}, "duplicates": [],
            }), encoding="utf-8")
            stdout = ""
        elif command[0] == "/synthetic/ruff":
            stdout = "[]"
        elif command[:4] == ["git", "-c", f"safe.directory={repo}", "rev-parse"]:
            stdout = "a" * 40
        else:
            assert command[:4] == ["git", "-c", f"safe.directory={repo}", "diff"]
            stdout = "1\t0\tsrc/source.py\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(measure_module.subprocess, "run", fake_run)

    measure_module.main()

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["evaluation"] == {
        "execution": "local_subprocess", "environment": "allowlisted_subprocesses",
        "os_isolated": False, "network_isolated": False,
    }
    assert result["metrics"]["backends"] == {"complexity": "internal", "duplication": "jscpd", "lint": "ruff"}
    assert result["hidden_passed"] == result["hidden_total"] == 1
    assert result["diff"]["src"] == {"added": 1, "removed": 0}
    assert len(commands) == 4
    assert all(not path.exists() for path in owned_paths)
    assert os.environ["COPILOT_GITHUB_TOKEN"] == "synthetic-review-marker"


@pytest.mark.parametrize("returncode, stdout", [(128, ""), (0, "")])
def test_given_unavailable_git_head_when_measuring_then_failure_is_explicit(
    measurement_command, measure_module, monkeypatch, returncode, stdout
):
    monkeypatch.setattr(
        measure_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, returncode, stdout, ""),
    )

    with pytest.raises(RuntimeError, match="valid HEAD"):
        measure_module.main()

    assert not measurement_command.exists()


@pytest.mark.parametrize("classname, name", [
    ("unrelated.test_feature", "test_feature"),
    ("test_feature", "other_test"),
    ("test_feature", "TestWrong::<import>"),
])
def test_given_lookalike_junit_identity_when_evaluating_then_it_cannot_replace_an_expected_test(
    hidden_candidate, measure_module, monkeypatch, classname, name
):
    repo, suite, _ = hidden_candidate

    def fake_run(command, **kwargs):
        path = next(argument.split("=", 1)[1] for argument in command if argument.startswith("--junit-xml="))
        root = ET.Element("testsuites")
        test_suite = ET.SubElement(root, "testsuite")
        ET.SubElement(test_suite, "testcase", classname=classname, name=name)
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(measure_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="unexpected test identity"):
        measure_module.run_hidden(str(repo), str(suite), ["f1"], "pytest")


@pytest.mark.parametrize("report, returncode", [
    ('<testcase classname="test_feature" name="test_feature" />' * 2, 0),
    ('<testcase classname="test_feature" name="test_feature"><failure /></testcase>', 0),
    ('<testcase classname="test_feature" name="test_feature" />', 1),
])
def test_given_duplicate_or_contradictory_junit_when_evaluating_then_measurement_fails(
    hidden_candidate, measure_module, monkeypatch, report, returncode
):
    repo, suite, _ = hidden_candidate

    def fake_run(command, **kwargs):
        path = next(argument.split("=", 1)[1] for argument in command if argument.startswith("--junit-xml="))
        Path(path).write_text(f"<testsuites><testsuite>{report}</testsuite></testsuites>", encoding="utf-8")
        return subprocess.CompletedProcess(command, returncode, "", "")

    monkeypatch.setattr(measure_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="duplicate test identity|exit status disagrees"):
        measure_module.run_hidden(str(repo), str(suite), ["f1"], "pytest")


def test_given_partially_run_module_when_evaluating_then_only_unrun_test_is_an_error(
    hidden_candidate, measure_module, monkeypatch
):
    repo, suite, test = hidden_candidate
    test.write_text("def test_first():\n    assert True\n\ndef test_unrun():\n    assert True\n", encoding="utf-8")

    def fake_run(command, **kwargs):
        path = next(argument.split("=", 1)[1] for argument in command if argument.startswith("--junit-xml="))
        Path(path).write_text(
            '<testsuites><testsuite><testcase classname="test_feature" name="test_first" /></testsuite></testsuites>',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(measure_module.subprocess, "run", fake_run)

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], "pytest")

    assert result == {"test_feature::test_first": "passed", "test_feature::test_unrun": "error"}


def test_given_pytest_class_when_evaluating_then_class_and_method_identity_are_preserved(
    hidden_candidate, measure_module
):
    repo, suite, test = hidden_candidate
    test.write_text("class TestFeature:\n    def test_feature(self):\n        assert True\n", encoding="utf-8")

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], "pytest")

    assert result == {"test_feature::TestFeature::test_feature": "passed"}


def test_given_inexact_collection_marker_when_validating_results_then_it_is_rejected(measure_module):
    with pytest.raises(RuntimeError, match="unexpected test identity"):
        measure_module.validated_results(
            {"test_feature::wrong::<import>": "error"}, ["test_feature::test_feature"]
        )


def test_given_failed_hidden_process_when_evaluating_then_owned_home_and_test_copy_are_cleaned(
    hidden_candidate, measure_module, monkeypatch
):
    repo, suite, _ = hidden_candidate
    owned_paths = []

    def fake_run(command, **kwargs):
        owned_paths.extend([Path(kwargs["cwd"]), Path(kwargs["env"]["HOME"]).parent])
        return subprocess.CompletedProcess(command, 2, "", "")

    monkeypatch.setattr(measure_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="exited with code"):
        measure_module.run_hidden(str(repo), str(suite), ["f1"], "pytest")

    assert owned_paths
    assert all(not path.exists() for path in owned_paths)


def test_given_test_function_returning_non_outcome_when_stdlib_runs_then_report_is_written(
    hidden_candidate, measure_module
):
    repo, suite, test = hidden_candidate
    test.write_text("def test_it():\n    return True\n", encoding="utf-8")

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], "stdlib")

    assert result == {"test_feature::test_it": "passed"}


@pytest.mark.parametrize("exception", ["ValueError", "TypeError", "ProductError"])
@pytest.mark.parametrize("style", ["function", "unittest", "import"])
def test_candidate_source_exceptions_are_nonpasses_with_raw_private_evidence(
    hidden_candidate, measure_module, runner, exception, style
):
    repo, suite, test = hidden_candidate
    (repo / "src" / "product.py").write_text(
        "class ProductError(Exception):\n    pass\n\n"
        + (f"raise {exception}('private candidate diagnostic')\n" if style == "import" else
           f"def exercise():\n    raise {exception}('private candidate diagnostic')\n"), encoding="utf-8"
    )
    if style != "unittest":
        code = "from product import exercise\n\ndef test_feature():\n    exercise()\n"
        identity = "test_feature::test_feature"
    else:
        code = ("import unittest\nfrom product import exercise\n\nclass TestFeature(unittest.TestCase):\n"
                "    def test_feature(self):\n        exercise()\n")
        identity = "test_feature::TestFeature::test_feature"
    test.write_text(code, encoding="utf-8")

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)

    assert result == {identity: "failed"}
    evidence = result.provenance[identity]
    assert evidence["raw_outcome"] == ("error" if runner == "stdlib" or style == "import" else "failed")
    assert evidence["attribution"] == "candidate_exception"
    assert evidence["candidate"] == {"module": "product", "source": str(repo / "src" / "product.py")}
    assert "private candidate diagnostic" in evidence["diagnostic"]
    assert evidence["frames"][-1]["file"] == str(repo / "src" / "product.py")


@pytest.mark.parametrize("product, test_body", [
    ("def exercise():\n    raise OSError('disk')\n", "exercise()"),
    ("def exercise():\n    raise MemoryError('memory')\n", "exercise()"),
    ("def exercise():\n    raise TimeoutError('timeout')\n", "exercise()"),
    ("def exercise():\n    raise RuntimeError('unclassified')\n", "exercise()"),
    ("def exercise():\n    import missing_external_dependency\n", "exercise()"),
    ("def exercise():\n    return True\n", "raise ValueError('oracle bug')"),
    ("def exercise():\n    return True\n", "missing_test_helper()"),
    ("def exercise():\n    return True\n", "import missing_test_dependency"),
    ("def exercise():\n    return True\n", "from product import MisspelledHelper"),
    ("def exercise():\n    return True\n",
     "compile('def broken(:', __import__('product').__file__, 'exec')"),
    (("def exercise():\n    try:\n        import missing_external_dependency\n"
      "    except ImportError as error:\n        raise ValueError('wrapped') from error\n"), "exercise()"),
])
def test_unattributed_and_infrastructure_exceptions_remain_unknown(
    hidden_candidate, measure_module, runner, product, test_body
):
    repo, suite, test = hidden_candidate
    (repo / "src" / "product.py").write_text(product, encoding="utf-8")
    test.write_text(f"from product import exercise\n\ndef test_feature():\n    {test_body}\n", encoding="utf-8")

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)

    assert result == {"test_feature::test_feature": "error"}
    evidence = result.provenance["test_feature::test_feature"]
    assert evidence["attribution"] == "unknown"
    assert evidence["raw_outcome"] == ("error" if runner == "stdlib" else "failed")
    assert evidence["diagnostic"]


@pytest.mark.parametrize("fault, expected", [
    ("missing_export", "failed"), ("missing_method", "failed"), ("missing_package", "failed"),
    ("missing_field", "failed"), ("module_export", "failed"),
    ("typo_export", "error"), ("typo_method", "error"), ("external_dependency", "error"),
    ("collection_assertion", "error"), ("dynamic_typo", "error"),
])
def test_only_declared_missing_candidate_apis_are_nonpasses(
    hidden_candidate, measure_module, runner, fault, expected
):
    repo, suite, test = hidden_candidate
    suite.joinpath("suite.json").write_text(json.dumps({
        "package": "workbench",
        "features": [{"id": "f1", "api": [
            "Workbench() keeps everything in memory.", "exercise() -> bool.",
            "OnHold importable from workbench.", "open_case() -> Case with attributes id, stage.",
        ]}],
    }), encoding="utf-8")
    package = repo / "src" / "workbench.py"
    package.write_text("class Workbench:\n    pass\n", encoding="utf-8")
    if fault == "missing_package":
        package.unlink()
    elif fault == "external_dependency":
        package.write_text("import missing_external_dependency\nclass Workbench:\n    pass\n", encoding="utf-8")
    elif fault == "missing_field":
        package.write_text("class Case:\n    pass\n", encoding="utf-8")
    elif fault == "dynamic_typo":
        package.write_text("class Workbench:\n    def __getattr__(self, name):\n        raise AttributeError(name)\n",
                           encoding="utf-8")
    code = "from workbench import Workbench\n\ndef test_feature():\n    assert True\n"
    if fault in ("missing_export", "typo_export"):
        name = "OnHold" if fault == "missing_export" else "TypoHelper"
        code = f"from workbench import {name}\n\ndef test_feature():\n    assert True\n"
    elif fault in ("missing_method", "typo_method"):
        name = "exercise" if fault == "missing_method" else "typo_helper"
        code = f"from workbench import Workbench\n\ndef test_feature():\n    Workbench().{name}()\n"
    elif fault == "missing_field":
        code = "from workbench import Case\n\ndef test_feature():\n    Case().stage\n"
    elif fault == "module_export":
        code = "import workbench\n\ndef test_feature():\n    workbench.OnHold\n"
    elif fault == "collection_assertion":
        code = "assert False, 'broken collection helper'\n\ndef test_feature():\n    assert True\n"
    elif fault == "dynamic_typo":
        code = "from workbench import Workbench\n\ndef test_feature():\n    Workbench().typo_helper()\n"
    test.write_text(code, encoding="utf-8")

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)

    assert result == {"test_feature::test_feature": expected}
    evidence = result.provenance["test_feature::test_feature"]
    assert evidence["diagnostic"] and evidence["raw_outcome"] in ("failed", "error")
    assert evidence["attribution"] == (
        "mandatory_api" if fault in ("missing_method", "missing_field", "module_export") else
        "mandatory_import" if expected == "failed" else "unknown"
    )


def test_missing_f5_export_does_not_hide_retained_f4_passes(tmp_path, measure_module, runner):
    import shutil

    suite = KIT_ROOT / "suites" / "s1-retrofit"
    repo = tmp_path / "candidate"
    shutil.copytree(suite / "reference" / "f04" / "workbench", repo / "src" / "workbench")

    result = measure_module.run_hidden(str(repo), str(suite), [f"f{k:02d}" for k in range(1, 6)], runner)

    prior = {key: value for key, value in result.items() if not key.startswith("test_f05_hidden::")}
    later = {key: value for key, value in result.items() if key.startswith("test_f05_hidden::")}
    assert len(prior) == 51 and set(prior.values()) == {"passed"}
    assert len(later) == 13 and set(later.values()) == {"failed"}
    assert all(result.provenance[key]["raw_outcome"] == "error" for key in later)
    assert all(result.provenance[key]["candidate"]["missing"] == "OnHold" for key in later)
    assert all("ImportError" in result.provenance[key]["diagnostic"] for key in later)


@pytest.mark.parametrize("origin", ["candidate", "test_helper"])
def test_syntax_error_requires_actual_candidate_loader_provenance(
    hidden_candidate, measure_module, runner, origin
):
    repo, suite, test = hidden_candidate
    folder = repo / "src" if origin == "candidate" else test.parent
    (folder / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    test.write_text("import broken\n\ndef test_feature():\n    assert True\n", encoding="utf-8")

    result = measure_module.run_hidden(str(repo), str(suite), ["f1"], runner)

    assert result == {"test_feature::test_feature": "failed" if origin == "candidate" else "error"}
    evidence = result.provenance["test_feature::test_feature"]
    assert evidence["raw_outcome"] == "error" and evidence["diagnostic"]
    assert evidence["attribution"] == ("candidate_syntax" if origin == "candidate" else "unknown")


def test_measurement_preserves_private_attribution_without_changing_dict_consumers(
    measurement_command, measure_module, monkeypatch
):
    provenance = {"test_feature::test_feature": {
        "raw_outcome": "error", "outcome": "failed", "attribution": "candidate_exception",
        "diagnostic": "synthetic private trace",
    }}
    monkeypatch.setattr(measure_module, "run_hidden", lambda *args: measure_module.HiddenResults(
        {"test_feature::test_feature": "failed"}, provenance
    ))
    monkeypatch.setattr(
        measure_module.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "a" * 40, ""),
    )

    measure_module.main()

    result = json.loads(measurement_command.read_text(encoding="utf-8"))
    assert result["hidden"] == {"test_feature::test_feature": "failed"}
    assert result["hidden_passed"] == 0 and result["hidden_total"] == 1
    assert result["hidden_provenance"] == provenance


@pytest.mark.parametrize(("original", "replacement", "omits_action"), [
    ('entry.get("seq"), entry.get("action"), entry.get("target")',
     'entry.get("seq"), entry.get("target")', True),
    ('hashlib.sha256(payload.encode("utf-8")).hexdigest()',
     'hashlib.sha512(payload.encode("utf-8")).hexdigest()[:64]', False),
], ids=["omitted-action", "non-sha256"])
def test_f10_oracle_rejects_nonconforming_audit_hashes(
    tmp_path, validator_module, original, replacement, omits_action
):
    suite = KIT_ROOT / "suites" / "s1-retrofit"
    source = (suite / "reference/cr1/workbench/__init__.py").read_text(encoding="utf-8")
    assert source.count(original) == 1
    package = tmp_path / "workbench"
    package.mkdir()
    (package / "__init__.py").write_text(source.replace(original, replacement), encoding="utf-8")
    feature = suite / "features/f10"
    tests = [str(feature / "examples/test_f10_audit.py"), str(feature / "hidden/test_f10_hidden.py")]

    outcomes = validator_module.run_isolated(tests, str(package))

    assert set(outcomes.values()) <= {"passed", "failed"}
    assert outcomes["test_f10_audit::test_f10_writes_are_chained_in_the_audit_trail"] == "failed"
    assert outcomes["test_f10_hidden::test_h10_entry_shape_and_chain"] == "failed"
    if omits_action:
        assert outcomes["test_f10_hidden::test_h10_changed_actor_or_hash_is_detected"] == "failed"
