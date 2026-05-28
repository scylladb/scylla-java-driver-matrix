import os
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_test_constructs_one_docker_command_with_workspace_env(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls_file = tmp_path / "docker.calls"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -e
            command="$1"
            printf '%q' "$1" >> "${FAKE_DOCKER_CALLS}"
            shift
            for arg in "$@"; do
              printf ' %q' "$arg" >> "${FAKE_DOCKER_CALLS}"
            done
            printf '\\n' >> "${FAKE_DOCKER_CALLS}"
            case "$command" in
              run)
                printf 'fake-container\\n'
                ;;
              logs)
                exit 0
                ;;
              wait)
                printf '0\\n'
                ;;
              rm)
                exit 0
                ;;
              *)
                echo "unexpected docker command: $*" >&2
                exit 2
                ;;
            esac
            """
        )
    )
    fake_docker.chmod(0o755)

    home = tmp_path / "home"
    home.mkdir()
    ccm_dir = tmp_path / "scylla-ccm"
    ccm_dir.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "HOME": str(home),
            "CCM_DIR": str(ccm_dir),
            "SCYLLA_JAVA_DRIVER_MATRIX_DIR": str(REPO_ROOT),
            "SCYLLA_VERSION": "2026.1.3",
            "FAKE_DOCKER_CALLS": str(calls_file),
        }
    )
    env.pop("WORKSPACE", None)

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/run_test.sh"), "python3", "-c", "print('ok')"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    calls = calls_file.read_text().splitlines()
    assert calls[0].startswith("run ")
    assert " -e WORKSPACE " in f" {calls[0]} "
    assert calls[1:] == ["logs fake-container -f", "wait fake-container", "rm -f fake-container"]
