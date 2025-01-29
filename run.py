import json
import logging
import os
import re
import shutil
import subprocess
import sys
from distutils.util import strtobool
from functools import cached_property
from pathlib import Path
from typing import Set
from packaging.version import Version

import yaml

from processjunit import ProcessJUnit

DEV_MODE = bool(strtobool(os.environ.get("DEV_MODE", "False")))


class Run:
    def __init__(self, java_driver_git, scylla_install_dir, tag, tests, driver_type, scylla_version=None):
        self._tag = tag
        self._java_driver_git = Path(java_driver_git)
        self._scylla_version = scylla_version
        self._scylla_install_dir = scylla_install_dir
        self._tests = tests
        self._report_path = self._java_driver_git / "integration-tests" / "target" / "surefire-reports"
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
        result = set()
        ignore_file_path = self.version_folder / "ignore.yaml"
        if not ignore_file_path.is_file():
            return result
        with (self.version_folder / "ignore.yaml").open(mode="r", encoding="utf-8") as file:
            content = yaml.safe_load(file)
            result.update(content['tests'])
        return result

    @cached_property
    def environment(self):
        result = {}
        result.update(os.environ)
        if self._scylla_version:
            result['SCYLLA_VERSION'] = self._scylla_version
        else:
            result['INSTALL_DIRECTORY'] = self._scylla_install_dir
        return result

    def _run_command_in_shell(self, cmd: str):
        logging.info("Execute the cmd '%s'", cmd)
        with subprocess.Popen(cmd, shell=True, executable="/bin/bash", env=self.environment,
                              cwd=self._java_driver_git, stderr=subprocess.PIPE, text=True) as proc:
            _, stderr = proc.communicate()
            status_code = proc.returncode
        assert status_code == 0, stderr

    def _apply_patch_files(self) -> bool:
        is_dir_empty = True
        for file_path in self.version_folder.iterdir():
            is_dir_empty = False
            if file_path.name.startswith("patch"):
                try:
                    logging.info("Show patch's statistics for file '%s'", file_path)
                    self._run_command_in_shell(f"git apply --stat {file_path}")
                    logging.info("Detect patch's errors for file '%s'", file_path)
                    self._run_command_in_shell(f"git apply -v --check {file_path}")
                    logging.info("Applying patch file '%s'", file_path)
                    self._run_command_in_shell(f"patch -p1 -i {file_path}")
                except Exception as exc:
                    logging.error("Failed to apply patch '%s' to version '%s', with: '%s'",
                                  file_path, self._tag, str(exc))
                    raise
        if is_dir_empty:
            logging.warning("The '%s' directory does not contain any files", self.version_folder)

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
        self._run_command_in_shell("git checkout .")
        self._run_command_in_shell(f"git checkout {self._tag}")
        self._apply_patch_files()

        tests_string = self._tests
        if exclude_str := ','.join(f"!{ignore_element}" for ignore_element in self.ignore_tests):
            tests_string = f"{exclude_str},{tests_string}"

        no_tty = '' if sys.stdout.isatty() else '-B'

        logging.info("Formatting the Java-driver code after applying the patch")
        self._run_command_in_shell(f"mvn {no_tty} com.coveo:fmt-maven-plugin:format")

        self._run_command_in_shell(f"mvn {no_tty} clean")
        logging.info("Starting build the version")
        self._run_command_in_shell(f"mvn {no_tty} install -DskipTests=true -Dmaven.javadoc.skip=true -V")

        cmd = f"mvn {no_tty} -pl integration-tests -Dtest='{tests_string}' test"
        if self._tag.startswith('3'):
            cmd = f"mvn {no_tty} -pl driver-core -Dtest.groups='short,long' -Dtest='{tests_string}' test"

        shutil.rmtree(self._report_path, ignore_errors=True)
        if self._scylla_version:
            cmd += f" -Dscylla.version={self._scylla_version} -Dccm.scylla"
        elif self._scylla_install_dir:
            cmd += f" -Dccm.directory={self._scylla_install_dir}"
        else:
            raise ValueError("No scylla version or Cassandra dir defined")

        logging.info("Starting run the tests")
        try:
            self._run_command_in_shell(cmd)
            logging.info("All tests are passed for '%s' version", self._tag)
        except AssertionError:
            # Some tests are failed
            pass
        metadata_file = Path(os.path.dirname(__file__)) / "reports" / self.metadata_file_name
        metadata_file.parent.mkdir(exist_ok=True)
        metadata = {
            "driver_name": f"TEST-{self._tag}",
            "driver_type": "java",
            "junit_result": f"./TEST-{self._tag}.xml",
        }
        report = ProcessJUnit(
            new_report_xml_path=Path(os.path.dirname(__file__)) / "reports" / f"TEST-{self._tag}.xml",
            tests_result_path=self._report_path,
            tag=self._tag)
        metadata_file.write_text(json.dumps(metadata))
        return report
