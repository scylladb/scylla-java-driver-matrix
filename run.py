import json
import logging
import os
import re
import shutil
import shlex
import subprocess
import sys
from functools import cached_property
from pathlib import Path
from typing import List, Sequence, Set
from packaging.version import Version

import yaml

from processjunit import ProcessJUnit


def strtobool(value: str) -> bool:
    value = value.lower()
    if value in ("y", "yes", "t", "true", "on", "1"):
        return True
    if value in ("n", "no", "f", "false", "off", "0"):
        return False
    raise ValueError(f"invalid truth value {value!r}")


DEV_MODE = bool(strtobool(os.environ.get("DEV_MODE", "False")))


def load_ignore_tests(ignore_file_path: Path) -> Set[str]:
    if not ignore_file_path.is_file():
        return set()

    text = ignore_file_path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^\s*-\s+[^'\"#\n][^#\n]*\s+#\S", line):
            raise ValueError(
                f"Invalid test selector in '{ignore_file_path}' at line {line_number}: "
                "entries containing '#' must be quoted"
            )

    content = yaml.safe_load(text)
    if content is None:
        return set()
    if not isinstance(content, dict):
        raise ValueError(f"The '{ignore_file_path}' file must contain a YAML mapping")

    tests = content.get('tests')
    if tests is None:
        return set()
    if not isinstance(tests, list):
        raise ValueError(f"The 'tests' entry in '{ignore_file_path}' must be a list")

    result = set()
    invalid_indexes = []
    duplicates = []
    for index, test_name in enumerate(tests, start=1):
        if not isinstance(test_name, str) or not test_name.strip():
            invalid_indexes.append(index)
            continue
        test_name = test_name.strip()
        if test_name in result:
            duplicates.append(test_name)
            continue
        result.add(test_name)

    if invalid_indexes or duplicates:
        details = []
        if invalid_indexes:
            indexes = ", ".join(str(index) for index in invalid_indexes)
            details.append(f"empty or non-string entries at indexes: {indexes}")
        if duplicates:
            details.append(f"duplicate entries: {', '.join(duplicates)}")
        raise ValueError(f"Invalid ignore tests in '{ignore_file_path}': {'; '.join(details)}")

    return result


class Run:
    def __init__(self, java_driver_git, scylla_install_dir, tag, tests, driver_type, scylla_version=None, patch_only=False, checkout_ref=None):
        self._patch_only = patch_only
        self._tag = tag
        self._checkout_ref = checkout_ref or tag
        self._java_driver_git = Path(java_driver_git)
        self._scylla_version = scylla_version
        self._scylla_install_dir = scylla_install_dir
        self._tests = tests
        self._report_path = self._java_driver_git / "integration-tests" / "target" / "failsafe-reports"
        if self._tag.startswith('3'):
            self._report_path = self._java_driver_git / "driver-core" / "target" / "surefire-reports"
        self._root_path = Path(__file__).parent
        self._driver_type = driver_type

    def _setup_out_dir(self):
        here = os.path.dirname(__file__)
        xunit_dir = os.path.join(here, 'xunit', self._tag)
        if not os.path.exists(xunit_dir):
            os.makedirs(xunit_dir)
        return xunit_dir

    @property
    def metadata_file_name(self) -> str:
        return f'metadata_{self._tag}.json'

    @cached_property
    def version(self) -> str:
        version = self._tag
        if f"-scylla-" in version:
            version = version.replace(f"-scylla-", ".")
        return version

    @cached_property
    def version_folder(self) -> Path:
        version_pattern = re.compile(r"(\d+.)+\d+$")
        target_version_folder = self._root_path / "versions" / self._driver_type
        driver_version_dir_path = target_version_folder / self.version
        if driver_version_dir_path.is_dir():
            logging.info("The full directory for '%s' tag is '%s'", self._tag, driver_version_dir_path)
            return driver_version_dir_path

        target_version = Version(self.version)
        tags_defined = sorted(
            (
                Version(folder_path.name)
                for folder_path in target_version_folder.iterdir() if version_pattern.match(folder_path.name)
            ),
            reverse=True
        )
        for tag in tags_defined:
            if tag <= target_version:
                logging.info("The full directory for '%s' tag is '%s'", self._tag, driver_version_dir_path)
                return target_version_folder / str(tag)
        else:
            raise ValueError("Not found directory for python-driver version '%s'", self._tag)

    @cached_property
    def ignore_tests(self) -> Set[str]:
        ignore_file_path = self.version_folder / "ignore.yaml"
        return load_ignore_tests(ignore_file_path)

    @cached_property
    def environment(self):
        result = {}
        result.update(os.environ)
        if java_home := self._java_home_for_driver():
            result['JAVA_HOME'] = java_home
        if self._scylla_version:
            result['SCYLLA_VERSION'] = self._scylla_version
        else:
            result['INSTALL_DIRECTORY'] = self._scylla_install_dir
        return result

    def _java_home_for_driver(self) -> str:
        jvm_config = self._java_driver_git / ".mvn" / "jvm.config"
        if not jvm_config.is_file():
            return ""
        if "--add-exports=" not in jvm_config.read_text(encoding="utf-8"):
            return ""

        for candidate in (
                os.environ.get("JAVA_HOME_11_X64"),
                os.environ.get("JAVA_11_HOME"),
                "/usr/lib/jvm/temurin-11-jdk-amd64",
        ):
            if candidate and Path(candidate).is_dir():
                return candidate

        logging.warning("Driver JVM config requires Java 11, but no Java 11 home was found")
        return ""

    def _run_command(self, cmd: Sequence[str]):
        cmd = [str(arg) for arg in cmd]
        logging.info("Execute the cmd '%s'", shlex.join(cmd))
        with subprocess.Popen(cmd, env=self.environment, cwd=self._java_driver_git,
                              stderr=subprocess.PIPE, text=True) as proc:
            _, stderr = proc.communicate()
            status_code = proc.returncode
        assert status_code == 0, stderr

    def _mvn_command(self, *args: str) -> List[str]:
        cmd = ["mvn"]
        if not sys.stdout.isatty():
            cmd.append("-B")
        cmd.extend(args)
        return cmd

    def _apply_patch_files(self) -> bool:
        is_dir_empty = True
        for file_path in self.version_folder.iterdir():
            is_dir_empty = False
            if file_path.name.startswith("patch"):
                try:
                    logging.info("Show patch's statistics for file '%s'", file_path)
                    self._run_command(["git", "apply", "--stat", str(file_path)])
                    logging.info("Detect patch's errors for file '%s'", file_path)
                    self._run_command(["git", "apply", "-v", "--check", str(file_path)])
                    logging.info("Applying patch file '%s'", file_path)
                    self._run_command(["patch", "-p1", "-i", str(file_path)])
                except Exception as exc:
                    logging.error("Failed to apply patch '%s' to version '%s', with: '%s'",
                                  file_path, self._tag, str(exc))
                    raise
        if is_dir_empty:
            logging.warning("The '%s' directory does not contain any files", self.version_folder)

    def _test_command(self, tests_string: str) -> List[str]:
        if self._tag.startswith('3'):
            tests_string = tests_string or '*'
            return self._mvn_command(
                "-pl", "driver-core", "-Dtest.groups=short,long", f"-Dtest={tests_string}", "test"
            )

        cmd = self._mvn_command("-pl", "integration-tests", "integration-test")
        if tests_string:
            cmd.append(f"-Dit.test={tests_string}")
        return cmd

    def _scylla_version_for_test_command(self) -> str:
        if (
                self._driver_type == "datastax"
                and not self._tag.startswith("3")
                and self._scylla_version
                and ":" not in self._scylla_version
                and os.environ.get("SCYLLA_UNIFIED_PACKAGE") is None
        ):
            return f"release:{self._scylla_version}"
        return self._scylla_version

    def create_metadata_for_failure(self, reason: str) -> None:
        reports_dir = Path(os.path.dirname(__file__)) / "reports"
        if not reports_dir.exists():
            reports_dir.mkdir(exist_ok=True, parents=True)
        metadata_file = reports_dir / self.metadata_file_name
        metadata = {
            "driver_name": f"TEST-{self._tag}",
            "driver_type": "java",
            "failure_reason": reason,
        }
        metadata_file.write_text(json.dumps(metadata))

    def run(self) -> ProcessJUnit:
        self._run_command(["git", "checkout", "."])
        logging.info("Checking out driver ref '%s' for version '%s'", self._checkout_ref, self._tag)
        self._run_command(["git", "checkout", self._checkout_ref])
        self._apply_patch_files()

        if self._patch_only:
            logging.info("Patch-only mode: patches applied successfully for '%s'", self._tag)
            return None

        tests_string = self._tests
        if exclude_str := ','.join(f"!{ignore_element}" for ignore_element in self.ignore_tests):
            tests_string = f"{exclude_str},{tests_string}".rstrip(',')

        logging.info("Formatting the Java-driver code after applying the patch")
        self._run_command(self._mvn_command("com.coveo:fmt-maven-plugin:format"))

        self._run_command(self._mvn_command("clean"))
        logging.info("Starting build the version")
        self._run_command(self._mvn_command("install", "-DskipTests=true", "-Dmaven.javadoc.skip=true", "-V"))

        cmd = self._test_command(tests_string)

        shutil.rmtree(self._report_path, ignore_errors=True)
        if self._scylla_version:
            scylla_version = self._scylla_version_for_test_command()
            if self._tag.startswith('3') or self._driver_type != 'scylla':
                cmd.append(f"-Dscylla.version={scylla_version}")
            else:
                # Way it works after 4.19.0.0 `ccm.distribution` was introduced
                cmd.extend([f"-Dccm.version={scylla_version}", "-Dccm.distribution=scylla"])
                # Before 4.19.0.0 it required a flag:
                cmd.append("-Dccm.scylla")

        elif self._scylla_install_dir:
            cmd.append(f"-Dccm.directory={self._scylla_install_dir}")
        else:
            raise ValueError("No scylla version or Cassandra dir defined")

        logging.info("Starting run the tests")
        try:
            self._run_command(cmd)
            logging.info("All tests are passed for '%s' version", self._tag)
        except AssertionError:
            # Some tests are failed
            pass
        metadata_file = Path(os.path.dirname(__file__)) / "reports" / self.metadata_file_name
        metadata_file.parent.mkdir(exist_ok=True)
        metadata = {
            "driver_name": f"TEST-{self._driver_type}-{self._tag}",
            "driver_type": "java",
            "junit_result": f"./TEST-{self._driver_type}-{self._tag}.xml",
        }
        report = ProcessJUnit(
            new_report_xml_path=Path(os.path.dirname(__file__)) / "reports" / f"TEST-{self._driver_type}-{self._tag}.xml",
            tests_result_path=self._report_path,
            tag=self._tag,
            driver_type=self._driver_type,
        )
        metadata_file.write_text(json.dumps(metadata))
        return report
