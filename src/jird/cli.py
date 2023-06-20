"""Command line interface for Jird."""
import json
import logging
import logging.config

# queue imported so compiliation with nuitka works
import queue  # noqa: F401, pylint: disable=W0611
import random
from argparse import ArgumentParser, Namespace
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import jird.midi
from jird.config import Config
from jird.core import (
    Note,
    Piece,
    parse,
    print_interval_table,
    print_music,
    temper,
)
from jird.lilypond import write_lilypond_music
from jird.parser import LarkError
from jird.scala import write_scale

# Use import below if using lark itself rather than standalone parser
# from lark import LarkError

logger = logging.getLogger(__name__)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "level": "DEBUG",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "jird": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "__main__": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
    },
}


def get_parser() -> ArgumentParser:
    """Build parser for running jird command line interface."""
    parser = ArgumentParser(
        description="Jird - a little language for music in just intonation."
    )

    parser.add_argument("files", nargs="*", help="Text files containing music to play")
    parser.add_argument("-t", type=float, help="Basic time in seconds")
    parser.add_argument("-f", type=float, help="Basic frequency in Hertz")
    parser.add_argument(
        "--tuning_method",
        type=str,
        help="Method for tuning notes to desired frequencies",
    )
    parser.add_argument(
        "-e",
        "--edo",
        type=int,
        help="Temper with given number of equal divisions of the octave",
    )
    parser.add_argument(
        "--pitch_bend_range",
        type=int,
        help="Max pitch bend in semitones when using pitch bend tuning",
    )
    parser.add_argument(
        "-s",
        "--synth",
        type=str,
        help="Synth to use for playback",
    )
    parser.add_argument("--train", help="File containing ratios for ear training")
    parser.add_argument("-n", "--notes", action="store_true", help="Print notes")
    parser.add_argument(
        "-p",
        "--programs",
        type=str,
        help="Comma-separated list of midi programs to use for playing midi",
    )
    parser.add_argument(
        "-l",
        "--lilypond",
        action="store_true",
        help="Write out lilypond representation of music",
    )
    parser.add_argument(
        "--scale",
        action="store_true",
        help="Write out Scala scl file for scale in music",
    )
    parser.add_argument(
        "-m", "--midi", action="store_true", help="Just write midi file"
    )
    parser.add_argument(
        "--soundfont",
        type=str,
        help="Path to soundfont to use with fluidsynth",
    )
    parser.add_argument(
        "-i",
        "--instrument",
        type=str,
        help="Path to patch (fxp or xiz) to use with Surge XT or ZynAddSubFX",
    )
    parser.add_argument("-c", "--config", help="Config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show logs")
    return parser


def print_banner() -> None:
    """Print welcome banner."""
    print("\nJIRD - It's just intonation\n")


def print_goodbye() -> None:
    """Print closing message."""
    print("Thank you for using Jird!")


ACTIONS: Dict[str, Callable[[Piece], None]] = {
    "n": print_music,
    "t": print_interval_table,
}
"""
Actions available in interactive mode.
If the key of ACTIONS dict is in the input text, the value (a function)
is called on the parsed music.
"""


def interactive_mode_repl(
    transform: Callable[[Piece], Piece],
    play: Callable[[Piece], None],
) -> None:
    """
    REPL (Read-Eval-*Play* Loop) for interactively playing music.

    Parameters
    ----------
    transform : callable Piece -> Piece
        Function to apply to music before playing. Allows tempering music for example.
    play : callable Piece -> None
        Function to play music with.
    """
    try:
        while True:
            text = input("  ")
            if not text:
                continue

            try:
                music = transform(parse(text))
                for k, v in ACTIONS.items():
                    if k in text:
                        v(music)

                # Until recently https://github.com/FluidSynth/fluidsynth/pull/1159
                # fluidsynth would cut off playback abruptly. Until this change is
                # released just append a one beat rest in interactive mode.
                music = _append_rest(music)

                play(music)
            except LarkError as e:
                # Do not crash the interpreter on a syntax error
                print(e)
    except EOFError:
        # Exit on Ctrl-D
        print_goodbye()


REST = Note(frequency=Fraction(0), duration=Fraction(1))


def _append_rest(music: Piece) -> Piece:
    """Add rest at end of music."""
    return tuple([*part, REST] for part in music)


def ear_training(
    training_input: List[str],
    transform: Callable[[Piece], Piece],
    play: Callable[[Piece], None],
) -> None:
    """
    Ear training mode.

    Play intervals randomly selected from `training_input` and ask user to
    input the corresponding ratio. Print correct ratio if answer is wrong.

    Parameters
    ----------
    training_input : list of str
        List of ratios to choose from for ear training. Expected to be just the
        ratios, e.g. "7/6" rather than "<1 7/6>:1".
    transform : callable Piece -> Piece
        Function to apply to music before playing.
    play : callable Piece -> None
        Function to play music with.
    """
    total = 0
    correct = 0
    sounds = [(x, parse(f"<1 {x}>:8 0:2")) for x in training_input]
    try:
        while True:
            string, sound = random.choice(sounds)
            play(transform(sound))
            guess = input("? ")
            total += 1
            if guess != string:
                print(f"\n{string}\n")
            else:
                correct += 1
    except EOFError:
        # Exit on Ctrl-D
        print(f"Score: {correct}/{total}, {100 * correct / max(total, 1):.1f}%")
        print_goodbye()


def top_level(args: Namespace) -> None:
    """
    Top level function for running command line interface.

    Uses same transform and play functions in all modes, so e.g. tempering
    music automatically works in interactive, ear training, and file
    playback modes.

    Parameters
    ----------
    args : Namespace
        Command line arguments.
    """
    # Options can come from config file or command line args
    # Command line arguments override config values if both are used
    config_file_dict = {}
    if args.config is not None:
        with open(args.config, encoding="utf8") as f:
            config_file_dict = json.load(f)
    args_dict = {k: v for k, v in vars(args).items() if v is not None}
    config = Config.from_dict({**config_file_dict, **args_dict})

    if config.verbose:
        logging.config.dictConfig(LOGGING_CONFIG)

    # Define transform and play functions to be used in all interpreter modes

    transform = partial(temper, edo=config.edo)

    if args.midi:
        play: Callable[..., Any] = partial(
            jird.midi.music_to_midi_file,
            config=config,
        )
    else:
        play = partial(
            jird.midi.play_music,
            config=config,
        )

    print_banner()
    if args.train:
        with open(args.train, "r", encoding="utf8") as f:
            ratios = f.read().splitlines()
        ear_training(ratios, transform, play)
    elif not args.files:
        interactive_mode_repl(transform, play)
    else:
        for file in args.files:
            _handle_file(file, args, config, transform, play)


def _handle_file(
    file: str,
    args: Namespace,
    config: Config,
    transform: Callable[[Piece], Piece],
    play: Callable[..., None],
) -> None:
    logger.info("Processing %s", file)
    with open(file, "r", encoding="utf8") as f:
        text = f.read()
    music = transform(parse(text))
    if not any(music):
        return
    if args.notes:
        print_music(music)
    elif args.lilypond:
        write_lilypond_music(
            music, f0=config.f, output_path=Path(file).with_suffix(".ly")
        )
    elif args.scale:
        write_scale(music, Path(file).with_suffix(".scl"))
    else:
        play(music, filename=Path(file).with_suffix(".midi"))


def main(cli_args: Optional[List[str]] = None) -> None:
    """Get command line arguments and run `top_level`."""
    parser = get_parser()
    args = parser.parse_args(cli_args)
    top_level(args)


if __name__ == "__main__":
    main()
