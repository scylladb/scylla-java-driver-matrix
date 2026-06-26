from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_datastax_patches_use_current_udf_feature_flag():
    for patch_file in (REPO_ROOT / "versions" / "datastax").glob("*/patch"):
        assert "experimental:true" not in patch_file.read_text(encoding="utf-8"), patch_file
