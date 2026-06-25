from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from run import load_ignore_tests


def test_repository_ignore_files_are_valid():
    for ignore_file in sorted((REPO_ROOT / "versions").glob("*/*/ignore.yaml")):
        load_ignore_tests(ignore_file)


def test_load_ignore_tests_rejects_unquoted_method_selector(tmp_path):
    ignore_file = tmp_path / "ignore.yaml"
    ignore_file.write_text(
        """\
tests:
  - DriverIT #should_fail
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="entries containing '#' must be quoted"):
        load_ignore_tests(ignore_file)


def test_load_ignore_tests_rejects_empty_and_duplicate_entries(tmp_path):
    ignore_file = tmp_path / "ignore.yaml"
    ignore_file.write_text(
        """\
tests:
  - DriverIT
  -
  - DriverIT
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="empty or non-string entries.*duplicate entries: DriverIT"):
        load_ignore_tests(ignore_file)
