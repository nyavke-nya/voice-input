"""Dry-run installer detection is side-effect free across common desktops."""
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _dry_run(**updates):
    env = os.environ.copy()
    for name in (
        "HYPRLAND_INSTANCE_SIGNATURE", "SWAYSOCK", "I3SOCK",
        "XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION",
        "WAYLAND_DISPLAY", "DISPLAY", "XDG_SESSION_TYPE",
    ):
        env.pop(name, None)
    env.update(updates)
    return subprocess.run(
        [str(ROOT / "install.sh"), "--dry-run"], cwd=ROOT, env=env,
        capture_output=True, text=True, check=False,
    )


def test_desktop_detection_matrix():
    cases = (
        ({"HYPRLAND_INSTANCE_SIGNATURE": "x", "WAYLAND_DISPLAY": "wayland-1"}, "hyprland", "wayland"),
        ({"SWAYSOCK": "/tmp/sway", "XDG_SESSION_TYPE": "wayland"}, "sway", "wayland"),
        ({"I3SOCK": "/tmp/i3", "DISPLAY": ":0"}, "i3", "x11"),
        ({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME", "XDG_SESSION_TYPE": "wayland"}, "gnome", "wayland"),
        ({"XDG_CURRENT_DESKTOP": "X-Cinnamon", "DISPLAY": ":0"}, "cinnamon", "x11"),
        ({"XDG_CURRENT_DESKTOP": "XFCE", "DISPLAY": ":0"}, "xfce", "x11"),
        ({"XDG_CURRENT_DESKTOP": "KDE", "WAYLAND_DISPLAY": "wayland-0"}, "kde", "wayland"),
    )
    for env, desktop, session in cases:
        result = _dry_run(**env)
        assert result.returncode == 0, result.stderr
        assert f"Desktop/WM:  {desktop}" in result.stdout
        assert f"Session:     {session}" in result.stdout
        assert "не изменены" in result.stdout and "no files" in result.stdout


def test_uninstall_dry_run_and_bad_argument():
    result = subprocess.run(
        [str(ROOT / "uninstall.sh"), "--dry-run"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0 and "Nothing was removed" in result.stdout
    bad = subprocess.run(
        [str(ROOT / "install.sh"), "--definitely-invalid"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    assert bad.returncode == 2


def test_installed_command_resolves_repository_symlink():
    with tempfile.TemporaryDirectory() as temp:
        link = Path(temp) / "voice-input"
        link.symlink_to(ROOT / "voice-input")
        result = subprocess.run(
            [str(link), "--diag"], cwd=temp,
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "config:" in result.stdout and "injection:" in result.stdout


def test_run_script_forwards_cli_arguments():
    result = subprocess.run(
        [str(ROOT / "run.sh"), "--help"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage: voice-input [OPTION]" in result.stdout


if __name__ == "__main__":
    test_desktop_detection_matrix()
    test_uninstall_dry_run_and_bad_argument()
    test_installed_command_resolves_repository_symlink()
    test_run_script_forwards_cli_arguments()
    print("test_installer OK")
