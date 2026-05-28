import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.pr_integration_changes import detect_changes


def test_runner_changes_include_shell_wrapper_and_workflows():
    for changed_file in [
        "scripts/run_test.sh",
        "scripts/image",
        ".github/workflows/integration-tests.yml",
        ".github/workflows/pr-integration-tests.yml",
        "main.py",
    ]:
        outputs = detect_changes([changed_file], repo_root=REPO_ROOT)

        assert outputs["runner_changed"] == "true", changed_file


def test_changed_version_patch_expands_to_driver_matrix_entry():
    outputs = detect_changes(["versions/scylla/4.19.0.9/patch"], repo_root=REPO_ROOT)

    assert outputs["version_count"] == "1"
    matrix = json.loads(outputs["version_matrix"])
    assert matrix["include"] == [
        {
            "driver_type": "scylla",
            "driver_repository": "scylladb/java-driver",
            "driver_version": "4.19.0.9",
            "driver_ref": "4.19.0.9",
        }
    ]


def test_ccm_cache_restore_and_save_use_the_same_path():
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/integration-tests.yml").read_text())
    steps = workflow["jobs"]["integration-test"]["steps"]
    restore = next(step for step in steps if step.get("id") == "ccm-cache")
    save = next(step for step in steps if step.get("name") == "Save CCM download cache")

    assert restore["with"]["path"] == "~/.ccm/scylla-repository"
    assert save["with"]["path"] == restore["with"]["path"]
