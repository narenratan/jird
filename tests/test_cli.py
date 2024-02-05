"""Tests for jird.cli."""
import os
from functools import partial
from pathlib import Path

import pytest

import jird.midi
from jird.cli import (
    ACTIONS,
    _append_rest,
    ear_training,
    get_parser,
    interactive_mode_repl,
    main,
    print_banner,
    print_goodbye,
)
from jird.config import DEFAULT_SURGE_PATCH, DEFAULT_ZYN_PATCH
from jird.core import parse, temper


def test_parser():
    parser = get_parser()
    args = parser.parse_args(["foo"])
    assert args.files == ["foo"]


def test_print_banner(capfd):
    print_banner()
    out, _ = capfd.readouterr()
    assert out


def test_print_goodbye(capfd):
    print_goodbye()
    out, _ = capfd.readouterr()
    assert out


def mock_input(input_lines):
    input_generator = (x for x in input_lines)

    def _mock_input(_):
        try:
            return next(input_generator)
        except StopIteration as e:
            raise EOFError from e

    return _mock_input


@pytest.mark.parametrize("action", ["", *list(ACTIONS.keys())])
@pytest.mark.parametrize("edo", [None, 12, 19, 24, 31, 53, 72])
@pytest.mark.parametrize(
    "input_lines",
    [
        [""],
        [""],
        ["<1 5/4>:1", "7/6:1/4"],
        ["<1 5/4>:1", "7/6:1/4"],
        ["<1 5/4>:1", "7/6:1/4"],
        ["<1 5/4>:1", "7/6:1/4"],
        10 * ["<1 5/4>:1"],
        ["<1 5/4>:1; 1/2:1;"],
        ["<1 5/4>:1; 1/2:1;"],
        ["<1 5/4>:1; 1/2:1;"],
        ["<1 5/4>:1; 1/2:1;"],
        ["<1 5/4>:1; 1/2:1;"],
        ["<1 5/4>:1; 1/2:1;"],
        ["<1 5/4>:1; 1/2:1;"],
        ["<1 5/4>:1; 1/2:1;"],
        ["1:1/3 9/8:1/3 5/4:1/3; 1/2*(1:1/4 3/2:1/4 1:1/4 3/2:1/4);"],
        ["1:1/3 9/8:1/3 5/4:1/3; 1/2*(1:1/4 3/2:1/4 1:1/4 3/2:1/4);"],
        ["1:1"],
        ["<1 5/4>:1"],
        ["0:16"],
        ["0:1 1:1"],
    ],
)
def test_interactive_mode_repl(monkeypatch, input_lines, edo, action):
    input_lines = [x + action for x in input_lines]
    monkeypatch.setattr("builtins.input", mock_input(input_lines))
    transform = partial(temper, edo=edo) if edo is not None else lambda x: x
    play = partial(
        jird.midi.play_music, f0=440, t0=0.01, programs=None, pitch_bend_range=2
    )
    interactive_mode_repl(transform, play)


def test_interactive_mode_repl_bad_input(monkeypatch, capfd):
    monkeypatch.setattr("builtins.input", mock_input("3"))

    def transform(x):
        return x

    play = partial(
        jird.midi.play_music, f0=440, t0=0.01, programs=None, pitch_bend_range=2
    )
    interactive_mode_repl(transform, play)
    out, _ = capfd.readouterr()
    assert "Expected one of:" in out


@pytest.mark.parametrize(
    "music_str, expected_music_str",
    [
        ("1:2", "1:2 0:1"),
        ("<1 5/4>:2", "<1 5/4>:2 0:1"),
        ("1:2; 2:2", "1:2 0:1; 2:2 0:1"),
        ("1:1 <1 5/4>:2", "1:1 <1 5/4>:2 0:1"),
        ("1:2; <1 5/4>:2", "1:2 0:1; <1 5/4>:2 0:1"),
    ],
)
def test_append_rest(music_str, expected_music_str):
    music = parse(music_str)
    expected_music = parse(expected_music_str)
    output = _append_rest(music)
    assert output == expected_music


@pytest.fixture(
    params=[
        [""],
        ["5/4"],
        ["6/5", "5/4"],
        ["7/6", "6/5", "5/4"],
        ["7/6", "6/5", "5/4", "2"],
    ]
)
def training_file(tmp_path, request):
    """Text file containing ratios for ear training."""
    training_file_path = tmp_path / "training.txt"
    training_text = "\n".join(request.param) + "\n"
    training_file_path.write_text(training_text)
    return training_file_path


