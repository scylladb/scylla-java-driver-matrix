import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.upstream_release_watch import decide, fallback_for, resolve, summarize


@pytest.fixture(name="versions_dir")
def fixture_versions_dir(tmp_path):
    versions_dir = tmp_path / "versions" / "apache"
    for version in ("4.19.1", "4.19.2", "4.19.3"):
        (versions_dir / version).mkdir(parents=True)
    return versions_dir


def test_resolve_prefers_the_dispatched_tag_over_the_newest_release(versions_dir):
    outputs = resolve("4.19.3", '["4.19.9"]', versions_dir=versions_dir)

    assert outputs == {"driver_ref": "4.19.3", "forced": "true", "has_directory": "true"}


def test_resolve_takes_the_newest_release_when_no_tag_is_dispatched(versions_dir):
    outputs = resolve("", '["4.19.9"]', versions_dir=versions_dir)

    assert outputs == {"driver_ref": "4.19.9", "forced": "false", "has_directory": "false"}


def test_resolve_fails_when_no_tag_resolves(versions_dir):
    for latest in ("", "[]"):
        with pytest.raises(SystemExit):
            resolve("", latest, versions_dir=versions_dir)


def test_resolve_fails_cleanly_on_malformed_json(versions_dir):
    with pytest.raises(SystemExit):
        resolve("", "not json", versions_dir=versions_dir)


def test_onboarded_tag_does_not_run():
    assert decide(forced=False, has_directory=True, already_tested=False)["should_run"] == "false"


def test_tag_without_a_version_directory_runs_once():
    assert decide(forced=False, has_directory=False, already_tested=False)["should_run"] == "true"
    assert decide(forced=False, has_directory=False, already_tested=True)["should_run"] == "false"


def test_a_dispatched_tag_always_runs():
    for has_directory in (True, False):
        for already_tested in (True, False):
            outputs = decide(forced=True, has_directory=has_directory, already_tested=already_tested)

            assert outputs["should_run"] == "true", (has_directory, already_tested)


def test_fallback_names_the_newest_directory_at_or_below_the_tag(versions_dir):
    assert fallback_for("4.19.9", versions_dir=versions_dir) == "4.19.3"
    assert fallback_for("4.19.2", versions_dir=versions_dir) == "4.19.2"


def test_fallback_is_empty_when_nothing_applies(versions_dir):
    assert fallback_for("4.18.0", versions_dir=versions_dir) == ""
    assert fallback_for("4.19.3-rc1", versions_dir=versions_dir) == ""


def test_summary_names_the_directory_the_matrix_would_patch_with(versions_dir):
    summary = summarize(
        "4.19.9", forced=False, has_directory=False, already_tested=False, versions_dir=versions_dir
    )

    assert f"{versions_dir.as_posix()}/4.19.3/" in summary


def test_summary_points_at_a_dispatch_once_the_tag_has_been_tested(versions_dir):
    summary = summarize(
        "4.19.9", forced=False, has_directory=False, already_tested=True, versions_dir=versions_dir
    )

    assert "driver_ref: 4.19.9" in summary
    assert "4.19.3" not in summary


def test_watch_workflow_never_runs_integration_from_a_pull_request():
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/upstream-release-watch.yml").read_text()
    )

    assert "github.event_name != 'pull_request'" in workflow["jobs"]["integration"]["if"]


def test_watch_workflow_marks_a_tag_only_after_a_conclusive_run():
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/upstream-release-watch.yml").read_text()
    )
    detect = workflow["jobs"]["detect"]["steps"]
    lookup = next(step for step in detect if step.get("id") == "marker")
    save = next(
        step
        for step in workflow["jobs"]["mark-tested"]["steps"]
        if step.get("name") == "Save the tested marker"
    )

    # The two keys name the same tag through different contexts: steps.resolve inside detect,
    # needs.detect from a separate job.
    prefix = "upstream-release-tested-apache-"
    assert lookup["with"]["key"] == f"{prefix}${{{{ steps.resolve.outputs.driver_ref }}}}"
    assert save["with"]["key"] == f"{prefix}${{{{ needs.detect.outputs.driver_ref }}}}"
    assert lookup["with"]["lookup-only"] is True
    assert lookup["with"]["path"] == save["with"]["path"]
    assert "needs.integration.result == 'success'" in workflow["jobs"]["mark-tested"]["if"]
    assert "needs.integration.result == 'failure'" in workflow["jobs"]["mark-tested"]["if"]
