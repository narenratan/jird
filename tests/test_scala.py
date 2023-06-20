"""Tests for jird.scala."""
from fractions import Fraction

import pytest

from jird.core import parse
from jird.scala import (
    build_scale,
    scala_midi_note,
    write_scala_files_for_midi,
    write_scale,
    write_scl_file,
)


@pytest.mark.parametrize(
    "music_str, expected_scale",
    [
        ("", []),
        ("1:1", [Fraction(1, 1)]),
        ("3/4:1", [Fraction(3, 2)]),
        ("0:1", []),
        ("0:1 1:1", [Fraction(1, 1)]),
        ("1:1 7/6:2", [Fraction(1, 1), Fraction(7, 6)]),
        ("1:1 4/3:4 7/6:2", [Fraction(1, 1), Fraction(7, 6), Fraction(4, 3)]),
        ("1:1 4/3:4 7/6:2 4/3:2", [Fraction(1, 1), Fraction(7, 6), Fraction(4, 3)]),
        ("2:1", [Fraction(1, 1)]),
        ("1:1 2:1", [Fraction(1, 1)]),
        ("1:1; 2:1", [Fraction(1, 1)]),
        ("1:1; 3:1", [Fraction(1, 1), Fraction(3, 2)]),
    ],
)
def test_build_scale(music_str, expected_scale):
    music = parse(music_str)
    output = build_scale(music)
    assert output == expected_scale


@pytest.mark.parametrize(
    "ratios,expected_file_lines",
    [
        ([Fraction(1, 1)], [" test", " 1", "!", " 1"]),
        ([Fraction(3, 2)], [" test", " 1", "!", " 3/2"]),
        ([Fraction(1, 1), Fraction(3, 2)], [" test", " 2", "!", " 1", " 3/2"]),
        (
            [Fraction(1, 1), Fraction(3, 2), Fraction(5, 2)],
            [" test", " 3", "!", " 1", " 3/2", " 5/2"],
        ),
    ],
)
def test_write_scl_file(ratios, expected_file_lines, tmp_path):
    output_path = tmp_path / "test.scl"
    write_scl_file(ratios, output_path)
    file_contents = output_path.read_text()
    expected_file_contents = "\n".join(expected_file_lines) + "\n"
    assert file_contents == expected_file_contents


@pytest.mark.parametrize(
    "music_str,expected_file_lines",
    [
        ("1:1", [" test", " 1", "!", " 2"]),
        ("1:1 0:1", [" test", " 1", "!", " 2"]),
        ("1:1 2:1", [" test", " 1", "!", " 2"]),
        ("2:1", [" test", " 1", "!", " 2"]),
        ("3/2:1", [" test", " 1", "!", " 3/2"]),
        ("1:1 3/2:1", [" test", " 2", "!", " 3/2", " 2"]),
        ("<1 5/4 3/2>:1:10", [" test", " 3", "!", " 5/4", " 3/2", " 2"]),
    ],
)
def test_write_scale(music_str, expected_file_lines, tmp_path):
    music = parse(music_str)
    output_path = tmp_path / "test.scl"
    write_scale(music, output_path)
    file_contents = output_path.read_text()
    expected_file_contents = "\n".join(expected_file_lines) + "\n"
    assert file_contents == expected_file_contents


def test_empty_write_scale(tmp_path):
    output_path = tmp_path / "foo"
    write_scale(parse(""), output_path)


@pytest.mark.parametrize(
    "music_str, expected_scl_lines, expected_kbm_lines",
    [
        (
            "1:1",
            [" test", " 1", "!", " 1"],
            [
                "1",
                "0",
                "0",
                "0",
                "0",
                "440.0",
                "0",
                "! Mapping",
                "0",
            ],
        ),
        (
            "1:1 0:1",
            [" test", " 1", "!", " 1"],
            [
                "1",
                "0",
                "0",
                "0",
                "0",
                "440.0",
                "0",
                "! Mapping",
                "0",
            ],
        ),
        (
            "1:1 5/4:1",
            [" test", " 1", "!", " 5/4"],
            [
                "2",
                "0",
                "1",
                "0",
                "0",
                "440.0",
                "0",
                "! Mapping",
                "0",
                "1",
            ],
        ),
        (
            "<1 5/4 3/2>:4:2",
            [" test", " 2", "!", " 5/4", " 3/2"],
            [
                "3",
                "0",
                "2",
                "0",
                "0",
                "440.0",
                "0",
                "! Mapping",
                "0",
                "1",
                "2",
            ],
        ),
    ],
)
def test_write_scala_files_for_midi(
    music_str, expected_scl_lines, expected_kbm_lines, tmp_path
):
    music = parse(music_str)
    base_path = tmp_path / "test.midi"
    write_scala_files_for_midi(music, 440.0, base_path)
    scl_contents = base_path.with_suffix(".scl").read_text()
    kbm_contents = base_path.with_suffix(".kbm").read_text()

    expected_scl_contents = "\n".join(expected_scl_lines) + "\n"
    expected_kbm_contents = "\n".join(expected_kbm_lines) + "\n"

    assert scl_contents == expected_scl_contents
    assert kbm_contents == expected_kbm_contents


def test_empty_write_scala_files_for_midi(tmp_path):
    output_path = tmp_path / "foo"
    write_scala_files_for_midi(parse(""), 440.0, output_path)


def test_scala_midi_note():
    note = parse("5/4:1")[0][0]
    index = 7
    frequency_map = {Fraction(5, 4): index}
    midi_note = scala_midi_note(note, frequency_map)
    assert midi_note.pitch == index
    assert midi_note.bend is None


def test_scala_midi_rest():
    note = parse("0:1")[0][0]
    frequency_map = {Fraction(5, 4): 7}
    midi_note = scala_midi_note(note, frequency_map)
    assert midi_note.pitch == 0
    assert midi_note.bend is None
    assert midi_note.velocity == 0
