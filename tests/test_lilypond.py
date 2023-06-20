"""Tests for jird.lilypond."""
from fractions import Fraction

import pytest

from jird.constants import MIDDLE_C_FREQUENCY
from jird.core import parse
from jird.lilypond import (
    _count_leading_shared,
    lilypond_chord,
    lilypond_note,
    lilypond_part,
    write_lilypond_music,
)


@pytest.mark.parametrize(
    "jird_note, expected_lilypond_note",
    [
        ("5/4:1", 'e\'4 $(cents "-14") $(ratios "1" "5/4")'),
        ("6/5:1", 'ef\'4 $(cents "+16") $(ratios "1" "6/5")'),
        ("2*5/4:1", 'e\'\'4 $(cents "-14") $(ratios "2" "5/4")'),
        ("1/4*5/4:1", 'e,4 $(cents "-14") $(ratios "1/4" "5/4")'),
        ("1:1", 'c\'4 $(cents "+0") $(ratios "1" "1")'),
        ("1:1/2", 'c\'8 $(cents "+0") $(ratios "1" "1")'),
        ("1:2", 'c\'2 $(cents "+0") $(ratios "1" "1")'),
        ("1:4", 'c\'1 $(cents "+0") $(ratios "1" "1")'),
        ("9/8*5/4:1", 'fs\'4 $(cents "-10") $(ratios "9/8" "5/4")'),
        ("3/2*6/5:1", 'bf\'4 $(cents "+18") $(ratios "3/2" "6/5")'),
        ("7/6:1", 'ds\'4 $(cents "-33") $(ratios "1" "7/6")'),
        ("6/5:1", 'ef\'4 $(cents "+16") $(ratios "1" "6/5")'),
        ("0:1", "r4"),
        ("0:2", "r2"),
        ("0:4", "r1"),
        ("0:1/2", "r8"),
        ("0:8", "r1 r1"),
        ("0:12", "r1 r1 r1"),
        ("0:3", "r2 r4"),
        ("1/2:3", 'c2~ $(cents "+0") $(ratios "1" "1/2") c4'),
        ("1/2:7/2", 'c2~ $(cents "+0") $(ratios "1" "1/2") c4~c8'),
        ("1/2:2/3", r'\tuplet 3/2 {c4 $(cents "+0") $(ratios "1" "1/2") }'),
        ("1/2:1/3", r'\tuplet 3/2 {c8 $(cents "+0") $(ratios "1" "1/2") }'),
        ("1/2:4/5", r'\tuplet 5/4 {c4 $(cents "+0") $(ratios "1" "1/2") }'),
        ("1/2:2/5", r'\tuplet 5/4 {c8 $(cents "+0") $(ratios "1" "1/2") }'),
        ("1/2:4/7", r'\tuplet 7/4 {c4 $(cents "+0") $(ratios "1" "1/2") }'),
        ("1/2:2/7", r'\tuplet 7/4 {c8 $(cents "+0") $(ratios "1" "1/2") }'),
        ("1/2:3/5", r'\tuplet 5/4 {c8~ $(cents "+0") $(ratios "1" "1/2") c16}'),
    ],
)
def test_lilypond_note(jird_note, expected_lilypond_note):
    note = parse(jird_note)[0][0]
    output = lilypond_note(note, f0=MIDDLE_C_FREQUENCY)
    assert output == expected_lilypond_note


@pytest.mark.parametrize(
    "jird_chord, expected_lilypond_chord",
    [
        ("<1 5/4>:1", '<c\' e\'>4 $(cents "+0" "-14") $(ratios "1" "1" "5/4")'),
        ("<1 2*5/4>:1", '<c\' e\'\'>4 $(cents "+0" "-14") $(ratios "1" "1" "5/2")'),
        ("<2 2*5/4>:1", '<c\'\' e\'\'>4 $(cents "+0" "-14") $(ratios "2" "1" "5/4")'),
        (
            "<2*5/4 2*3/2>:1",
            '<e\'\' g\'\'>4 $(cents "-14" "+2") $(ratios "2" "5/4" "3/2")',
        ),
        ("<1 6/5>:1", '<c\' ef\'>4 $(cents "+0" "+16") $(ratios "1" "1" "6/5")'),
        ("<1 6/5>:1/2", '<c\' ef\'>8 $(cents "+0" "+16") $(ratios "1" "1" "6/5")'),
        (
            "<1 6/5 3/2>:1",
            '<c\' ef\' g\'>4 $(cents "+0" "+16" "+2") $(ratios "1" "1" "6/5" "3/2")',
        ),
        ("9/8*<1 5/4>:1", '<d\' fs\'>4 $(cents "+4" "-10") $(ratios "9/8" "1" "5/4")'),
        ("1/2*9/8*<1 5/4>:1", '<d fs>4 $(cents "+4" "-10") $(ratios "9/16" "1" "5/4")'),
        (
            "1/2*9/8*<1 2*5/4>:1",
            '<d fs\'>4 $(cents "+4" "-10") $(ratios "9/16" "1" "5/2")',
        ),
    ],
)
def test_lilypond_chord(jird_chord, expected_lilypond_chord):
    chord = parse(jird_chord)[0][0]
    output = lilypond_chord(chord, f0=MIDDLE_C_FREQUENCY)
    assert output == expected_lilypond_chord


@pytest.mark.parametrize(
    "jird_part, expected_lilypond_part",
    [
        (
            "1:1 3/2:1",
            r"""\new Staff{
  c'4 $(cents "+0") $(ratios "1" "1")
  g'4 $(cents "+2") $(ratios "1" "3/2")
}""",
        ),
        (
            "1:1 9/8*<1 6/5>:1/2",
            r"""\new Staff{
  c'4 $(cents "+0") $(ratios "1" "1")
  <d' f'>8 $(cents "+4" "+20") $(ratios "9/8" "1" "6/5")
}""",
        ),
        (
            "1/4:1",
            r"""\new Staff{
  \clef bass
  c,4 $(cents "+0") $(ratios "1" "1/4")
}""",
        ),
    ],
)
def test_lilypond_part(jird_part, expected_lilypond_part):
    part = parse(jird_part)[0]
    output = lilypond_part(part, f0=MIDDLE_C_FREQUENCY, indent_level=0)
    assert output == expected_lilypond_part


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
def test_write_lilypond_music(music_str, tmp_path):
    music = parse(music_str)
    output_path = tmp_path / "out.ly"
    write_lilypond_music(music, f0=440, output_path=output_path)
    assert output_path.exists()


@pytest.mark.parametrize(
    "parts, expected_count",
    [
        ([(), ()], 0),
        ([(1,), (1,)], 1),
        ([(1, 1), (1, 1)], 2),
        ([(1, 1, 2), (1, 1, 2)], 3),
        ([(1, 2, 1), (1, 1, 2)], 1),
        ([(2, 1, 1), (1, 1, 2)], 0),
        ([(1, 1), (1, 1), (1, 1)], 2),
        ([(1, 2), (1, 1), (1, 1)], 1),
        ([(1, 1, 1), (1, 1, 1), (1, 1, 2)], 2),
        ([(1, 2, 1), (1, 1, 1), (1, 1, 2)], 1),
    ],
)
def test_count_leading_shared(parts, expected_count):
    fraction_parts = [tuple(Fraction(x) for x in part) for part in parts]
    count = _count_leading_shared(fraction_parts)
    assert count == expected_count
