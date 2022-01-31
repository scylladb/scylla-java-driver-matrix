import os
import logging
import argparse
import shutil
import subprocess
from pathlib import Path
from typing import List

import run

logging.basicConfig(level=logging.INFO)


def main(arguments: argparse.Namespace):
    result_dir_path = Path(__file__).parent / "xunit"
    shutil.rmtree(result_dir_path, ignore_errors=True)
    status = 0
    for is_scylla_driver, driver_version in arguments.versions:
        driver_type = "scylla" if is_scylla_driver else "datastax"
        logging.info("=== JAVA DRIVER VERSION %s:%s ===", driver_type, driver_version)
        report = run.Run(
            java_driver_git=arguments.java_driver_git,
            scylla_install_dir=arguments.scylla_install_dir,
            driver_version=driver_version,
            tests=arguments.tests,
            driver_type=driver_type,
            scylla_version=arguments.scylla_version,
            result_dir_path=result_dir_path).run()

        logging.info("=== JAVA DRIVER MATRIX RESULTS FOR %s:%s ===", driver_type, driver_version)
        logging.info(", ".join(f"{key}: {value}" for key, value in report.summary.items()))
        if report.is_failed:
            status = 1
    quit(status)


def extract_n_latest_repo_tags(repo_directory: str, major_versions: List[str], latest_tags_size: int = 2,
                               is_scylla_driver: bool = True) -> List[str]:
    major_versions = sorted(major_versions, key=lambda major_ver: float(major_ver))
    filter_version = f"| grep {'' if is_scylla_driver else '-v '}scylla"
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
            version = tuple(repo_tag.split(".", maxsplit=2)[:2])
            if version not in ignore_tags:
                ignore_tags.add(version)
                selected_tags.setdefault(repo_tag[0], []).append(repo_tag)

    for major_version in major_versions:
        if len(selected_tags[major_version]) < latest_tags_size:
            raise ValueError(f"There are no '{latest_tags_size}' different versions that start with the major version"
                             f" '{major_version}'")
        result.extend(selected_tags[major_version][:latest_tags_size])
    return result


def get_arguments() -> argparse.Namespace:
    versions = ["3"]
    parser = argparse.ArgumentParser()
    parser.add_argument('java_driver_git', help='folder with git repository of java-driver')
    parser.add_argument('scylla_install_dir',
                        help='folder with scylla installation, e.g. a checked out git scylla has been built', nargs='?',
                        default='')
    parser.add_argument('--versions', default=versions,
                        help='java-driver major versions to test, default={}'.format(','.join(versions)))
    parser.add_argument('--tests', default='*',
                        help='tests to pass to nosetests tool, default=tests.integration.standard')
    parser.add_argument('--scylla-version', help="relocatable scylla version to use",
                        default=os.environ.get('SCYLLA_VERSION', None))
    parser.add_argument('--version_size', help='The number of the latest versions that will test.'
                                               'The version is filtered by the major and minor values.'
                                               'For example, the user selects the 2 latest versions for version 4.'
                                               'The values to be returned are: 4.9.0-scylla-1 and 4.8.0-scylla-0',
                        type=int, default=2, nargs='?')
    arguments = parser.parse_args()
    versions = arguments.versions
    if isinstance(versions, str):
        versions = versions.split(',')

    arguments.versions = [(True, version) for version in
                          extract_n_latest_repo_tags(
                              repo_directory=arguments.java_driver_git, major_versions=versions,
                              latest_tags_size=arguments.version_size,
                              is_scylla_driver=True)]
    arguments.versions.extend([(False, version) for version in
                               extract_n_latest_repo_tags(
                                   repo_directory=arguments.java_driver_git, major_versions=versions,
                                   latest_tags_size=arguments.version_size,
                                   is_scylla_driver=False)])
    return arguments


if __name__ == '__main__':
    main(get_arguments())
