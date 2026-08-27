from __future__ import annotations

import json
import uuid
from pathlib import Path


DEFAULT_VERSIONS_DIR = Path("versions") / "apache"


def as_bool(value: str) -> bool:
    """Read a GitHub Actions boolean. An unset cache-hit output arrives as an empty string."""
    return value.strip().lower() == "true"


def write_outputs(outputs: dict[str, str], path: str) -> None:
    """Append to $GITHUB_OUTPUT with the delimited form, safe for a value containing a newline.

    driver_ref can come straight from a workflow_dispatch input, so a plain `name=value` line would
    let an embedded newline forge extra output lines.
    """
    with open(path, "a", encoding="utf-8") as handle:
        for name, value in outputs.items():
            delimiter = f"ghadelim_{uuid.uuid4().hex}"
            handle.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def pick(input_value: str, latest_json: str, kind: str) -> str:
    """Explicit input wins, otherwise take the first resolved version.

    Same shape as the Normalize inputs step in integration-tests.yml.
    """
    if input_value:
        return input_value
    try:
        latest = json.loads(latest_json or "[]")
    except json.JSONDecodeError as error:
        raise SystemExit(f"Unable to resolve {kind}: {error}") from error
    if not latest:
        raise SystemExit(f"Unable to resolve {kind}")
    return latest[0]


def as_tuple(name: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in name.split("."))
    except ValueError:
        return None


def fallback_for(tag: str, versions_dir: Path = DEFAULT_VERSIONS_DIR) -> str:
    """The directory Run.version_folder would resolve to: newest defined version <= tag."""
    target = as_tuple(tag)
    if target is None:
        return ""
    candidates = []
    for path in Path(versions_dir).iterdir():
        if not path.is_dir():
            continue
        parsed = as_tuple(path.name)
        if parsed is not None and parsed <= target:
            candidates.append((parsed, path.name))
    return max(candidates)[1] if candidates else ""


def resolve(
    driver_ref_input: str,
    latest_json: str,
    versions_dir: Path = DEFAULT_VERSIONS_DIR,
) -> dict[str, str]:
    """The tag to consider, and whether it is onboarded.

    Split from decide() because the marker cache key contains the tag, so the lookup step sits
    between the two.
    """
    driver_ref = pick(driver_ref_input, latest_json, "upstream release tag")
    return {
        "driver_ref": driver_ref,
        "forced": str(bool(driver_ref_input)).lower(),
        # The same exact-match test Run.version_folder makes before it starts falling back.
        "has_directory": str((Path(versions_dir) / driver_ref).is_dir()).lower(),
    }


def decide(forced: bool, has_directory: bool, already_tested: bool) -> dict[str, str]:
    """An explicit dispatch always runs; otherwise a tag runs once, while it has no directory."""
    return {"should_run": str(forced or not (has_directory or already_tested)).lower()}


def summarize(
    driver_ref: str,
    forced: bool,
    has_directory: bool,
    already_tested: bool,
    versions_dir: Path = DEFAULT_VERSIONS_DIR,
) -> str:
    label = Path(versions_dir).as_posix()
    heading = "Requested" if forced else "Newest"
    lines = [f"### {heading} `apache` release tag: `{driver_ref}`", ""]
    # Reuses decide()'s formula rather than re-deriving it, so the wording can't drift from should_run.
    should_run = decide(forced, has_directory, already_tested)["should_run"] == "true"

    if has_directory and not should_run:
        lines.append(f"`{label}/{driver_ref}/` exists — nothing to do.")
    elif has_directory:
        lines.append(f"`{label}/{driver_ref}/` exists; re-testing it on request.")
    elif not should_run:
        lines.append(
            f"No `{label}/{driver_ref}/` directory, and the integration workflow has already run "
            f"against this tag. Nothing to do until the directory is added; dispatch this workflow "
            f"with `driver_ref: {driver_ref}` to test it again."
        )
    else:
        fallback = fallback_for(driver_ref, versions_dir) or "nothing"
        lines.append(
            f"No `{label}/{driver_ref}/` directory, so the matrix would patch this tag with "
            f"`{label}/{fallback}/`. Running the integration workflow against `{driver_ref}` to "
            f"find out whether that still works."
        )

    return "\n".join(lines) + "\n"
