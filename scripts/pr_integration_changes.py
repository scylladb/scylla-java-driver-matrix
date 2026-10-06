from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable, Iterable


REPOSITORIES = {
    "apache": "apache/cassandra-java-driver",
    "datastax": "apache/cassandra-java-driver",
    "scylla": "scylladb/java-driver",
}

IMAGE_SOURCE_PATHS = {"scripts/Dockerfile", "scripts/requirements.txt"}

RUNNER_PATHS = {
    ".github/workflows/integration-tests.yml",
    ".github/workflows/pr-integration-tests.yml",
    "scripts/run_test.sh",
    "scripts/image",
    *IMAGE_SOURCE_PATHS,
}


def is_runner_path(filename: str) -> bool:
    return filename.endswith(".py") or filename in RUNNER_PATHS


def remote_tag_exists(repository: str, tag: str) -> bool:
    output = subprocess.check_output(
        ["git", "ls-remote", "--tags", f"https://github.com/{repository}.git", f"refs/tags/{tag}"],
        text=True,
    )
    return bool(output.strip())


def detect_changes(
    changed_files: Iterable[str],
    repo_root: Path = Path("."),
    tag_exists: Callable[[str, str], bool] | None = None,
) -> dict[str, str]:
    repo_root = Path(repo_root)
    tag_exists = tag_exists or remote_tag_exists
    changed_files = list(changed_files)

    version_dirs = set()
    for filename in changed_files:
        parts = filename.split("/")
        if len(parts) >= 3 and parts[0] == "versions":
            path = repo_root / parts[0] / parts[1] / parts[2]
            if path.is_dir():
                version_dirs.add((parts[1], parts[2]))

    version_matrix = []
    pending_tags = []
    for driver_type, version in sorted(version_dirs):
        repository = REPOSITORIES.get(driver_type)
        if repository is None:
            raise SystemExit(f"Unsupported driver type in versions/{driver_type}/{version}")
        # A patch for a release that is not tagged yet (e.g. an aborted release re-dispatched with
        # this PR as matrix-ref) cannot be checked out here; the release run validates it instead.
        if not tag_exists(repository, version):
            pending_tags.append(f"{driver_type}/{version}")
            continue
        version_matrix.append(
            {
                "driver_type": driver_type,
                "driver_repository": repository,
                "driver_version": version,
                "driver_ref": version,
            }
        )

    runner_changed = any(is_runner_path(filename) for filename in changed_files)
    scripts_image_source_changed = any(filename in IMAGE_SOURCE_PATHS for filename in changed_files)
    scripts_image_changed = "scripts/image" in changed_files and (repo_root / "scripts/image").is_file()

    # GitHub validates the matrix expression even when the job is skipped.
    matrix = {
        "include": version_matrix
        or [
            {
                "driver_type": "none",
                "driver_repository": "none",
                "driver_version": "none",
                "driver_ref": "none",
            }
        ]
    }

    return {
        "runner_changed": str(runner_changed).lower(),
        "scripts_image_source_changed": str(scripts_image_source_changed).lower(),
        "scripts_image_changed": str(scripts_image_changed).lower(),
        "version_count": str(len(version_matrix)),
        "version_matrix": json.dumps(matrix, separators=(",", ":")),
        "pending_tags": ",".join(pending_tags),
    }
