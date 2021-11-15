import logging
import os
import subprocess
import yaml


class Run:
    def __init__(self, java_driver_git, scylla_install_dir, tag, tests, scylla_version=None):
        self._tag = tag
        self._java_driver_git = java_driver_git
        self._scylla_version = scylla_version
        self._scylla_install_dir = scylla_install_dir
        self._tests = tests
        self._run()
        self.summary = self._process_output()

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

    def _environment(self):
        result = {}
        result.update(os.environ)
        if self._scylla_version:
            result['SCYLLA_VERSION'] = self._scylla_version
        else:
            result['INSTALL_DIRECTORY'] = self._scylla_install_dir
        return result

    def _apply_patch(self):
        here = os.path.dirname(__file__)
        patch_file = os.path.join(here, 'versions', self._tag, 'patch')
        if not os.path.exists(patch_file):
            raise Exception('Cannot find patch for version {}'.format(self._tag))
        command = "patch -p1 -i {}".format(patch_file)
        subprocess.check_call(command, shell=True)

    def _run(self):
        os.chdir(self._java_driver_git)
        subprocess.check_call('git checkout .'.format(self._tag), shell=True)
        subprocess.check_call('git checkout {}'.format(self._tag), shell=True)
        self._apply_patch()
        exclude_str = ''
        for ignore_element in self._ignoreSet():
            exclude_str += '!%s, ' % ignore_element

        cmd = ["bash", "-c", "mvn  -B install -DskipTests=true -Dmaven.javadoc.skip=true -V"]
        logging.info(cmd)
        self.status = subprocess.run(cmd, env=self._environment(), cwd=self._java_driver_git)

        if not self.status.returncode == 0:
            logging.error("Build failed")
            return

        if self._tag.startswith('3.7'):
            self._report_path =  "driver-core/target/surefire-reports/"
            cmd = ["bash", "-c", "rm -rf {0}*".format(self._report_path)]
            logging.info(cmd)
            subprocess.run(cmd, env=self._environment(), cwd=self._java_driver_git)
            if  self._scylla_version:
                cmd = ["bash",  "-c",  "mvn -B -pl driver-core -Dtest.groups='long' -Dtest='{0}{self._tests}' test -Dscylla.version={self._scylla_version}".format(exclude_str, self=self)]
            elif self._scylla_install_dir:
                cmd = ["bash",  "-c",  "mvn -B -pl driver-core -Dtest.groups='long' -Dtest='{0}{self._tests}' test -Dccm.directory={self._scylla_install_dir}".format(exclude_str, self=self)]
            else:
                raise ValueError("No scylla version or cassaandra dir defined")

            logging.info(cmd)
            self.status = subprocess.run(cmd, env=self._environment(), cwd=self._java_driver_git)
        else:
            self._report_path = "integration-tests/target/surefire-reports/"
            cmd = ["bash", "-c", "rm -rf {0}*".format(self._report_path)]
            logging.info(cmd)
            subprocess.run(cmd, env=self._environment(), cwd=self._java_driver_git)

            if  self._scylla_version:
                cmd = ["bash",  "-c",  "mvn -B -pl integration-tests -Dtest='{0}{self._tests}' test -Dscylla.version={self._scylla_version}".format(exclude_str, self=self)]
            elif self._scylla_install_dir:
                cmd = ["bash",  "-c",  "mvn -B -pl integration-tests -Dtest='{0}{self._tests}' test -Dccm.directory={self._scylla_install_dir}".format(exclude_str, self=self)]
            else:
                raise ValueError("No scylla version or cassaandra dir defined")

            logging.info(cmd)
            self.status = subprocess.run(cmd, env=self._environment(), cwd=self._java_driver_git)

    def _process_output(self):
        subprocess.call(["bash", "-c", "mkdir -p ../{0} ;"
                                       " rm ../{0}/* ;"
                                       " mv {1}*.* ../{0}/".format(self._tag, self._report_path)],
            universal_newlines=True, cwd=self._java_driver_git)

        subprocess.call(["bash", "-c", "sed -i 's/com.datastax/{0}.com.datastax/' ../{0}/*.xml".format(self._tag)],
                        universal_newlines=True, cwd=self._java_driver_git)

        return self.status.returncode == 0
