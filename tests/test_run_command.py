from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import run as run_module
from run import Run


def make_runner(tmp_path, tag="4.19.0.9", checkout_ref=None, driver_type="scylla"):
    driver = tmp_path / "driver repo"
    driver.mkdir()
    return Run(
        java_driver_git=driver,
        scylla_install_dir="",
        tag=tag,
        tests="",
        driver_type=driver_type,
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


def test_3x_test_commands_include_isolated_profile_run(tmp_path):
    runner = make_runner(tmp_path, tag="3.11.5.12")

    assert runner._test_commands("") == [
        [
            "mvn",
            "-B",
            "-pl",
            "driver-core",
            "-Dtest.groups=short,long",
            "-Dtest=*",
            "test",
        ],
        [
            "mvn",
            "-B",
            "-pl",
            "driver-core",
            "-Pisolated",
            "test",
        ],
    ]


def test_3x_isolated_test_command_keeps_explicit_selector(tmp_path):
    runner = make_runner(tmp_path, tag="3.11.5.12")

    assert runner._isolated_test_command("ControlConnectionTest") == [
        "mvn",
        "-B",
        "-pl",
        "driver-core",
        "-Pisolated",
        "-Dtest=ControlConnectionTest",
        "test",
    ]


def test_3x_run_uses_all_tests_selector_when_no_tests_or_ignores(monkeypatch, tmp_path):
    runner = make_runner(tmp_path, tag="3.11.5.12")
    commands = []
    runner.__dict__["ignore_tests"] = set()

    monkeypatch.setattr(run_module, "__file__", str(tmp_path / "run.py"))
    monkeypatch.setattr(runner, "_apply_patch_files", lambda: None)
    monkeypatch.setattr(runner, "_run_command", lambda cmd: commands.append([str(arg) for arg in cmd]))

    runner.run()

    assert commands[-2:] == [
        [
            "mvn",
            "-B",
            "-pl",
            "driver-core",
            "-Dtest.groups=short,long",
            "-Dtest=*",
            "test",
            "-Dscylla.version=2026.1.3",
        ],
        [
            "mvn",
            "-B",
            "-pl",
            "driver-core",
            "-Pisolated",
            "test",
            "-Dscylla.version=2026.1.3",
        ],
    ]


def test_3x_run_still_executes_isolated_tests_after_regular_test_failure(monkeypatch, tmp_path):
    runner = make_runner(tmp_path, tag="3.11.5.12")
    commands = []
    runner.__dict__["ignore_tests"] = set()

    def fake_run_command(cmd):
        cmd = [str(arg) for arg in cmd]
        commands.append(cmd)
        if "-Dtest.groups=short,long" in cmd:
            raise AssertionError("regular tests failed")

    monkeypatch.setattr(run_module, "__file__", str(tmp_path / "run.py"))
    monkeypatch.setattr(runner, "_apply_patch_files", lambda: None)
    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    runner.run()

    assert commands[-1] == [
        "mvn",
        "-B",
        "-pl",
        "driver-core",
        "-Pisolated",
        "test",
        "-Dscylla.version=2026.1.3",
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


def test_apache_scylla_version_uses_release_prefix_for_ccm_download(monkeypatch, tmp_path):
    monkeypatch.delenv("SCYLLA_UNIFIED_PACKAGE", raising=False)
    runner = make_runner(tmp_path, tag="4.12.0", driver_type="apache")

    assert runner._scylla_version_for_test_command() == "release:2026.1.3"


def test_apache_scylla_version_uses_release_prefix_for_rc_ccm_download(monkeypatch, tmp_path):
    monkeypatch.delenv("SCYLLA_UNIFIED_PACKAGE", raising=False)
    runner = make_runner(tmp_path, tag="4.12.0", driver_type="apache")
    runner._scylla_version = "2026.1.0-rc1"

    assert runner._scylla_version_for_test_command() == "release:2026.1.0-rc1"


def test_apache_scylla_version_preserves_dev_version(monkeypatch, tmp_path):
    monkeypatch.delenv("SCYLLA_UNIFIED_PACKAGE", raising=False)
    runner = make_runner(tmp_path, tag="4.12.0", driver_type="apache")
    runner._scylla_version = "2026.2.0~dev"

    assert runner._scylla_version_for_test_command() == "2026.2.0~dev"


def test_apache_scylla_version_preserves_hyphenated_dev_version(monkeypatch, tmp_path):
    monkeypatch.delenv("SCYLLA_UNIFIED_PACKAGE", raising=False)
    runner = make_runner(tmp_path, tag="4.12.0", driver_type="apache")
    runner._scylla_version = "2026.2.0-dev"

    assert runner._scylla_version_for_test_command() == "2026.2.0-dev"


def test_apache_scylla_version_preserves_local_package_version(monkeypatch, tmp_path):
    monkeypatch.setenv("SCYLLA_UNIFIED_PACKAGE", "/tmp/scylla-unified.tar.gz")
    runner = make_runner(tmp_path, tag="4.12.0", driver_type="apache")

    assert runner._scylla_version_for_test_command() == "2026.1.3"


def test_apache_scylla_version_preserves_explicit_ccm_prefix(monkeypatch, tmp_path):
    monkeypatch.delenv("SCYLLA_UNIFIED_PACKAGE", raising=False)
    runner = make_runner(tmp_path, tag="4.12.0", driver_type="apache")
    runner._scylla_version = "unstable/master:2026-06-26"

    assert runner._scylla_version_for_test_command() == "unstable/master:2026-06-26"


def test_legacy_driver_type_alias_uses_apache_versions(tmp_path):
    runner = make_runner(tmp_path, tag="4.12.0", driver_type="datastax")

    assert runner._driver_type == "apache"
    assert runner.version_folder == REPO_ROOT / "versions" / "apache" / "4.12.0"


def test_environment_uses_java_11_for_add_exports_jvm_config(monkeypatch, tmp_path):
    java_home_11 = tmp_path / "jdk-11"
    java_home_11.mkdir()
    monkeypatch.setenv("JAVA_HOME", "/usr/lib/jvm/temurin-8-jdk-amd64")
    monkeypatch.setenv("JAVA_HOME_11_X64", str(java_home_11))
    runner = make_runner(tmp_path)
    jvm_config = runner._java_driver_git / ".mvn" / "jvm.config"
    jvm_config.parent.mkdir()
    jvm_config.write_text(
        "--add-exports=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED\n",
        encoding="utf-8",
    )

    assert runner.environment["JAVA_HOME"] == str(java_home_11)


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
