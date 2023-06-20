"""
Code for translating jird music into lilypond code.

Lilypond can produce pdf sheet music from the lilypond code.

See https://lilypond.org/
"""
from fractions import Fraction
from itertools import chain
from math import floor, log2
from pathlib import Path
from typing import List, Tuple, Union

from jird.constants import MIDDLE_C_FREQUENCY, REST_FREQUENCY
from jird.core import (
    Chord,
    Note,
    Part,
    Piece,
    Power,
    RatioProduct,
    evaluate,
    lowest,
    prod,
    temper_note,
)

NOTE_NAMES = [
    "c",
    "cs",
    "df",
    "d",
    "ds",
    "ef",
    "e",
    "es",
    "f",
    "fs",
    "gf",
    "g",
    "gs",
    "af",
    "a",
    "as",
    "bf",
    "b",
    "bs",
]
"""
Lilypond note names to use. Currently uses nineteen notes but can be
any length. For example could use the note names from 31EDO to get
double sharps and flats, or variant with half sharps and flats (see
https://en.wikipedia.org/wiki/31_equal_temperament).
"""

DURATIONS = [
    Fraction(4, 1),
    Fraction(2, 1),
    Fraction(1, 1),
    Fraction(1, 2),
    Fraction(1, 4),
    Fraction(1, 8),
    Fraction(1, 16),
    Fraction(1, 32),
]
"""
Durations of basic lilypond notes.
"""

CENTS = r"""#(define (cents . args) #{
    ^\markup{
        \teeny
        \override #'(baseline-skip . 1.4)
        \with-color "gray"
        \center-column {
            $(reverse args)
        }
    }
#})
"""
"""
Scheme function to annotate note or chord with cent deviations.
Used to avoid duplication in the generated lilypond code.
"""

RATIOS = r"""#(define (ratios . args) #{
    _\markup{
        \teeny
        \override #'(baseline-skip . 1.4)
        \center-column {
            \with-color "blueviolet" $(reverse (cdr args))
            \with-color "orangered" $(car args)
        }
    }
#})
"""
"""
Scheme function to annotate note or chord with ratios.
Used to avoid duplication in the generated lilypond code.
"""

INDENT = "  "


def lilypond_pitch(
    note: Note, f0: float, base_edo: int = 12
) -> Tuple[str, str, Union[RatioProduct, Fraction, Power]]:
    """
    Calculate lilypond representation of pitch of `note`.

    Parameters
    ----------
    note : Note
        Note to represent.
    f0 : float
        Frequency of 1/1 in Hz.
    base_edo : int
        EDO to use when calculating cent deviations. Defaults to 12, in which
        case deviations are with respect to the nearest note in twelve tone
        equal temperament.

    Returns
    -------
    tuple of (str, str, RatioProduct or Fraction or Power)
        Note name, formatted cent deviation, and note frequency. Frequency is
        either a ratio or a power if `note` is tempered.
    """
    if evaluate(note.frequency) == REST_FREQUENCY:
        return "r", "", RatioProduct(Fraction(0))
    n_notes = len(NOTE_NAMES)
    real_frequency = evaluate(note.frequency) * f0
    steps = round(n_notes * log2(real_frequency / MIDDLE_C_FREQUENCY))
    octaves, note_index = divmod(steps, n_notes)
    # Lilypond writes unmarked c,d,...,b for octave *below* middle C
    octaves += 1
    base_note_name = NOTE_NAMES[note_index]
    octave_marks = abs(octaves) * ("'" if octaves > 0 else ",")
    note_name = base_note_name + octave_marks
    cent_deviation = note.cents - temper_note(note, edo=base_edo).cents
    cent_deviation_str = f"{round(cent_deviation):+}"
    return note_name, cent_deviation_str, note.frequency


def _factorize(n: int) -> Tuple[int, int]:
    """Factorize a number into the largest power of two it contains and the remaining factor."""
    assert n > 0
    count = 0
    while n % 2 == 0:
        count += 1
        n //= 2
    power_of_two = 2**count
    return power_of_two, n


