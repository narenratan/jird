"""Tests for jird.core."""
import operator
from fractions import Fraction
from math import isnan

import pytest

from jird.core import (
    Note,
    Power,
    RatioProduct,
    apply_to_notes,
    height,
    interval_table,
    lowest,
    parse,
    print_interval_table,
    print_music,
    temper,
    temper_note,
    total_duration,
)


def ratio(m, n):
    return RatioProduct(Fraction(m, n))


@pytest.mark.parametrize(
    "input_text, expected_music",
    [
        ("5/4:1", ([Note(frequency=ratio(5, 4), duration=ratio(1, 1))],)),
        ("5/4:1/4", ([Note(frequency=ratio(5, 4), duration=ratio(1, 4))],)),
        ("5/4:1/4;", ([Note(frequency=ratio(5, 4), duration=ratio(1, 4))], [])),
        (
            "5/4:1:1",
            ([Note(frequency=ratio(5, 4), duration=ratio(1, 1), volume=ratio(1, 1))],),
        ),
        (
            "5/4:1:2",
            ([Note(frequency=ratio(5, 4), duration=ratio(1, 1), volume=ratio(2, 1))],),
        ),
        (
            "5/4:1:1/2",
            ([Note(frequency=ratio(5, 4), duration=ratio(1, 1), volume=ratio(1, 2))],),
        ),
        (
            "5/4:1/4:2",
            ([Note(frequency=ratio(5, 4), duration=ratio(1, 4), volume=ratio(2, 1))],),
        ),
        (
            "6/5*5/4:1:2",
            (
                [
                    Note(
                        frequency=ratio(6, 5) * ratio(5, 4),
                        duration=ratio(1, 1),
                        volume=ratio(2, 1),
                    )
                ],
            ),
        ),
        (
            "<1 5/4 3/2>:1",
            (
                [
                    (
                        Note(frequency=ratio(1, 1), duration=ratio(1, 1)),
                        Note(frequency=ratio(5, 4), duration=ratio(1, 1)),
                        Note(frequency=ratio(3, 2), duration=ratio(1, 1)),
                    )
                ],
            ),
        ),
        (
            "1:1/3 5/4:1/3 3/2:1/3 2:1;",
            (
                [
                    Note(frequency=ratio(1, 1), duration=ratio(1, 3)),
                    Note(frequency=ratio(5, 4), duration=ratio(1, 3)),
                    Note(frequency=ratio(3, 2), duration=ratio(1, 3)),
                    Note(frequency=ratio(2, 1), duration=ratio(1, 1)),
                ],
                [],
            ),
        ),
        (
            "2*5/4:1",
            ([Note(frequency=ratio(2, 1) * ratio(5, 4), duration=ratio(1, 1))],),
        ),
        (
            "<1 5/4 3/2>:1 4/3*<1 5/4 3/2>:1 3/2*<1 5/4 3/2>:1;",
            (
                [
                    (
                        Note(frequency=ratio(1, 1), duration=ratio(1, 1)),
                        Note(frequency=ratio(5, 4), duration=ratio(1, 1)),
                        Note(frequency=ratio(3, 2), duration=ratio(1, 1)),
                    ),
                    (
                        Note(
                            frequency=ratio(4, 3) * ratio(1, 1),
                            duration=ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(4, 3) * ratio(5, 4),
                            duration=ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(4, 3) * ratio(3, 2),
                            duration=ratio(1, 1),
                        ),
                    ),
                    (
                        Note(
                            frequency=ratio(3, 2) * ratio(1, 1),
                            duration=ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(3, 2) * ratio(5, 4),
                            duration=ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(3, 2) * ratio(3, 2),
                            duration=ratio(1, 1),
                        ),
                    ),
                ],
                [],
            ),
        ),
        (
            "1:1; 5/4:1;",
            (
                [Note(frequency=ratio(1, 1), duration=ratio(1, 1))],
                [Note(frequency=ratio(5, 4), duration=ratio(1, 1))],
                [],
            ),
        ),
        (
            "1:1; 5/4:1",
            (
                [Note(frequency=ratio(1, 1), duration=ratio(1, 1))],
                [Note(frequency=ratio(5, 4), duration=ratio(1, 1))],
            ),
        ),
        (
            """
            1:1/4 5/4:1/4 3/2:1/2 ;
            <1 5/4 3/2>:1;
            """,
            (
                [
                    Note(frequency=ratio(1, 1), duration=ratio(1, 4)),
                    Note(frequency=ratio(5, 4), duration=ratio(1, 4)),
                    Note(frequency=ratio(3, 2), duration=ratio(1, 2)),
                ],
                [
                    (
                        Note(frequency=ratio(1, 1), duration=ratio(1, 1)),
                        Note(frequency=ratio(5, 4), duration=ratio(1, 1)),
                        Note(frequency=ratio(3, 2), duration=ratio(1, 1)),
                    )
                ],
                [],
            ),
        ),
        (
            "2*(1:1/4 5/4:1/4 3/2:1/2)",
            (
                [
                    Note(frequency=ratio(2, 1) * ratio(1, 1), duration=ratio(1, 4)),
                    Note(frequency=ratio(2, 1) * ratio(5, 4), duration=ratio(1, 4)),
                    Note(frequency=ratio(2, 1) * ratio(3, 2), duration=ratio(1, 2)),
                ],
            ),
        ),
        (
            "2*(1:1/4 5/4:1/4) 3/2:1/2",
            (
                [
                    Note(frequency=ratio(2, 1) * ratio(1, 1), duration=ratio(1, 4)),
                    Note(frequency=ratio(2, 1) * ratio(5, 4), duration=ratio(1, 4)),
                    Note(frequency=ratio(3, 2), duration=ratio(1, 2)),
                ],
            ),
        ),
        (
            "5/4:1**9/8",
            (
                [
                    Note(
                        frequency=ratio(5, 4),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    )
                ],
            ),
        ),
        (
            "3/2*5/4:1**9/8",
            (
                [
                    Note(
                        frequency=ratio(3, 2) * ratio(5, 4),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    )
                ],
            ),
        ),
        (
            "(1:1 5/4:1)**9/8",
            (
                [
                    Note(
                        frequency=ratio(1, 1),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    ),
                    Note(
                        frequency=ratio(5, 4),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    ),
                ],
            ),
        ),
        (
            "(1:1 5/4:1)**9/8 2:2",
            (
                [
                    Note(
                        frequency=ratio(1, 1),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    ),
                    Note(
                        frequency=ratio(5, 4),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    ),
                    Note(
                        frequency=ratio(2, 1),
                        duration=ratio(2, 1),
                        volume=ratio(1, 1),
                    ),
                ],
            ),
        ),
        (
            "3/2*(1:1 5/4:1)**9/8",
            (
                [
                    Note(
                        frequency=ratio(3, 2) * ratio(1, 1),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    ),
                    Note(
                        frequency=ratio(3, 2) * ratio(5, 4),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    ),
                ],
            ),
        ),
        (
            "(1:1:5/4 5/4:1)**9/8",
            (
                [
                    Note(
                        frequency=ratio(1, 1),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(5, 4),
                    ),
                    Note(
                        frequency=ratio(5, 4),
                        duration=ratio(1, 1),
                        volume=ratio(9, 8) * ratio(1, 1),
                    ),
                ],
            ),
        ),
        (
            "<1 5/4 3/2>:1**5/4",
            (
                [
                    (
                        Note(
                            frequency=ratio(1, 1),
                            duration=ratio(1, 1),
                            volume=ratio(5, 4) * ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(5, 4),
                            duration=ratio(1, 1),
                            volume=ratio(5, 4) * ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(3, 2),
                            duration=ratio(1, 1),
                            volume=ratio(5, 4) * ratio(1, 1),
                        ),
                    )
                ],
            ),
        ),
        (
            "(9/8:3 <1 5/4 3/2>:1)**5/4",
            (
                [
                    Note(
                        frequency=ratio(9, 8),
                        duration=ratio(3, 1),
                        volume=ratio(5, 4) * ratio(1, 1),
                    ),
                    (
                        Note(
                            frequency=ratio(1, 1),
                            duration=ratio(1, 1),
                            volume=ratio(5, 4) * ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(5, 4),
                            duration=ratio(1, 1),
                            volume=ratio(5, 4) * ratio(1, 1),
                        ),
                        Note(
                            frequency=ratio(3, 2),
                            duration=ratio(1, 1),
                            volume=ratio(5, 4) * ratio(1, 1),
                        ),
                    ),
                ],
            ),
        ),
    ],
)
def test_parse(input_text, expected_music):
    music = parse(input_text)
    assert music == expected_music


