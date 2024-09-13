import os
import sys
import logging
import argparse
import traceback
from datetime import timedelta
import subprocess
from typing import List

import run
from email_sender import send_mail, create_report, get_driver_origin_remote

logging.basicConfig(level=logging.INFO)


def main(java_driver_git, scylla_install_dir, tests, versions, driver_type,scylla_version, recipients):
    status = 0
    results = {}
    logging.info("=== Going to test those versions: %s", versions)

    for version in versions:
        logging.info("=== JAVA DRIVER VERSION %s ===", version)
        runner = run.Run(
                java_driver_git=java_driver_git,
                scylla_install_dir=scylla_install_dir,
                tag=version,
                tests=tests,
                driver_type=driver_type,
                scylla_version=scylla_version)
        try:
            report = runner.run()
            logging.info("=== JAVA DRIVER MATRIX RESULTS FOR %s ===", version)
            logging.info(", ".join(f"{key}: {value}" for key, value in report.summary.items()))
            if report.is_failed:
                status = 1
            if not run.DEV_MODE:
                report.clear_original_reports()
            results[version] = report.summary
            results[version]['time'] = str(timedelta(seconds=results[version]['time']))[:-3]
        except Exception:
            logging.exception(f"{version} failed")
            status = 1
            exc_type, exc_value, exc_traceback = sys.exc_info()
            failure_reason = traceback.format_exception(exc_type, exc_value, exc_traceback)
            results[version] = dict(exception=failure_reason)
            runner.create_metadata_for_failure(reason="\n".join(failure_reason))

    if recipients:
        email_report = create_report(results=results)
        email_report['driver_remote'] = get_driver_origin_remote(java_driver_git)
        email_report['status'] = "SUCCESS" if status == 0 else "FAILED"
        send_mail(recipients, email_report)
    quit(status)


def extract_n_latest_repo_tags(repo_directory: str, major_versions: List[str], latest_tags_size: int = 2,
                               is_scylla_driver: bool = True) -> List[str]:
    major_versions = sorted(major_versions, key=lambda major_ver: float(major_ver))
    filter_version = f"| grep {'' if is_scylla_driver else '-v '}'.*\..*\..*\.'"
    commands = [f"cd {repo_directory}", "git checkout .", ]
    if not os.environ.get("DEV_MODE", False):
        commands.append("git fetch -p --all")
    commands.append(f"git tag --sort=-creatordate {filter_version}")

    selected_tags = {}
    ignore_tags = set()
    result = []
    lines = subprocess.check_output("\n".join(commands), shell=True).decode().splitlines()
    for repo_tag in lines:
        if "." in repo_tag:
            version = tuple(repo_tag.split(".", maxsplit=3)[:3])
            if version not in ignore_tags:
                ignore_tags.add(version)
                selected_tags.setdefault(repo_tag[0], []).append(repo_tag)

    for major_version in major_versions:
        if len(selected_tags[major_version]) < latest_tags_size:
            raise ValueError(f"There are no '{latest_tags_size}' different versions that start with the major version"
                             f" '{major_version}'")
        result.extend(selected_tags[major_version][:latest_tags_size])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('java_driver_git', help='folder with git repository of java-driver')
    parser.add_argument('scylla_install_dir',
                        help='folder with scylla installation, e.g. a checked out git scylla has been built',
                        nargs='?', default='')
    parser.add_argument('--versions', default=[],
                        help='java-driver versions to test')
    parser.add_argument('--tests', default='*',
                        help='tests to pass to nosetests tool, default=tests.integration.standard')
    parser.add_argument('--scylla-version', help="relocatable scylla version to use", default=os.environ.get('SCYLLA_VERSION', None))
    parser.add_argument('--recipients', help="whom to send mail at the end of the run",  nargs='+', default=None)
    parser.add_argument('--driver-type', help='Type of python-driver ("scylla", "cassandra" or "datastax")',
                        dest='driver_type', default='datastax')
    parser.add_argument('--version-size', help='The number of the latest versions that will test.'
                                               'The version is filtered by the major and minor values.'
                                               'For example, the user selects the 2 latest versions for version 4.'
                                               'The values to be returned are: 4.9.0-scylla-1 and 4.8.0-scylla-0',
                        type=int, default=None, nargs='?')

    arguments = parser.parse_args()
    versions = []
    _input_versions = []
    if not isinstance(arguments.versions, list):
        versions = _input_versions = arguments.versions.split(',')

    if arguments.version_size:
        # all one digit version, would be used to look up latest tags
        versions = extract_n_latest_repo_tags(arguments.java_driver_git, list({v.split('.')[0] for v in _input_versions}),
                                              latest_tags_size=arguments.version_size,
                                              is_scylla_driver=arguments.driver_type == "scylla")

        # add back all the full qualified versions specified in `--versions` (i.e. not one digit versions)
        versions += [v for v in _input_versions if len(v.split('.')) > 1]

    main(java_driver_git=arguments.java_driver_git, scylla_install_dir=arguments.scylla_install_dir,
         tests=arguments.tests, versions=versions,
         scylla_version=arguments.scylla_version,
         driver_type=arguments.driver_type,
         recipients=arguments.recipients)

