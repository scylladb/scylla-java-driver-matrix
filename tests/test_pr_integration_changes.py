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


def test_changed_apache_version_patch_expands_to_driver_matrix_entry():
    outputs = detect_changes(["versions/apache/4.19.3/patch"], repo_root=REPO_ROOT)

    assert outputs["version_count"] == "1"
    matrix = json.loads(outputs["version_matrix"])
    assert matrix["include"] == [
        {
            "driver_type": "apache",
            "driver_repository": "apache/cassandra-java-driver",
            "driver_version": "4.19.3",
            "driver_ref": "4.19.3",
        }
    ]


def test_changed_legacy_version_patch_maps_to_apache_repository(tmp_path):
    version_dir = tmp_path / "versions" / "datastax" / "4.19.3"
    version_dir.mkdir(parents=True)

    outputs = detect_changes(["versions/datastax/4.19.3/patch"], repo_root=tmp_path)

    assert outputs["version_count"] == "1"
    matrix = json.loads(outputs["version_matrix"])
    assert matrix["include"] == [
        {
            "driver_type": "datastax",
            "driver_repository": "apache/cassandra-java-driver",
            "driver_version": "4.19.3",
            "driver_ref": "4.19.3",
        }
    ]


def test_ccm_cache_restore_and_save_use_the_same_path():
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/integration-tests.yml").read_text())
    steps = workflow["jobs"]["integration-test"]["steps"]
    restore = next(step for step in steps if step.get("id") == "ccm-cache")
    save = next(step for step in steps if step.get("name") == "Save CCM download cache")

    assert restore["with"]["path"] == "~/.ccm/scylla-repository"
    assert save["with"]["path"] == restore["with"]["path"]


def test_integration_workflow_uploads_reports_after_failures():
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/integration-tests.yml").read_text())
    steps = workflow["jobs"]["integration-test"]["steps"]
    reports = next(step for step in steps if step.get("name") == "Upload integration test reports")
    ccm_logs = next(step for step in steps if step.get("name") == "Upload CCM logs")

    for step in (reports, ccm_logs):
        assert step["if"] == "${{ always() }}"
        assert step["uses"].startswith("actions/upload-artifact@")
        assert len(step["uses"].removeprefix("actions/upload-artifact@")) == 40

    assert "reports/" in reports["with"]["path"]
    assert "driver/integration-tests/target/failsafe-reports/" in reports["with"]["path"]
    assert "driver/driver-core/target/surefire-reports/" in reports["with"]["path"]
    assert "~/.ccm/*/node*/logs/**" in ccm_logs["with"]["path"]