@pytest.mark.parametrize(
    "note, expected_cents",
    [
        (Note(frequency=Fraction(5, 4), duration=1), 386.314),
        (
            Note(frequency=Fraction(5, 4), duration=Fraction(1, 1)),
            386.314,
        ),
        (
            Note(frequency=Fraction(5, 4), duration=Fraction(1, 1)),
            386.314,
        ),
        (
            Note(frequency=5 / 4, duration=1),
            386.314,
        ),
        (Note(frequency=Fraction(4, 5), duration=1), -386.314),
    ],
)
def test_note_cents(note, expected_cents):
    cents = note.cents
    assert round(cents, 3) == expected_cents


def test_note_cents_nan():
    note = Note(frequency=Fraction(0, 1), duration=Fraction(1, 1))
    assert isnan(note.cents)


@pytest.mark.parametrize(
    "notes, function, expected_output",
    [
        # Test applying identity function to a note
        (parse("5/4:1"), lambda x: x, parse("5/4:1")),
        #
        # Test pulling frequency from a note
        (parse("5/4:1")[0], lambda x: x.frequency, [Fraction(5, 4)]),
        #
        # Test pulling frequencies from a chord
        (
            parse("<1 5/4 3/2>:1")[0],
            lambda x: x.frequency,
            [
                (
                    Fraction(1, 1),
                    Fraction(5, 4),
                    Fraction(3, 2),
                )
            ],
        ),
        #
        # Test pulling durations from two notes
        (
            parse("5/4:1 7/6:1/4")[0],
            lambda x: x.duration,
            [Fraction(1, 1), Fraction(1, 4)],
        ),
        #
        # Test doubling frequency of a note
        (
            parse("5/4:1")[0],
            lambda x: Note(frequency=Fraction(2) * x.frequency, duration=x.duration),
            [
                Note(
                    frequency=Fraction(2) * ratio(5, 4),
                    duration=Fraction(1, 1),
                )
            ],
        ),
    ],
)
def test_apply_to_notes(notes, function, expected_output):
    output = apply_to_notes(notes, function)
    assert output == expected_output


