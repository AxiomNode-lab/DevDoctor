from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"
VERSION = "1.2.0rc1"


def _write_fake_python(fake_bin: Path) -> None:
    fake_bin.mkdir(parents=True)
    python3 = fake_bin / "python3"
    python3.write_text(
        r"""#!/bin/sh
set -eu

if [ "${1:-}" = "-c" ]; then
  echo 1
  exit 0
fi

if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then
  if [ "${DEVDOCTOR_FAKE_VENV_FAIL:-0}" = "1" ]; then
    exit 1
  fi
  target="$3"
  mkdir -p "$target/bin"
  cat > "$target/bin/python" <<'PYTHON'
#!/bin/sh
set -eu
BIN_DIR="$(dirname "$0")"

if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pip" ]; then
  cat > "$BIN_DIR/devdoctor" <<'DEVDOCTOR'
#!/bin/sh
case "$0" in
  */envs/*)
    echo "DevDoctor 1.2.0rc1"
    exit 0
    ;;
esac
if [ "${DEVDOCTOR_FAKE_FAIL_FINAL:-0}" = "1" ]; then
  exit 42
fi
echo "DevDoctor 1.2.0rc1"
DEVDOCTOR
  chmod +x "$BIN_DIR/devdoctor"
  exit 0
fi

if [ "${1:-}" = "-c" ]; then
  echo "1.2.0rc1"
  exit 0
fi

exit 2
PYTHON
  chmod +x "$target/bin/python"
  exit 0
fi

exit 2
""",
        encoding="utf-8",
    )
    python3.chmod(0o755)


def _installer_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    _write_fake_python(fake_bin)

    data_home = tmp_path / "data"
    bin_home = tmp_path / "bin"
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_DATA_HOME": str(data_home),
            "XDG_BIN_HOME": str(bin_home),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    return env, data_home, bin_home


def _run_installer(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            "sh",
            str(INSTALLER),
            "--source",
            "pypi",
            "--version",
            VERSION,
            "--yes",
        ),
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_installer_venv_preflight_fails_before_devdoctor_state_is_created(
    tmp_path: Path,
) -> None:
    env, data_home, bin_home = _installer_env(tmp_path)
    env["DEVDOCTOR_FAKE_VENV_FAIL"] = "1"

    result = _run_installer(env)

    assert result.returncode != 0
    assert "python3-venv" in result.stderr
    assert not (data_home / "devdoctor").exists()
    assert not (bin_home / "devdoctor").exists()


def test_installer_activates_immutable_environment_without_moving_it(tmp_path: Path) -> None:
    env, data_home, bin_home = _installer_env(tmp_path)

    result = _run_installer(env)

    envs = list((data_home / "devdoctor" / "envs").iterdir())
    assert result.returncode == 0, result.stderr
    assert len(envs) == 1
    installed_env = envs[0]
    command = installed_env / "bin" / "devdoctor"
    version_link = data_home / "devdoctor" / "versions" / VERSION
    link = bin_home / "devdoctor"
    assert command.is_file()
    assert version_link.is_symlink()
    assert version_link.readlink() == installed_env
    assert link.is_symlink()
    assert link.readlink() == command
    assert f"Environment: {installed_env}" in result.stdout


def test_installer_restores_previous_symlinks_on_activation_failure(tmp_path: Path) -> None:
    env, data_home, bin_home = _installer_env(tmp_path)
    base = data_home / "devdoctor"
    old_env = base / "envs" / "old-env"
    old_env.mkdir(parents=True)
    versions = base / "versions"
    versions.mkdir(parents=True)
    version_link = versions / VERSION
    version_link.symlink_to(old_env)

    bin_home.mkdir(parents=True)
    link = bin_home / "devdoctor"
    old_target = old_env / "bin" / "devdoctor"
    link.symlink_to(old_target)
    env["DEVDOCTOR_FAKE_FAIL_FINAL"] = "1"

    result = _run_installer(env)

    assert result.returncode != 0
    assert link.is_symlink()
    assert link.readlink() == old_target
    assert version_link.is_symlink()
    assert version_link.readlink() == old_env
    assert list((base / "envs").iterdir()) == [old_env]
    assert not (base / ".install.lock").exists()


def test_installer_refuses_concurrent_activation_lock(tmp_path: Path) -> None:
    env, data_home, _ = _installer_env(tmp_path)
    lock = data_home / "devdoctor" / ".install.lock"
    lock.mkdir(parents=True)

    result = _run_installer(env)

    assert result.returncode != 0
    assert "already active" in result.stderr
    assert lock.exists()


def _run_installer_args(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("sh", str(INSTALLER), *args),
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_installer_git_source_installs_main_from_the_repository(tmp_path: Path) -> None:
    # Until a PyPI release exists this is the only source that can succeed.
    env, _data_home, bin_home = _installer_env(tmp_path)

    result = _run_installer_args(env, "--source", "git", "--yes")

    assert result.returncode == 0, result.stderr
    assert "package: git+https://github.com/AxiomNode-lab/DevDoctor.git@main" in result.stdout
    assert (bin_home / "devdoctor").is_symlink()


def test_installer_git_source_with_version_pins_the_release_tag(tmp_path: Path) -> None:
    env, _data_home, _bin_home = _installer_env(tmp_path)

    result = _run_installer_args(env, "--source", "git", "--version", VERSION, "--yes")

    assert result.returncode == 0, result.stderr
    assert f"@v{VERSION}" in result.stdout


def test_installer_git_source_requires_a_git_executable(tmp_path: Path) -> None:
    env, _data_home, _bin_home = _installer_env(tmp_path)
    fake_git = tmp_path / "fake-bin" / "git"
    fake_git.write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
    fake_git.chmod(0o755)

    result = _run_installer_args(env, "--source", "git", "--yes")

    assert result.returncode != 0
    assert "git is required" in result.stderr
