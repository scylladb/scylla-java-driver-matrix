import logging
import os
import shutil
import subprocess
from distutils.util import strtobool
from functools import cached_property
from pathlib import Path

import yaml

from processjunit import ProcessJUnit

DEV_MODE = bool(strtobool(os.environ.get("DEV_MODE", "False")))


class Run:
    def __init__(self, java_driver_git, scylla_install_dir, tag, tests, scylla_version=None):
        self._tag = tag
        self._java_driver_git = Path(java_driver_git)
        self._scylla_version = scylla_version
        self._scylla_install_dir = scylla_install_dir
        self._tests = tests
        self._report_path = self._java_driver_git / "integration-tests" / "target" / "surefire-reports"
        if self._tag.startswith('3.7'):
            self._report_path = self._java_driver_git / "driver-core" / "target" / "surefire-reports"

    def _setup_out_dir(self):
        here = os.path.dirname(__file__)
        xunit_dir = os.path.join(here, 'xunit', self._tag)
        if not os.path.exists(xunit_dir):
            os.makedirs(xunit_dir)
        return xunit_dir

    def _ignoreFile(self):
        here = os.path.dirname(__file__)
        return os.path.join(here, 'versions', self._tag, 'ignore.yaml')

    def _ignoreSet(self):
        ignore_tests = []
        with open(self._ignoreFile()) as f:
            content = yaml.safe_load(f)
            ignore_tests.extend(content['tests'])
        return set(ignore_tests)

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
                              cwd=self._java_driver_git, stderr=subprocess.PIPE) as proc:
            stderr = proc.communicate()
            status_code = proc.returncode
        assert status_code == 0, stderr

    def _apply_patch(self):
        patch_file = Path(os.path.dirname(__file__)) / 'versions' / self._tag / 'patch'
        if not patch_file.is_file():
            raise Exception('Cannot find patch for version {}'.format(self._tag))
        self._run_command_in_shell(f"git apply --check {patch_file}")
        self._run_command_in_shell(f"patch -p1 -i {patch_file}")

    def run(self) -> ProcessJUnit:
        self._run_command_in_shell("git checkout .")
        self._run_command_in_shell(f"git checkout {self._tag}")
        self._apply_patch()
        exclude_str = ', '.join(f"!{ignore_element}" for ignore_element in self._ignoreSet())

        logging.info("Formatting the Java-driver code after applying the patch")
        self._run_command_in_shell("mvn com.coveo:fmt-maven-plugin:format")
        logging.info("Starting build the version")
        self._run_command_in_shell("mvn install -DskipTests=true -Dmaven.javadoc.skip=true -V")

        cmd = f"mvn -B -pl integration-tests -Dtest='{exclude_str}, {self._tests}' test"
        if self._tag.startswith('3.7'):
            cmd = f"mvn -B -pl driver-core -Dtest.groups='long' -Dtest='{exclude_str}, {self._tests}' test"

        shutil.rmtree(self._report_path, ignore_errors=True)
        if self._scylla_version:
            cmd += f" -Dscylla.version={self._scylla_version}"
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

        report = ProcessJUnit(
            new_report_xml_path=Path(os.path.dirname(__file__)) / "reports" / f"TEST-{self._tag}.xml",
            tests_result_path=self._report_path,
            tag=self._tag)
        return report
