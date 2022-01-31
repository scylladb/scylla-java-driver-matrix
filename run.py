import logging
import os
import re
import shutil
import subprocess
import tempfile
from distutils.util import strtobool
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Dict, Set

import yaml
from packaging.version import Version

from processjunit import ProcessJUnit

DEV_MODE = bool(strtobool(os.environ.get("DEV_MODE", "False")))


class Run:
    def __init__(self, java_driver_git, scylla_install_dir, driver_version, tests, driver_type, result_dir_path,
                 scylla_version=None):
        self.driver_version = driver_version
        self._java_driver_git = Path(java_driver_git)
        self._scylla_version = scylla_version
        self._scylla_install_dir = scylla_install_dir
        self._tests = tests
        self._root_path = Path(__file__).parent
        root_tests_result = self._java_driver_git / "integration-tests" / "target"
        if self.driver_version.startswith("3"):
            root_tests_result = self._java_driver_git / "driver-core" / "target"
        if not DEV_MODE and root_tests_result.is_dir():
            # Remove old JAR files
            shutil.rmtree(root_tests_result)
        self._surefire_reports_path = root_tests_result / "surefire-reports"
        self._failsafe_reports_path = root_tests_result / "failsafe-reports"
        self._driver_type = driver_type
        self._report_path = result_dir_path / f"{self._driver_type}_{self.driver_version}.xml"
        self._venv_path = self._root_path / "venv" / self._driver_type / self.driver_version

    @cached_property
    def version(self) -> str:
        version = self.driver_version
        if f"-scylla-" in version:
            version = version.replace(f"-scylla-", ".")
        return version

    @cached_property
    def version_folder(self) -> Path:
        version_pattern = re.compile(r"(\d+.)+\d+$")
        target_version_folder = self._root_path / "versions" / self._driver_type
        driver_version_dir_path = target_version_folder / self.version
        if driver_version_dir_path.is_dir():
            logging.info("The full directory for '%s' tag is '%s'", self.driver_version, driver_version_dir_path)
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
                logging.info("The full directory for '%s' tag is '%s'", self.driver_version, driver_version_dir_path)
                return target_version_folder / str(tag)
        else:
            raise ValueError("Not found directory for python-driver version '%s'", self.driver_version)

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
    def environment(self) -> Dict:
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

    def _checkout_branch(self):
        try:
            self._run_command_in_shell("git checkout .")
            logging.info("git checkout to '%s' tag branch", self.driver_version)
            self._run_command_in_shell(f"git checkout {self.driver_version}")
            return True
        except Exception as exc:
            logging.error("Failed to branch for version '%s', with: '%s'", self.driver_version, str(exc))
            return False

    def _apply_patch_files(self) -> bool:
        is_dir_empty = True
        for file_path in self.version_folder.iterdir():
            is_dir_empty = False
            if file_path.name.startswith("patch"):
                try:
                    logging.info("Show patch's statistics for file '%s'", file_path)
                    self._run_command_in_shell(f"git apply --stat {file_path}")
                    logging.info("Detect patch's errors for file '%s'", file_path)
                    self._run_command_in_shell(f"git apply --check {file_path}")
                    logging.info("Applying patch file '%s'", file_path)
                    self._run_command_in_shell(f"patch -p1 -i {file_path}")
                except Exception as exc:
                    logging.error("Failed to apply patch '%s' to version '%s', with: '%s'",
                                  file_path, self.driver_version, str(exc))
                    return False
        if is_dir_empty:
            logging.warning("The '%s' directory does not contain any files", self.version_folder)
        return True

    @lru_cache(maxsize=None)
    def _activate_venv_cmd(self):
        return f"source {self._venv_path}/bin/activate"

    @lru_cache(maxsize=None)
    def _create_venv(self):
        basic_packages = ("https://github.com/scylladb/scylla-ccm/archive/master.zip",)
        if self._venv_path.exists() and self._venv_path.is_dir():
            logging.info("Removing old python venv in directory '%s'", self._venv_path)
            shutil.rmtree(self._venv_path)

        logging.info("Creating a new python venv in directory '%s'", self._venv_path)
        self._venv_path.mkdir(parents=True)
        self._run_command_in_shell(cmd=f"python3 -m venv {self._venv_path}")
        logging.info("Upgrading 'pip' and 'setuptools' packages to the latest version")
        self._run_command_in_shell(cmd=f"{self._activate_venv_cmd()} && pip install --upgrade pip setuptools")
        logging.info("Installing the following packages:\n%s", "\n".join(basic_packages))
        self._run_command_in_shell(cmd=f"{self._activate_venv_cmd()} && pip install {' '.join(basic_packages)}")

    @lru_cache(maxsize=None)
    def _install_python_requirements(self):
        if os.environ.get("DEV_MODE", False) and self._venv_path.exists() and self._venv_path.is_dir():
            return True
        try:
            self._create_venv()
            scripts_directory_path = self._root_path / "scripts"
            for requirement_file in ["requirements.txt", "test-requirements.txt"]:
                requirement_file_path = scripts_directory_path / requirement_file
                if requirement_file_path.is_file():
                    self._run_command_in_shell(f"{self._activate_venv_cmd()} && "
                                               f"pip install --force-reinstall -r {requirement_file_path}")
            return True
        except Exception as exc:
            logging.error("Failed to install python requirements for version %s, with: %s",
                          self.driver_version, str(exc))
            return False

    @lru_cache(maxsize=None)
    def create_report_result(self) -> ProcessJUnit:
        temp_path = Path(tempfile.mkdtemp())
        if self._surefire_reports_path.is_dir():
            self._run_command_in_shell(f"mv {self._surefire_reports_path / 'TEST*.xml'} {temp_path}/")
        if self._failsafe_reports_path.is_dir():
            self._run_command_in_shell(f"mv {self._failsafe_reports_path / 'TEST*.xml'} {temp_path}/")
            shutil.rmtree(self._failsafe_reports_path)
        return ProcessJUnit(new_report_xml_path=self._report_path, tests_result_path=temp_path)

    def run(self) -> ProcessJUnit:
        if not (self._checkout_branch() and self._apply_patch_files() and self._install_python_requirements()):
            raise RuntimeError("Something unexpected happened, please check the console logs messages.")

        tests_string = self._tests
        if exclude_str := ', '.join(f"!{ignore_element}" for ignore_element in self.ignore_tests):
            tests_string = f"{exclude_str}, {tests_string}"
        logging.info("Running 'mvn clean' to clear old build")
        self._run_command_in_shell("mvn clean")
        if not DEV_MODE:
            logging.info("Formatting the Java-driver code after applying the patch")
            self._run_command_in_shell("mvn com.coveo:fmt-maven-plugin:format")
        logging.info("Starting build the version")
        self._run_command_in_shell("mvn install -DskipTests=true -Dmaven.javadoc.skip=true -V")

        cmd = f"mvn -B -pl integration-tests -Dtest='{tests_string}' test"
        if self.driver_version.startswith("3"):
            cmd = f"mvn -B -pl driver-core -Dtest.groups='long' -Dtest='{tests_string}' test"
        shutil.rmtree(self._report_path, ignore_errors=True)
        if self._scylla_version:
            cmd += f" -Dscylla.version={self._scylla_version}"
        elif self._scylla_install_dir:
            cmd += f" -Dccm.directory={self._scylla_install_dir}"
        else:
            raise ValueError("No scylla version or Cassandra dir defined")

        try:
            self._run_command_in_shell(cmd)
            logging.info("All tests are passed for '%s' version", self.driver_version)
        except AssertionError:
            # Some tests are failed
            pass

        return self.create_report_result()
