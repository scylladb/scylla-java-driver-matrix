from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import main


def test_main_does_not_import_email_sender_eagerly():
    assert "email_sender" not in vars(main)


def test_patch_only_succeeds_without_report_or_mail(monkeypatch):
    created = []

    class FakeRun:
        def __init__(self, **kwargs):
            created.append(kwargs)

        def run(self):
            return None

    monkeypatch.setattr(main.run, "Run", FakeRun)
    # email_sender must not be imported even when recipients are given.
    monkeypatch.setitem(sys.modules, "email_sender", None)

    with pytest.raises(SystemExit) as exc_info:
        main.main(
            java_driver_git="../java-driver",
            scylla_install_dir="",
            tests="",
            versions=["4.19.2.2"],
            driver_type="scylla",
            scylla_version=None,
            recipients=["qa@example.com"],
            patch_only=True,
        )

    assert exc_info.value.code == 0
    assert [kwargs["patch_only"] for kwargs in created] == [True]