@pytest.mark.bad_type
def test_apply_to_notes_bad_type():
    with pytest.raises(ValueError, match="foo"):
        apply_to_notes("foo", lambda x: x)


@pytest.mark.parametrize(
    "note, edo, expected_tempered_note",
    [
        (
            Note(frequency=Fraction(6, 5), duration=Fraction(1, 1)),
            12,
            Note(frequency=Power(2, 3, 12), duration=Fraction(1, 1)),
        ),
        (
            Note(frequency=Fraction(6, 5), duration=Fraction(1, 1)),
            19,
            Note(frequency=Power(2, 5, 19), duration=Fraction(1, 1)),
        ),
        (
            Note(frequency=Fraction(7, 5), duration=Fraction(1, 1)),
            12,
            Note(frequency=Power(2, 6, 12), duration=Fraction(1, 1)),
        ),
        (
            Note(frequency=Fraction(7, 5), duration=Fraction(1, 1)),
            19,
            Note(frequency=Power(2, 9, 19), duration=Fraction(1, 1)),
        ),
    ],
)
def test_temper_note(note, edo, expected_tempered_note):
    tempered_note = temper_note(note, edo=edo)
    assert tempered_note == expected_tempered_note


def test_temper_note_zero_freq():
    note = Note(frequency=Fraction(0, 1), duration=1)
    tempered_note = temper_note(note, edo=19)
    assert note == tempered_note


@pytest.mark.parametrize(
    "notes, edo, expected_tempered_notes",
    [
        (
            ([Note(frequency=Fraction(6, 5), duration=Fraction(1, 1))],),
            12,
            ([Note(frequency=Power(2, 3, 12), duration=Fraction(1, 1))],),
        ),
        (
            ([Note(frequency=Fraction(6, 5), duration=Fraction(1, 1))],),
            19,
            ([Note(frequency=Power(2, 5, 19), duration=Fraction(1, 1))],),
        ),
        (
            (
                [
                    (
                        Note(frequency=Fraction(7, 5), duration=Fraction(1, 1)),
                        Note(frequency=Fraction(3, 2), duration=Fraction(1, 1)),
                    )
                ],
            ),
            12,
            (
                [
                    (
                        Note(frequency=Power(2, 6, 12), duration=Fraction(1, 1)),
                        Note(frequency=Power(2, 7, 12), duration=Fraction(1, 1)),
                    )
                ],
            ),
        ),
        (
            (
                [
                    (
                        Note(frequency=Fraction(7, 5), duration=Fraction(1, 1)),
                        Note(frequency=Fraction(3, 2), duration=Fraction(1, 1)),
                    )
                ],
            ),
            19,
            (
                [
                    (
                        Note(frequency=Power(2, 9, 19), duration=Fraction(1, 1)),
                        Note(frequency=Power(2, 11, 19), duration=Fraction(1, 1)),
                    )
                ],
            ),
        ),
    ],
)
def test_temper(notes, edo, expected_tempered_notes):
    tempered_notes = temper(notes, edo=edo)
    assert tempered_notes == expected_tempered_notes


