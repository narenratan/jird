"""Tests for jird.process."""
import subprocess

import pytest

from jird.process import run, run_async


@pytest.mark.parametrize("verbose", [True, False])
def test_run(verbose):
    run(["ls"], verbose=verbose)


@pytest.mark.parametrize("verbose", [True, False])
def test_run_bad_command(verbose):
    with pytest.raises(SystemExit) as e:
        run(["_not_a_command"], verbose=verbose)
    assert e.type == SystemExit
    assert e.value.code == 1


@pytest.mark.parametrize("verbose", [True, False])
def test_run_failing_command(verbose):
    with pytest.raises(subprocess.CalledProcessError):
        run(["ls", "/_not_a_dir"], verbose=verbose)


@pytest.mark.parametrize("verbose", [True, False])
def test_run_async(verbose):
    p = run_async(["ls"], verbose=verbose)
    p.kill()


@pytest.mark.parametrize("verbose", [True, False])
def test_run_async_bad_command(verbose):
    with pytest.raises(SystemExit) as e:
        run_async(["_not_a_command"], verbose=verbose)
    assert e.type == SystemExit
    assert e.value.code == 1
