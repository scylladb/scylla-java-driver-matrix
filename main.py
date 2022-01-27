import os
import logging
import argparse

import run

logging.basicConfig(level=logging.INFO)


def main(java_driver_git, scylla_install_dir, tests, versions, scylla_version):
    status = 0
    for version in versions:
        logging.info("=== JAVA DRIVER VERSION %s ===", version)
        report = run.Run(
            java_driver_git=java_driver_git,
            scylla_install_dir=scylla_install_dir,
            tag=version,
            tests=tests,
            scylla_version=scylla_version).run()

        logging.info("=== JAVA DRIVER MATRIX RESULTS FOR %s ===", version)
        logging.info(", ".join(f"{key}: {value}" for key, value in report.summary.items()))
        if report.is_failed:
            status = 1
    quit(status)


if __name__ == '__main__':
    versions = ['4.1.0', '4.2.0', '4.3.0', '4.x']
    parser = argparse.ArgumentParser()
    parser.add_argument('java_driver_git', help='folder with git repository of java-driver')
    parser.add_argument('scylla_install_dir',
                        help='folder with scylla installation, e.g. a checked out git scylla has been built',
                        nargs='?', default='')
    parser.add_argument('--versions', default=versions,
                        help='java-driver versions to test, default={}'.format(','.join(versions)))
    parser.add_argument('--tests', default='*',
                        help='tests to pass to nosetests tool, default=tests.integration.standard')
    parser.add_argument('--scylla-version', help="relocatable scylla version to use", default=os.environ.get('SCYLLA_VERSION', None))
    arguments = parser.parse_args()
    if not isinstance(arguments.versions, list):
        versions = arguments.versions.split(',')
    main(arguments.java_driver_git, arguments.scylla_install_dir, arguments.tests, versions, arguments.scylla_version)