@pytest.mark.parametrize(
    "input_text, expected_duration",
    [
        ("5/4:1", 1),
        ("5/4:1/4", Fraction(1, 4)),
        ("5/4:1 3/2:1", 2),
        ("5/4:1 3/2:1/4", Fraction(5, 4)),
        ("5/4:1/4 3/2:1/4 9/8:1/4", Fraction(3, 4)),
        ("<1 7/6 4/3>:2/3", Fraction(2, 3)),
        ("1:1 <1 7/6 4/3>:2/3", Fraction(5, 3)),
        ("1:1 <1 7/6 4/3>:2/3; 9/8:5/3", Fraction(5, 3)),
    ],
)
def test_total_duration(input_text, expected_duration):
    music = parse(input_text)
    duration = total_duration(music)
    assert duration == expected_duration


def test_total_duration_empty_list():
    assert total_duration([]) == 0


def test_total_duration_empty_tuple():
    assert total_duration(()) == 0


@pytest.mark.bad_type
def test_total_duration_bad_type():
    with pytest.raises(ValueError, match="foo"):
        total_duration("foo")


@pytest.mark.parametrize(
    "input_text, expected_out",
    [
        (
            "5/4:1",
            """[
  Note(frequency=5/4, cents=386.314, duration=1),
],
""",
        ),
        (
            "5/4:1 16/15:1/4",
            """[
  Note(frequency=5/4, cents=386.314, duration=1),
  Note(frequency=16/15, cents=111.731, duration=1/4),
],
""",
        ),
        (
            "<1 5/4>:1",
            """[
  (
    Note(frequency=1, cents=0.0, duration=1),
    Note(frequency=5/4, cents=386.314, duration=1),
  ),
],
""",
        ),
    ],
)
def test_print_music(capfd, input_text, expected_out):
    music = parse(input_text)[0]
    print_music(music)
    out, _ = capfd.readouterr()
    assert out == expected_out


@pytest.mark.bad_type
def test_print_music_bad_type():
    with pytest.raises(ValueError, match="foo"):
        print_music("foo")


@pytest.mark.parametrize(
    "music_text, expected_height",
    [
        ("", 0),
        ("9/7:1", 1),
        ("<1 3/2>:1/3", 2),
        ("3/2*<1 7/6 3/2 16/9 2*4/3>:1/7", 5),
        ("1:1; 1:1", 2),
        ("<1 3/2>:1; 1:1", 3),
        ("<1 3/2>:1; <1 5/4>:1", 4),
        ("<1 3/2>:1; <1 5/4 16/9>:1;", 5),
        ("4/3:1/2 <1 3/2>:1/2; <1 5/4 16/9>:1;", 5),
        ("4/3:1/2 <1 3/2>:1/2; <1 5/4 16/9>:1; <1 3/2>:1", 7),
    ],
)
def test_height(music_text, expected_height):
    music = parse(music_text)
    actual_height = height(music)
    assert actual_height == expected_height


@pytest.mark.bad_type
def test_height_bad_type():
    with pytest.raises(ValueError, match="foo"):
        height("foo")


