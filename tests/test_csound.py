"""Tests for jird.csound."""
import pytest

from jird.core import parse
from jird.csound import csound_part, csound_score, write_csound_score


@pytest.mark.parametrize(
    "jird_part, expected_csound_part, f0, t0",
    [
        ("1:1", "i 1 0.0 1.0 1.0 440.0", 440, 1),
        ("1:1", "i 1 0.0 1.0 1.0 550.0", 550, 1),
        ("1:1", "i 1 0.0 2.0 1.0 440.0", 440, 2),
        ("1:1:2", "i 1 0.0 1.0 2.0 440.0", 440, 1),
        ("1:2", "i 1 0.0 2.0 1.0 440.0", 440, 1),
        ("2:1", "i 1 0.0 1.0 1.0 880.0", 440, 1),
        ("1:1 1:1", "i 1 0.0 1.0 1.0 440.0\ni 1 1.0 1.0 1.0 440.0", 440, 1),
        ("1:2 1:1", "i 1 0.0 2.0 1.0 440.0\ni 1 2.0 1.0 1.0 440.0", 440, 1),
        ("<1 5/4>:1", "i 1 0.0 1.0 1.0 440.0\ni 1 0.0 1.0 1.0 550.0", 440, 1),
    ],
)
def test_csound_part(jird_part, expected_csound_part, f0, t0):
    output = csound_part(parse(jird_part)[0], f0, t0, instrument=1)
    assert output == expected_csound_part


@pytest.mark.parametrize(
    "jird_music, expected_csound_score",
    [
        ("1:1", "i 1 0.0 1.0 1.0 440.0"),
        ("1:1; 1:1", "i 1 0.0 1.0 1.0 440.0\n\ni 2 0.0 1.0 1.0 440.0"),
    ],
)
def test_csound_score(jird_music, expected_csound_score):
    output = csound_score(parse(jird_music), f0=440, t0=1)
    assert output == expected_csound_score


@pytest.mark.parametrize(
    "music_str",
    [
        "",
        "1:1",
        "<1 5/4>:1",
        "5/4:2 1:2",
        "1:2; 7/6:2",
        "1:1/3",
        "1:12",
        "<1 5/4>:1/3",
        "<1 5/4>:12",
    ],
)
def test_write_csound_score(music_str, tmp_path):
    music = parse(music_str)
    output_path = tmp_path / "out.sco"
    write_csound_score(music, f0=440, t0=1.2, output_path=output_path)
    assert output_path.exists()
