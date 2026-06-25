from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from run import Run


def make_runner(tmp_path, tag="4.19.0.9", checkout_ref=None):
    driver = tmp_path / "driver repo"
    driver.mkdir()
    return Run(
        java_driver_git=driver,
        scylla_install_dir="",
        tag=tag,
        tests="",
        driver_type="scylla",
        scylla_version="2026.1.3",
        checkout_ref=checkout_ref,
    )


def test_3x_test_command_defaults_empty_selector_to_all_tests(tmp_path):
    runner = make_runner(tmp_path, tag="3.11.5.12")

    assert runner._test_command("") == [
        "mvn",
        "-B",
        "-pl",
        "driver-core",
        "-Dtest.groups=short,long",
        "-Dtest=*",
        "test",
    ]


def test_4x_test_command_keeps_selector_as_one_argv_entry(tmp_path):
    runner = make_runner(tmp_path)
    selector = "!BadIT#case,Good IT; echo unsafe"

    assert runner._test_command(selector) == [
        "mvn",
        "-B",
        "-pl",
        "integration-tests",
        "integration-test",
        f"-Dit.test={selector}",
    ]


def test_run_command_invokes_subprocess_without_shell(monkeypatch, tmp_path):
    runner = make_runner(tmp_path, checkout_ref="feature/ref; echo unsafe")
    captured = {}

    class FakeProcess:
        returncode = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def communicate(self):
            return None, ""

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    runner._run_command(["git", "checkout", runner._checkout_ref])

    assert captured["cmd"] == ["git", "checkout", "feature/ref; echo unsafe"]
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["cwd"] == tmp_path / "driver repo"