@pytest.mark.parametrize(
    "ratios, expected_table",
    [
        (
            (1, Fraction(5, 4), Fraction(3, 2)),
            [
                [Fraction(1, 1), Fraction(5, 4), Fraction(3, 2)],
                [Fraction(4, 5), Fraction(1, 1), Fraction(6, 5)],
                [Fraction(2, 3), Fraction(5, 6), Fraction(1, 1)],
            ],
        ),
        (
            (1, Fraction(5, 4), Fraction(3, 2), Fraction(15, 8)),
            [
                [Fraction(1, 1), Fraction(5, 4), Fraction(3, 2), Fraction(15, 8)],
                [Fraction(4, 5), Fraction(1, 1), Fraction(6, 5), Fraction(3, 2)],
                [Fraction(2, 3), Fraction(5, 6), Fraction(1, 1), Fraction(5, 4)],
                [Fraction(8, 15), Fraction(2, 3), Fraction(4, 5), Fraction(1, 1)],
            ],
        ),
        (
            (1, Fraction(6, 5), Fraction(3, 2), Fraction(16, 9)),
            [
                [Fraction(1, 1), Fraction(6, 5), Fraction(3, 2), Fraction(16, 9)],
                [Fraction(5, 6), Fraction(1, 1), Fraction(5, 4), Fraction(40, 27)],
                [Fraction(2, 3), Fraction(4, 5), Fraction(1, 1), Fraction(32, 27)],
                [Fraction(9, 16), Fraction(27, 40), Fraction(27, 32), Fraction(1, 1)],
            ],
        ),
        (
            (1, Fraction(6, 5), Fraction(3, 2), Fraction(12, 7)),
            [
                [Fraction(1, 1), Fraction(6, 5), Fraction(3, 2), Fraction(12, 7)],
                [Fraction(5, 6), Fraction(1, 1), Fraction(5, 4), Fraction(10, 7)],
                [Fraction(2, 3), Fraction(4, 5), Fraction(1, 1), Fraction(8, 7)],
                [Fraction(7, 12), Fraction(7, 10), Fraction(7, 8), Fraction(1, 1)],
            ],
        ),
    ],
)
def test_interval_table(ratios, expected_table):
    table = interval_table(ratios)
    assert table == expected_table


@pytest.mark.parametrize(
    "input_string, expected_out",
    [
        (
            "1:1 5/4:1 3/2:1",
            """
         1  5/4  3/2
     ---------------
  1  |   1  5/4  3/2
5/4  | 4/5    1  6/5
3/2  | 2/3  5/6    1

""",
        ),
        (
            "0:1 1:1 5/4:1 3/2:1",
            """
         1  5/4  3/2
     ---------------
  1  |   1  5/4  3/2
5/4  | 4/5    1  6/5
3/2  | 2/3  5/6    1

""",
        ),
        (
            "<1 5/4 3/2>:1",
            """
         1  5/4  3/2
     ---------------
  1  |   1  5/4  3/2
5/4  | 4/5    1  6/5
3/2  | 2/3  5/6    1

""",
        ),
        ("", ""),
    ],
)
def test_print_interval_table(input_string, expected_out, capfd):
    music = parse(input_string)
    print_interval_table(music)
    out, _ = capfd.readouterr()
    assert out == expected_out


@pytest.mark.parametrize(
    "arg, expected_ratios",
    [
        ((), ()),
        ((Fraction(1),), (Fraction(1),)),
        ((Fraction(1), Fraction(2)), (Fraction(1), Fraction(2))),
        (RatioProduct(Fraction(1)), (Fraction(1),)),
        (RatioProduct((Fraction(1), Fraction(2))), (Fraction(1), Fraction(2))),
        (Fraction(1), (Fraction(1),)),
    ],
)
def test_ratio_product_init(arg, expected_ratios):
    ratio_product = RatioProduct(arg)
    assert ratio_product.ratios == expected_ratios


@pytest.mark.bad_type
def test_ratio_product_init_bad_type():
    with pytest.raises(ValueError):
        RatioProduct("foo")


@pytest.mark.parametrize(
    "ratio_product, expected_repr",
    [
        (RatioProduct(Fraction(1)), "1"),
        (RatioProduct(Fraction(1, 1)), "1"),
        (RatioProduct(Fraction(2, 1)), "2"),
        (RatioProduct(Fraction(6, 5)), "6/5"),
        (RatioProduct((Fraction(7, 6), Fraction(6, 5))), "7/6*6/5"),
        (RatioProduct((Fraction(2, 1), Fraction(6, 5))), "2*6/5"),
        (RatioProduct((Fraction(7, 6), Fraction(2, 1))), "7/6*2"),
        (RatioProduct(()), ""),
    ],
)
def test_ratio_product_repr(ratio_product, expected_repr):
    assert str(ratio_product) == expected_repr


@pytest.mark.parametrize(
    "ratio_product, expected_value",
    [
        (RatioProduct(Fraction(1)), 1),
        (RatioProduct((Fraction(1), Fraction(2))), 2),
        (RatioProduct((Fraction(1), Fraction(2), Fraction(3))), 6),
        (RatioProduct((Fraction(3, 2), Fraction(6, 5))), Fraction(9, 5)),
    ],
)
def test_ratio_product_evaluate(ratio_product, expected_value):
    assert ratio_product.evaluate() == expected_value


