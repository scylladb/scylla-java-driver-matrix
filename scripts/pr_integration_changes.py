from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


REPOSITORIES = {
    "apache": "apache/cassandra-java-driver",
    "datastax": "apache/cassandra-java-driver",
    "scylla": "scylladb/java-driver",
}

IMAGE_SOURCE_PATHS = {"scripts/Dockerfile", "scripts/requirements.txt"}

RUNNER_PATHS = {
    ".github/workflows/integration-tests.yml",
    ".github/workflows/release-integration-tests.yml",
    ".github/workflows/pr-integration-tests.yml",
    "scripts/run_test.sh",
    "scripts/image",
    *IMAGE_SOURCE_PATHS,
}


def is_runner_path(filename: str) -> bool:
    return filename.endswith(".py") or filename in RUNNER_PATHS


def detect_changes(changed_files: Iterable[str], repo_root: Path = Path(".")) -> dict[str, str]:
    repo_root = Path(repo_root)
    changed_files = list(changed_files)

    version_dirs = set()
    for filename in changed_files:
        parts = filename.split("/")
        if len(parts) >= 3 and parts[0] == "versions":
            path = repo_root / parts[0] / parts[1] / parts[2]
            if path.is_dir():
                version_dirs.add((parts[1], parts[2]))

    version_matrix = []
    for driver_type, version in sorted(version_dirs):
        repository = REPOSITORIES.get(driver_type)
        if repository is None:
            raise SystemExit(f"Unsupported driver type in versions/{driver_type}/{version}")
        candidate_ref_file = path / "checkout-ref"
        candidate_ref = candidate_ref_file.read_text().strip() if candidate_ref_file.is_file() else ""
        if candidate_ref_file.is_file() and not candidate_ref:
            raise SystemExit(f"Empty checkout-ref in {path}")
        scylla_versions = ("LATEST", "PRIOR", "LTS-LATEST", "LTS-PRIOR") if candidate_ref and driver_type == "scylla" else ("LATEST",)
        for scylla_version in scylla_versions:
            entry = {
                "driver_type": driver_type,
                "driver_repository": repository,
                "driver_version": version,
                "driver_ref": candidate_ref or version,
            }
            if candidate_ref:
                entry["scylla_version"] = scylla_version
            version_matrix.append(entry)

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
    }
