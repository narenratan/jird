"""Tests for jird.midi."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import pytest

import jird.midi
from jird.config import Config
from jird.core import Note, parse
from jird.midi import (
    chord_to_midi,
    chord_to_scala_midi,
    fourteen_bit,
    midi_track,
    music_to_midi_file,
    play_music,
    set_program,
    tempo_track,
    track_header,
    variable_length_quantity,
)


# Test values from http://www.music.mcgill.ca/~ich/classes/mumt306/StandardMIDIfileformat.html#BM1_1
@pytest.mark.parametrize(
    "n, expected_hex",
    [
        (0x00, "00"),
        (0x40, "40"),
        (0x7F, "7F"),
        (0x80, "8100"),
        (0x2000, "C000"),
        (0x3FFF, "FF7F"),
        (0x4000, "818000"),
        (0x100000, "C08000"),
        (0x1FFFFF, "FFFF7F"),
        (0x200000, "81808000"),
        (0x8000000, "C0808000"),
        (0xFFFFFFF, "FFFFFF7F"),
    ],
)
def test_variable_length_quantity(n, expected_hex):
    output = variable_length_quantity(n)
    assert output == expected_hex


CENTER = 0x2000
MAX = 0x3FFF
SEMITONE = round((MAX - CENTER) / 2)


@pytest.mark.parametrize(
    "frequency_ratio, expected_pitch, expected_bend",
    [
        (2 ** (-9 / 12), 60, CENTER),
        (2 ** (-8 / 12), 61, CENTER),
        (2 ** (-10 / 12), 59, CENTER),
        (2 ** (-8.5 / 12), 60, CENTER + SEMITONE / 2),
        (1, 69, 8192),
        (2 ** (1 / 12), 70, CENTER),
        (2 ** (0.5 / 12), 70, CENTER - SEMITONE / 2),
        (5 / 4, 73, CENTER - round(SEMITONE * (400.0 - 386.314) / 100)),
        (6 / 5, 72, CENTER + round(SEMITONE * (315.641 - 300.0) / 100)),
        (7 / 6, 72, CENTER - round(SEMITONE * (300.0 - 266.871) / 100)),
        (2 * 7 / 6, 84, CENTER - round(SEMITONE * (300.0 - 266.871) / 100)),
        (0, 0, CENTER),
    ],
)
def test_midi_note(frequency_ratio, expected_pitch, expected_bend):
    note = Note(frequency=frequency_ratio, duration=1)
    output_midi_note = note.to_midi(f0=440, pitch_bend_range=2)
    assert output_midi_note.pitch == expected_pitch
    assert output_midi_note.bend == expected_bend


@pytest.mark.parametrize(
    "n, expected_hex",
    [
        (0x3000, "0060"),
        (0, "0000"),
        (1, "0100"),
        (2, "0200"),
        (15, "0F00"),
        (16, "1000"),
        (0x7F, "7F00"),
        (0x8F, "0F01"),
        (0x3FFF, "7F7F"),
    ],
)
def test_fourteen_bit(n, expected_hex):
    output_hex = fourteen_bit(n)
    assert output_hex == expected_hex


@pytest.mark.parametrize(
    "input_hex, expected_header",
    [
        ("", "4d54726b00000000"),
        ("FF", "4d54726b00000001"),
        ("EFFF", "4d54726b00000002"),
        (9 * "AB", "4d54726b00000009"),
        (0x24 * "CD", "4d54726b00000024"),
    ],
)
def test_track_header(input_hex, expected_header):
    header = track_header(input_hex)
    assert header == expected_header


@pytest.mark.parametrize(
    "t0, expected_tempo_string",
    [
        (1e-6, "00FF510300000100FF2F00"),
        (2e-6, "00FF510300000200FF2F00"),
        (0.25, "00FF510303D09000FF2F00"),
        (0.5, "00FF510307A12000FF2F00"),
    ],
)
def test_tempo_track(t0, expected_tempo_string):
    output_track = tempo_track(t0)
    assert output_track[16:] == expected_tempo_string


@pytest.mark.parametrize(
    "program, channels, expected_byte_string",
    [
        (1, [0], "00C000"),
        (2, [0], "00C001"),
        (1, [1], "00C100"),
        (47, [0], "00C02E"),
        (1, [0, 1], "00C00000C100"),
        (47, [0, 1], "00C02E00C12E"),
        (47, [3, 15], "00C32E00CF2E"),
    ],
)
def test_set_program(program, channels, expected_byte_string):
    byte_string = set_program(program, channels)
    assert byte_string == expected_byte_string


@pytest.mark.parametrize(
    "notes_str, channels, expected_byte_string",
    [
        ("5/4:1", [0], "00E04F3B" + "00904940" + "8740804900"),
        ("5/4:1", [1], "00E14F3B" + "00914940" + "8740814900"),
        ("5/4:1", [0, 1, 2], "00E04F3B" + "00904940" + "8740804900"),
        (
            "<1 5/4>:1",
            [0, 1],
            "00E00040"
            + "00E14F3B"
            + "00904540"
            + "00914940"
            + "8740804500"
            + "00814900",
        ),
    ],
)
def test_chord_to_midi(notes_str, channels, expected_byte_string, monkeypatch):
    # Monkeypatch midi division so reference bytes do not need updating if division changes
    monkeypatch.setattr(jird.constants, "DIVISION", 960)

    notes = parse(notes_str)[0][0]
    byte_string = chord_to_midi(notes, f0=440, channels=channels, pitch_bend_range=2)
    assert byte_string == expected_byte_string


@pytest.mark.parametrize(
    "notes_str, expected_byte_string",
    [
        ("5/4:1", "00930740B440830700"),
        ("<1 5/4>:1", "0093034000930740B44083030000830700"),
    ],
)
def test_chord_to_scala_midi(notes_str, expected_byte_string, monkeypatch):
    # Monkeypatch midi division so reference bytes do not need updating if division changes
    monkeypatch.setattr(jird.constants, "DIVISION", 960)

    notes = parse(notes_str)[0][0]
    frequency_map = {Fraction(1): 3, Fraction(5, 4): 7}
    byte_string = chord_to_scala_midi(notes, frequency_map, channel=3)
    assert byte_string == expected_byte_string


def test_midi_track(monkeypatch):
    # Monkeypatch midi division so reference bytes do not need updating if division changes
    monkeypatch.setattr(jird.constants, "DIVISION", 960)

    music = parse("5/4:1")[0]
    byte_string = midi_track(music, f0=440, channels=[0], program=1, pitch_bend_range=2)
    assert byte_string == "4d54726b0000001400C00000E04F3B00904940874080490000FF2F00"


def test_midi_track_note(monkeypatch):
    # Monkeypatch midi division so reference bytes do not need updating if division changes
    monkeypatch.setattr(jird.constants, "DIVISION", 960)

    music = parse("5/4:1")[0]
    byte_string = midi_track(music, f0=440, channels=[0], program=1, pitch_bend_range=2)
    assert byte_string == "4d54726b0000001400C00000E04F3B00904940874080490000FF2F00"


ZYN_INSTRUMENT_PATH = Path(__file__).parents[1] / "src/jird/data/default.xiz"

CONFIGS = [
    Config.from_dict(
        {
            "f": 440,
            "t": 2,
            "tuning_method": "pitch_bend",
            "synth": "fluidsynth",
            "soundfont": "my_soundfont.sf2",
            "volume": 0.0,
            "parts": [
                {
                    "program": 47,
                    "volume": 0.0,
                    "panning": 0,
                }
            ],
        }
    ),
    Config.from_dict(
        {
            "f": 440,
            "t": 2,
            "tuning_method": "scala",
            "synth": "zynaddsubfx",
            "volume": 0.0,
            "parts": [
                {
                    "instrument": ZYN_INSTRUMENT_PATH,
                    "volume": 0.0,
                    "panning": 0,
                }
            ],
        }
    ),
]


@pytest.mark.parametrize("config", CONFIGS)
def test_music_to_midi_file(config, tmp_path):
    music = parse("5/4:1")
    output_path = tmp_path / "test.midi"
    music_to_midi_file(music, config=config, filename=output_path)
    assert output_path.exists()


@dataclass
class MockPopen:
    """Type to return from mocked subprocess.Popen."""

    pid: int = 14904
    stdout: str = ""

    def kill(self):
        """Mock kill method."""
        return


@pytest.mark.parametrize("config", CONFIGS)
def test_play_music(config, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "subprocess.run", lambda *args, **kwargs: MockPopen()  # noqa: ARG005
    )
    monkeypatch.setattr(
        "subprocess.Popen", lambda *args, **kwargs: MockPopen()  # noqa: ARG005
    )
    music = parse("5/4:1")
    output_path = tmp_path / "test.midi"
    play_music(music, config=config, filename=output_path)
    assert output_path.exists()


def file_not_found(*args, **kwargs):  # noqa: ARG001
    raise FileNotFoundError


@pytest.mark.parametrize("config", CONFIGS)
def test_play_music_missing_synth(config, tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.run", file_not_found)
    monkeypatch.setattr("subprocess.Popen", file_not_found)
    music = parse("5/4:1")
    output_path = tmp_path / "test.midi"
    with pytest.raises(SystemExit) as e:
        play_music(music, config=config, filename=output_path)
    assert e.type == SystemExit
    assert e.value.code == 1