@pytest.mark.parametrize(
    "left, right, expected_product",
    [
        (
            Fraction(1),
            RatioProduct(Fraction(1)),
            RatioProduct((Fraction(1), Fraction(1))),
        ),
        (
            RatioProduct(Fraction(1)),
            Fraction(1),
            RatioProduct((Fraction(1), Fraction(1))),
        ),
        (
            RatioProduct(Fraction(1)),
            RatioProduct(Fraction(1)),
            RatioProduct((Fraction(1), Fraction(1))),
        ),
        (
            RatioProduct((Fraction(1), Fraction(2))),
            RatioProduct(Fraction(3)),
            RatioProduct((Fraction(1), Fraction(2), Fraction(3))),
        ),
        (
            RatioProduct(Fraction(1)),
            RatioProduct((Fraction(2), Fraction(3))),
            RatioProduct((Fraction(1), Fraction(2), Fraction(3))),
        ),
        (
            RatioProduct((Fraction(1), Fraction(2))),
            RatioProduct((Fraction(3), Fraction(4))),
            RatioProduct((Fraction(1), Fraction(2), Fraction(3), Fraction(4))),
        ),
        (RatioProduct(()), RatioProduct(()), RatioProduct(())),
        (RatioProduct(()), RatioProduct(Fraction(1)), RatioProduct(Fraction(1))),
        (RatioProduct(Fraction(1)), RatioProduct(()), RatioProduct(Fraction(1))),
        (
            RatioProduct(()),
            RatioProduct((Fraction(1), Fraction(2))),
            RatioProduct((Fraction(1), Fraction(2))),
        ),
    ],
)
def test_ratio_product_mul(left, right, expected_product):
    product = left * right
    assert product == expected_product


@pytest.mark.parametrize(
    "left, op, right, expected_value",
    [
        ((1,), operator.le, (1,), True),
        ((1,), operator.lt, (1,), False),
        ((1,), operator.ge, (1,), True),
        ((1,), operator.gt, (1,), False),
        ((1,), operator.eq, (1,), True),
        ((1,), operator.le, (2,), True),
        ((1,), operator.lt, (2,), True),
        ((1,), operator.ge, (2,), False),
        ((1,), operator.gt, (2,), False),
        ((1,), operator.eq, (2,), False),
        ((1,), operator.le, (2, 3), True),
        ((1,), operator.lt, (2, 3), True),
        ((1,), operator.ge, (2, 3), False),
        ((1,), operator.gt, (2, 3), False),
        ((1,), operator.eq, (2, 3), False),
        ((2, 5), operator.le, (3, 4), True),
        ((2, 5), operator.lt, (3, 4), True),
        ((2, 5), operator.ge, (3, 4), False),
        ((2, 5), operator.gt, (3, 4), False),
        ((2, 5), operator.eq, (3, 4), False),
    ],
)
def test_ratio_product_ops(left, op, right, expected_value):
    left_ratio_product = RatioProduct(tuple(map(Fraction, left)))
    right_ratio_product = RatioProduct(tuple(map(Fraction, right)))
    value = op(left_ratio_product, right_ratio_product)
    assert value == expected_value


def test_ratio_product_eq_other_type():
    assert RatioProduct(Fraction(1)) != "foo"


@pytest.mark.parametrize(
    "power, expected_repr",
    [
        (Power(2, 3, 4), "2**3/4"),
        (Power(1, 1, 1), "1**1/1"),
        (Power(0, 1, 2), "0**1/2"),
    ],
)
def test_power_repr(power, expected_repr):
    assert str(power) == expected_repr


@pytest.mark.parametrize(
    "power, expected_value",
    [
        (Power(2, 3, 4), 2 ** (3 / 4)),
        (Power(1, 1, 1), 1),
        (Power(0, 1, 2), 0),
    ],
)
def test_power_evaluate(power, expected_value):
    value = power.evaluate()
    assert value == expected_value


def test_power_rmul():
    with pytest.raises(NotImplementedError):
        Fraction(3, 2) * Power(2, 3, 4)


@pytest.mark.parametrize(
    "music_str, expected_lowest",
    [
        ("", float("inf")),
        ("1:1", 1),
        ("0:1", float("inf")),
        ("1:1 0:1", 1),
        ("1:2 3:4", 1),
        ("1:2 1/2:4", Fraction(1, 2)),
        ("<5/4 3/2 2>:4", Fraction(5, 4)),
        ("<5/4 3/2 2>:4; <6/5 3/2 2>:4", Fraction(6, 5)),
    ],
)
def test_lowest(music_str, expected_lowest):
    music = parse(music_str)
    value = lowest(music)
    assert value == expected_lowest