def lilypond_duration(note: Note) -> str:
    """
    Get lilypond representation of duration of `note`.

    Parameters
    ----------
    note : Note
        Note to find duration of.

    Returns
    -------
    str
        Template of lilypond representation of `note` duration, ready to be
        populated with a lilypond note pitch or chord.
    """
    duration = Fraction(evaluate(note.duration))
    assert duration > 0

    # If denominator of note duration is not a power of two, write note as a
    # tuplet using the next smallest power of two. So for example a note with a
    # duration 1/3 gets written using a 3/2 tuplet, duration 1/5 a 5/4 tuplet,
    # and so on.

    power_of_two, odd_factor = _factorize(duration.denominator)

    rescale = 2 ** floor(log2(odd_factor))

    # Write remaining note as sum of 1/2**n durations

    to_divide = Fraction(duration.numerator, power_of_two * rescale)

    coeffs = {}
    for d in DURATIONS:
        coeffs[d], to_divide = divmod(to_divide, d)
    assert to_divide == 0, f"Could not represent {note} using durations: {DURATIONS}"

    # Lilypond writes a note lasting d beats as 4/d, so c1 is four beats,
    # c2 is two beats, c4 is one beat, c8 is half a beat, etc.

    # Lilypond notes to tie together:
    parts = list(
        chain.from_iterable(v * [f"{{0}}{4 / k}"] for k, v in coeffs.items() if v != 0)
    )

    # First argument, {0}, in template is for note name or chord
    # Second argument, {1}, in template is for annotations.
    if len(parts) == 1:
        base = parts[0] + "{1}"
    else:
        # Tie components to make full duration
        # Annotate the first of the tied notes
        base = f"{parts[0]}~" + "{1}" + "~".join(parts[1:])

    if odd_factor == 1:
        return base

    # Use tuplet if required

    return r"\tuplet" + f" {odd_factor}/{rescale} " + "{{" + base + "}}"


def lilypond_note(note: Note, f0: float) -> str:
    r"""
    Find complete lilypond representation of `note`.

    Parameters
    ----------
    note : Note
        Note to represent.
    f0 : float
        Base frequency in Hz.

    Returns
    -------
    str
        Lilypond representation of `note` including note name, duration, and
        annotations with cent deviation and ratios.

    Examples
    --------
    Lilypond representation of the just major third above middle C

    >>> from jird.core import parse
    >>> note = parse("5/4:1")[0][0]
    >>> print(lilypond_note(note, f0=261.63))
    e'4 $(cents "-14") $(ratios "1" "5/4")

    The `$(cents "-14")` is lilypond syntax to call a Scheme function called
    `cents` on `"-14"`. This Scheme function is defined at the top of the
    generated lilypond file to allow easy modification of the cent deviation
    formatting. Likewise for ratios.
    """
    duration = lilypond_duration(note)
    note_name, cent_deviation, frequency = lilypond_pitch(note, f0)
    if note_name == "r":
        # Do not need ties for rests
        return duration.format(note_name, "").replace("~", " ")
    cents = f'$(cents "{cent_deviation}")'

    # Ratios may not be present if note has been tempered
    ratios = ""
    if isinstance(frequency, RatioProduct):
        parts = frequency.ratios
        if len(parts) > 1:
            base = evaluate(prod(parts[:-1], Fraction(1)))
            freq = evaluate(parts[-1])
        else:
            base = 1
            freq = evaluate(frequency)
        ratios = f'$(ratios "{base}" "{freq}")'

    return duration.format(note_name, f" {cents} {ratios} ").strip()


def lilypond_chord(chord: Chord, f0: float) -> str:
    r"""
    Find lilypond representation of `chord`.

    Parameters
    ----------
    chord : Chord
        Chord to represent.
    f0 : float
        Base frequency in Hz.

    Returns
    -------
    str
        Lilypond representation of `chord` with note names, duration, and
        annotations with cent deviations and ratios.

    Examples
    --------
    Lilypond representation of just major triad

    >>> from jird.core import parse
    >>> chord = parse("<1 5/4 3/2>:4")[0][0]
    >>> print(lilypond_chord(chord, f0=440))
    <a' cs'' e''>1 $(cents "+0" "-14" "+2") $(ratios "1" "1" "5/4" "3/2")
    """
    template = lilypond_duration(chord[0])
    note_names, cent_deviations, frequencies = zip(
        *(lilypond_pitch(note, f0) for note in sorted(chord, key=lambda x: x.cents))
    )
    chord_body = f"<{' '.join(note_names)}>"
    cent_deviations_str = " ".join(f'"{x}"' for x in cent_deviations)
    cents = f"$(cents {cent_deviations_str})"

    # Ratios may not be present if chord has been tempered
    ratios = ""
    if all(isinstance(x, RatioProduct) for x in frequencies):
        parts = [x.ratios for x in frequencies]
        common = _count_leading_shared(parts)
        base = evaluate(prod(parts[0][:common], Fraction(1)))
        chord_freqs = [evaluate(prod(x[common:], Fraction(1))) for x in parts]
        freqs = " ".join(f'"{x}"' for x in chord_freqs)
        ratios = f'$(ratios "{base}" {freqs})'

    return template.format(chord_body, f" {cents} {ratios} ").strip()


