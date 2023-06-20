"""Utilities for running commands in subprocesses."""
import logging
import subprocess
import sys
from pathlib import Path
from typing import Sequence, Union

logger = logging.getLogger(__name__)


def run(command_parts: Sequence[Union[str, Path]], verbose: bool) -> None:
    """
    Run command in subprocess.

    Blocks until the command returns.

    Parameters
    ----------
    command_parts : list of str or Path
        Pieces of the command to run.
    verbose : bool
        Whether to print output from the command to the console.

    Raises
    ------
    subprocess.CalledProcessError
        If process exits nonzero. Even if not in verbose mode the command's
        stdout and stderr are printed to help debugging.
    """
    logger.info("Running '%s'", " ".join(str(x) for x in command_parts))
    error_msg = f"Could not find {command_parts[0]}. Check that {command_parts[0]} is installed."
    if verbose:
        try:
            subprocess.run(
                command_parts,
                check=True,
            )
        except FileNotFoundError:
            print(error_msg)
            sys.exit(1)
    else:
        try:
            subprocess.run(
                command_parts,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(e.stdout.decode())
            print(e.stderr.decode())
            raise
        except FileNotFoundError:
            print(error_msg)
            sys.exit(1)


def run_async(
    command_parts: Sequence[Union[str, Path]], verbose: bool
) -> "subprocess.Popen[bytes]":
    """
    Run command in subprocess without blocking.

    Returns immediately after running the command.

    Parameters
    ----------
    command_parts : list of str or Path
        Pieces of the command to run.
    verbose : bool
        Whether to print output from the command to the console.

    Returns
    -------
    subprocess.Popen
        Process that has been started.
    """
    logger.info("Running '%s'", " ".join(str(x) for x in command_parts))
    error_msg = f"Could not find {command_parts[0]}. Check that {command_parts[0]} is installed."
    if verbose:
        try:
            p = subprocess.Popen(command_parts)
        except FileNotFoundError:
            print(error_msg)
            sys.exit(1)
    else:
        try:
            p = subprocess.Popen(  # pylint: disable=R1732
                command_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except FileNotFoundError:
            print(error_msg)
            sys.exit(1)
    return p