@pytest.mark.parametrize(
    "input_lines, edo",
    [
        (["9/8"], None),
        (["9/8"], 12),
        (["9/8"], 19),
        (["9/8", "7/6", "5/4", "2"], None),
        (["9/8", "7/6", "5/4", "2"], 12),
        (["9/8", "7/6", "5/4", "2"], 19),
        (["9/8", "7/6", "5/4", "2"], None),
        (["9/8", "7/6", "5/4", "2"], None),
        (["9/8", "7/6", "5/4", "2"], None),
        (["9/8", "7/6", "5/4", "2"], None),
    ],
)
def test_ear_training_repl(monkeypatch, training_file, input_lines, edo):
    monkeypatch.setattr("builtins.input", mock_input(input_lines))

    transform = partial(temper, edo=edo) if edo is not None else lambda x: x
    play = partial(
        jird.midi.play_music, f0=440, t0=0.01, programs=None, pitch_bend_range=2
    )

    with open(training_file, "r", encoding="utf8") as f:
        ratios = f.read().splitlines()
    ear_training(ratios, transform, play)


def test_ear_training_definitely_correct(monkeypatch, tmp_path, capfd):
    ratio = "5/4"
    monkeypatch.setattr("builtins.input", mock_input([ratio]))

    training_input_file = tmp_path / "tmp_file"
    training_input_file.write_text(ratio)

    def identity(x):
        return x

    transform = identity
    play = partial(
        jird.midi.play_music, f0=440, t0=0.01, programs=None, pitch_bend_range=2
    )

    with open(training_input_file, "r", encoding="utf8") as f:
        ratios = f.read().splitlines()
    ear_training(ratios, transform, play)

    out, _ = capfd.readouterr()

    assert "100.0%" in out


@pytest.mark.parametrize(
    "args, input_lines",
    [
        (
            [],
            [],
        ),
        (
            ["-p", "18"],
            [],
        ),
        (
            ["-p", "1,33"],
            [],
        ),
        (
            ["-p", "1", "-e", "19"],
            [],
        ),
        (
            [],
            ["<1 5/4>:1"],
        ),
        (
            [],
            ["<1 5/4>:1", "1/2:2"],
        ),
        (
            ["-p", "1", "-e", "19"],
            ["<1 5/4>:1"],
        ),
        (
            ["-p", "1,33", "-e", "19"],
            ["<1 5/4>:1; 1/2:1"],
        ),
    ],
    ids=str,
)
def test_main(tmp_path, monkeypatch, args, input_lines):
    orig_dir = Path.cwd()
    try:
        os.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", mock_input(input_lines))
        main(args)
    finally:
        os.chdir(orig_dir)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-f", "261.63"],
        ["-t", "0.6"],
        ["-f", "261.63", "-t", "0.6"],
        ["-m", "--pitch_bend_range", "48"],
        ["-l"],
        ["-e", "19", "-l"],
        ["-n"],
        ["-v"],
        ["--scale"],
        ["-e", "19", "--scale"],
        ["-i", str(DEFAULT_SURGE_PATCH)],
        ["-i", str(DEFAULT_ZYN_PATCH)],
        ["--csound"],
        ["--csound", "-f", "261.63"],
    ],
    ids=str,
)
def test_main_with_music_file(tmp_path, args, music_file):
    orig_dir = Path.cwd()
    args = [*args, str(music_file)]
    try:
        os.chdir(tmp_path)
        main(args)
    finally:
        os.chdir(orig_dir)


@pytest.mark.parametrize(
    "args, input_lines",
    [
        (
            ["--train"],
            ["7/6"],
        ),
        (
            ["--train"],
            ["7/6", "3/2"],
        ),
        (
            ["--train"],
            [],
        ),
        (
            ["-p", "18", "--train"],
            ["7/6"],
        ),
        (
            [
                "-p",
                "18",
                "-e",
                "31",
                "--train",
            ],
            ["7/6"],
        ),
    ],
    ids=str,
)
def test_main_with_training_file(
    tmp_path, monkeypatch, args, input_lines, training_file
):
    orig_dir = Path.cwd()
    args = [*args, str(training_file)]
    try:
        os.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", mock_input(input_lines))
        main(args)
    finally:
        os.chdir(orig_dir)


def test_json_config(tmp_path):
    config_path = tmp_path / "config.json"
    music_path = tmp_path / "music"

    config_path.write_text(
        """
{
    "t": 0.63,
    "f": 440.0,
    "tuning_method": "scala",
    "synth": "surge_xt",
    "volume": -6.6666,
    "parts": [
        {
            "instrument": "~/repos/surge/resources/data/patches_factory/Polysynths/Oiro.fxp",
            "volume": -8.25,
            "panning": 0.5
        },
        {
            "instrument": "~/repos/surge/resources/data/patches_factory/Polysynths/Spik.fxp",
            "volume": -3.0,
            "panning": 0.0
        },
        {
            "instrument": "~/repos/surge/resources/data/patches_factory/Polysynths/Boss.fxp",
            "volume": -7.0,
            "panning": 0.0
        },
        {
            "instrument": "~/repos/surge/resources/data/patches_factory/Basses/E-Bass.fxp",
            "volume": -5.0,
            "panning": -0.5
        }
    ]
}
"""
    )

    music_path.write_text("1:1")

    main(["-c", str(config_path), str(music_path)])