def _count_leading_shared(parts: List[Tuple[Fraction, ...]]) -> int:
    """Find number of elements in common at the start of each tuple in `parts`."""
    shared = [len(set(x)) == 1 for x in zip(*parts)]
    try:
        count = shared.index(False)
    except ValueError:
        count = len(shared)
    return count


def lilypond_part(music: Part, f0: float, *, indent_level: int) -> str:
    r"""
    Lilypond representation of one part.

    Parameters
    ----------
    music : Part
        Part to be represented.
    f0 : float
        Base frequency in Hz.
    indent_level : int
        Number of levels to indent part in generated lilypond.

    Returns
    -------
    str
        Lilypond representation of part in `music`.

    Examples
    --------
    Lilypond representation of two notes and a chord

    >>> from jird.core import parse
    >>> part = parse("1:1 5/4:1 <1 5/4 3/2>:2")[0]
    >>> print(lilypond_part(part, f0=440, indent_level=0))
    \new Staff{
      a'4 $(cents "+0") $(ratios "1" "1")
      cs''4 $(cents "-14") $(ratios "1" "5/4")
      <a' cs'' e''>2 $(cents "+0" "-14" "+2") $(ratios "1" "1" "5/4" "3/2")
    }

    Bass clef is used for parts containing low notes

    >>> part = parse("1/4:4")[0]
    >>> print(lilypond_part(part, f0=440, indent_level=0))
    \new Staff{
      \clef bass
      a,1 $(cents "+0") $(ratios "1" "1/4")
    }
    """
    body = [
        lilypond_note(x, f0) if isinstance(x, Note) else lilypond_chord(x, f0)
        for x in music
    ]
    start = [indent_level * INDENT + r"\new Staff{"]
    end = [indent_level * INDENT + "}"]
    if lowest(music) <= 1 / 2:
        body = ["\\clef bass", *body]
    lines = start + [(indent_level + 1) * INDENT + x for x in body] + end
    return "\n".join(lines)


def lilypond_music(music: Piece, f0: float) -> str:
    r"""
    Lilypond representation of music containing multiple simultaneous parts.

    Parameters
    ----------
    music : Piece
        Music to represent
    f0 : float
        Base frequency in Hertz.

    Returns
    -------
    str
        Complete lilypond representation of `music`.

    Examples
    --------
    The output contains lilypond headers and Scheme functions for annotations
    with cent deviations and ratios.

    >>> from jird.core import parse
    >>> part = parse("1:4")
    >>> print(lilypond_music(part, f0=440))
    \version "2.22.2"
    \language "english"
    <BLANKLINE>
    #(define (cents . args) #{
        ^\markup{
            \teeny
            \override #'(baseline-skip . 1.4)
            \with-color "gray"
            \center-column {
                $(reverse args)
            }
        }
    #})
    <BLANKLINE>
    #(define (ratios . args) #{
        _\markup{
            \teeny
            \override #'(baseline-skip . 1.4)
            \center-column {
                \with-color "blueviolet" $(reverse (cdr args))
                \with-color "orangered" $(car args)
            }
        }
    #})
    <BLANKLINE>
    \score {
      <<
        \new Staff{
          a'1 $(cents "+0") $(ratios "1" "1")
        }
      >>
      \layout{}
    }
    """
    parts = [lilypond_part(part, f0, indent_level=2) for part in music]
    lines = [
        '\\version "2.22.2"',
        '\\language "english"',
        "",
        CENTS,
        RATIOS,
        "\\score {",
        INDENT + "<<",
        *parts,
    ] + [INDENT + ">>", INDENT + r"\layout{}", "}"]
    return "\n".join(lines)


def write_lilypond_music(
    music: Piece, f0: float, output_path: Union[str, Path]
) -> None:
    """
    Write lilypond representation of `music` to a file.

    Parameters
    ----------
    music : Piece
        Music to represent.
    f0 : float
        Base frequency in Hz.
    output_path : str or Path
        Filename for writing output.
    """
    lilypond_text = lilypond_music(music, f0)
    with open(output_path, "w", encoding="utf8") as f:
        f.write(lilypond_text)
