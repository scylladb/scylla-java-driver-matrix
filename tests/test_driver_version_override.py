import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import main as matrix_main


def test_explicit_driver_version_uses_untagged_ref_without_resolving_tag(monkeypatch):
    observed = {}

    class FakeRun:
        def __init__(self, **kwargs):
            observed.update(kwargs)

        def run(self):
            return None

    monkeypatch.setattr(matrix_main.run, "Run", FakeRun)
    monkeypatch.setattr(matrix_main, "resolve_driver_version", lambda *_: pytest.fail("tag lookup is not needed"))

    with pytest.raises(SystemExit) as result:
        matrix_main.main(
            java_driver_git="driver",
            scylla_install_dir="",
            tests="",
            versions=[],
            driver_type="scylla",
            scylla_version="2026.1.3",
            recipients=None,
            patch_only=True,
            checkout_ref="candidate-sha",
            driver_version="4.19.2.3",
        )

    assert result.value.code == 0
    assert observed["tag"] == "4.19.2.3"
    assert observed["checkout_ref"] == "candidate-sha"
