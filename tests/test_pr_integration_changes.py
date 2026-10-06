import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import pr_integration_changes
from scripts.pr_integration_changes import detect_changes


def all_tags_exist(repository, tag):
    return True


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
    outputs = detect_changes(["versions/scylla/4.19.0.9/patch"], repo_root=REPO_ROOT, tag_exists=all_tags_exist)

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
    outputs = detect_changes(["versions/apache/4.19.3/patch"], repo_root=REPO_ROOT, tag_exists=all_tags_exist)

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

    outputs = detect_changes(["versions/datastax/4.19.3/patch"], repo_root=tmp_path, tag_exists=all_tags_exist)

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


def test_untagged_version_is_excluded_from_matrix_and_reported_as_pending(tmp_path):
    for version in ("4.19.2.2", "4.19.2.3"):
        (tmp_path / "versions" / "scylla" / version).mkdir(parents=True)
    lookups = []

    def tag_exists(repository, tag):
        lookups.append((repository, tag))
        return tag != "4.19.2.3"

    outputs = detect_changes(
        ["versions/scylla/4.19.2.2/patch", "versions/scylla/4.19.2.3/patch"],
        repo_root=tmp_path,
        tag_exists=tag_exists,
    )

    assert sorted(lookups) == [("scylladb/java-driver", "4.19.2.2"), ("scylladb/java-driver", "4.19.2.3")]
    assert outputs["version_count"] == "1"
    assert outputs["pending_tags"] == "scylla/4.19.2.3"
    matrix = json.loads(outputs["version_matrix"])
    assert [entry["driver_version"] for entry in matrix["include"]] == ["4.19.2.2"]


def test_only_untagged_versions_fall_back_to_placeholder_matrix(tmp_path):
    (tmp_path / "versions" / "scylla" / "4.19.2.3").mkdir(parents=True)

    outputs = detect_changes(
        ["versions/scylla/4.19.2.3/patch"],
        repo_root=tmp_path,
        tag_exists=lambda repository, tag: False,
    )

    assert outputs["version_count"] == "0"
    assert outputs["pending_tags"] == "scylla/4.19.2.3"
    matrix = json.loads(outputs["version_matrix"])
    assert matrix["include"] == [
        {
            "driver_type": "none",
            "driver_repository": "none",
            "driver_version": "none",
            "driver_ref": "none",
        }
    ]


def test_no_pending_tags_when_all_versions_are_tagged():
    outputs = detect_changes(["versions/scylla/4.19.0.9/patch"], repo_root=REPO_ROOT, tag_exists=all_tags_exist)

    assert outputs["pending_tags"] == ""


def test_remote_tag_lookup_queries_exact_tag_ref(monkeypatch):
    calls = []

    def fake_check_output(cmd, **kwargs):
        calls.append(cmd)
        return "" if cmd[-1].endswith("4.19.2.3") else "abc123\trefs/tags/4.19.2.2\n"

    monkeypatch.setattr(pr_integration_changes.subprocess, "check_output", fake_check_output)

    assert pr_integration_changes.remote_tag_exists("scylladb/java-driver", "4.19.2.2") is True
    assert pr_integration_changes.remote_tag_exists("scylladb/java-driver", "4.19.2.3") is False
    assert calls[0] == [
        "git",
        "ls-remote",
        "--tags",
        "https://github.com/scylladb/java-driver.git",
        "refs/tags/4.19.2.2",
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


def test_integration_workflow_prior_scylla_version_has_fallback():
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/integration-tests.yml").read_text())
    steps = workflow["jobs"]["integration-test"]["steps"]
    select = next(step for step in steps if step.get("name") == "Select Scylla version query")
    fallback = next(step for step in steps if step.get("name") == "Resolve Scylla version fallback")

    assert "LAST.LAST.LAST-1" in select["run"]
    assert "LAST.LAST-1.LAST" in select["run"]
    assert "fallback_filters" in fallback["if"]
    assert "fallback_filters" in fallback["with"]["filters"]


def test_pr_workflow_reports_pending_tags_as_notice():
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/pr-integration-tests.yml").read_text())
    changes = workflow["jobs"]["changes"]
    notice = next(step for step in changes["steps"] if step.get("name") == "Report untagged driver versions")

    assert changes["outputs"]["pending_tags"] == "${{ steps.detect.outputs.pending_tags }}"
    assert notice["if"] == "${{ steps.detect.outputs.pending_tags != '' }}"
    assert "::notice::" in notice["run"]
    assert "${PENDING_TAGS}" in notice["run"]
