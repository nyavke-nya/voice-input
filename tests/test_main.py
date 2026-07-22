"""Однопроцессный lock демона без запуска Qt и сокета."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pill.__main__ import _instance_lock


def test_instance_lock_is_exclusive_and_reusable():
    if os.name == "nt":
        return
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CACHE_HOME"] = d
        first = _instance_lock()
        assert first and _instance_lock() is False
        first.close()
        second = _instance_lock()
        assert second
        second.close()


def test_cli_help_and_unknown_option():
    root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    help_result = subprocess.run(
        [sys.executable, "-m", "pill", "--help"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "Usage: voice-input [OPTION]" in help_result.stdout
    assert "--diag" in help_result.stdout

    bad_result = subprocess.run(
        [sys.executable, "-m", "pill", "--unknown"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad_result.returncode == 2
    assert "Unknown option" in bad_result.stderr


if __name__ == "__main__":
    test_instance_lock_is_exclusive_and_reusable()
    test_cli_help_and_unknown_option()
    print("test_main OK")
