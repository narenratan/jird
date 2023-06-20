"""Tests that jird package has been installed successfully."""
import subprocess


def test_run():
    subprocess.run("jird", check=True)


def test_run_help(capfd):
    subprocess.run(["jird", "-h"], check=True)
    out, _ = capfd.readouterr()
    assert "Jird - a little language for music in just intonation" in out


def test_run_module():
    subprocess.run(["python3", "-m", "jird"], check=True)
