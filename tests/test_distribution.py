import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _copy_distribution_subset(destination: Path) -> None:
    for name in ["server.py", "smoke_test.py", "README.md", "requirements.txt", "pyproject.toml"]:
        shutil.copy2(ROOT / name, destination / name)

    for name in ["apiproxy", "utils", "docs", "scripts"]:
        source = ROOT / name
        if source.exists():
            shutil.copytree(source, destination / name)


def test_distribution_clone_imports_without_external_checkout(tmp_path: Path) -> None:
    _copy_distribution_subset(tmp_path)

    env = os.environ.copy()
    env.pop("DOUYIN_PROJECT_ROOT", None)
    env["PYTHONPATH"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import server; "
                "print('IMPORT_OK'); "
                "print(server.get_task_status('missing')['error'])"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout
    assert "任务 missing 不存在" in result.stdout


def test_distribution_clone_exposes_packaging_metadata_and_main(tmp_path: Path) -> None:
    _copy_distribution_subset(tmp_path)

    env = os.environ.copy()
    env.pop("DOUYIN_PROJECT_ROOT", None)
    env["PYTHONPATH"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "import server; "
                "print(Path('pyproject.toml').exists()); "
                "print(callable(server.main))"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "True\nTrue" in result.stdout


def test_distribution_clone_installs_console_script_with_minimal_startup_deps(tmp_path: Path) -> None:
    _copy_distribution_subset(tmp_path)

    venv_path = tmp_path / ".venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

    python_bin = venv_path / "bin" / "python"
    pip_bin = venv_path / "bin" / "pip"
    cli_bin = venv_path / "bin" / "douyin-mcp-server"

    subprocess.run(
        [str(pip_bin), "install", "--no-deps", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [
            str(pip_bin),
            "install",
            "mcp[cli]>=1.0.0",
            "requests>=2.28.0",
            "rich>=13.7.0",
            "tqdm>=4.66.0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [str(cli_bin), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert python_bin.exists()
    assert result.returncode == 0, result.stderr
    assert "Douyin MCP Server" in result.stdout


def test_distribution_clone_exposes_smoke_script_help(tmp_path: Path) -> None:
    _copy_distribution_subset(tmp_path)

    result = subprocess.run(
        [sys.executable, "scripts/smoke_test.py", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Douyin MCP smoke test" in result.stdout
