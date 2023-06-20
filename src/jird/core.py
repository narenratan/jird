"""
Core jird code.

Includes representation of music, evaluation of parsed text into music,
and basic functions on music.
"""
import logging
import math
import operator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from fractions import Fraction
from functools import partial, reduce
from itertools import chain
from typing import Any, Callable, Iterable, List, Optional, Set, Tuple, TypeVar, Union

from jird import constants
from jird.parser import Lark_StandAlone, Token, Transformer

logger = logging.getLogger(__name__)

PARSER = Lark_StandAlone()  # type: ignore[no-untyped-call]

# Lark can generate a standalone parser to avoid a dependency on lark.
# This can be generated from the grammar in jird.g by running
#
#     $ python3 -m lark.tools.standalone --maybe_placeholders jird.g > parser.py
#
# For development it can be convenient to use lark itself to avoid
# regenerating the standalone parser after each change to the grammar.
#
# Use imports and definitions below if using lark itself rather than standalone parser
#
# from pathlib import Path
# from lark import Lark, Token, Transformer
#
# GRAMMAR = (Path(__file__).parent / "jird.g").read_text()
# PARSER = Lark(GRAMMAR, maybe_placeholders=True, parser="lalr")

Number = Union[Fraction, float]


class Unevaluated(ABC):
    """Base class for unevaluated quantities."""

    @abstractmethod
    def evaluate(self) -> Number:
        """Calculate actual value from unevaluated representation."""

    def __le__(self, other: Union["Unevaluated", Number]) -> bool:
        return self.evaluate() <= evaluate(other)

    def __lt__(self, other: Union["Unevaluated", Number]) -> bool:
        return self.evaluate() < evaluate(other)

    def __ge__(self, other: Union["Unevaluated", Number]) -> bool:
        return self.evaluate() >= evaluate(other)

    def __gt__(self, other: Union["Unevaluated", Number]) -> bool:
        return self.evaluate() > evaluate(other)


class RatioProduct(Unevaluated):
    """Unevaluated product of ratios."""

    def __init__(
        self, ratios: Union[Tuple[Fraction, ...], Fraction, "RatioProduct"] = ()
    ) -> None:
        """
        Create unevaluated product of ratios.

        Ratios making up the product are stored in a tuple. This allows seeing
        how a given ratio was composed.

        Parameters
        ----------
        ratios : tuple of Fraction or RatioProduct or Fraction
            Ratios making up the product.
        """
        if isinstance(ratios, tuple):
            self.ratios = ratios
        elif isinstance(ratios, Fraction):
            self.ratios = (ratios,)
        elif isinstance(ratios, RatioProduct):
            self.ratios = ratios.ratios
        else:
            raise ValueError(ratios)

    def __repr__(self) -> str:
        return "*".join(
            f"{x.numerator}" if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
            for x in self.ratios
        )

    def evaluate(self) -> Fraction:
        """Calculate product of ratios."""
        product = prod(self.ratios, Fraction(1))
        assert isinstance(product, Fraction)
        return product

    def __mul__(
        self, other: Union["RatioProduct", Fraction, Tuple[Fraction, ...]]
    ) -> "RatioProduct":
        return RatioProduct(self.ratios + RatioProduct(other).ratios)

    def __rmul__(
        self, other: Union["RatioProduct", Fraction, Tuple[Fraction, ...]]
    ) -> "RatioProduct":
        return RatioProduct(RatioProduct(other).ratios + self.ratios)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (RatioProduct, tuple, Fraction)):
            return False
        return self.ratios == RatioProduct(other).ratios


@dataclass
class Power(Unevaluated):
    """
    Unevaluated power.

    The power is of the form `b**(m/n)` where `b`, `m`, and `n` are
    integers. Used for example to make number of steps in equal temperaments
    more obvious, e.g. 2**8/12 rather than 2**2/3.
    """

    base: int
    exponent_numerator: int
    exponent_denominator: int

    def __repr__(self) -> str:
        return f"{self.base}**{self.exponent_numerator}/{self.exponent_denominator}"

    def evaluate(self) -> float:
        """Calculate value of power."""
        power: float = self.base ** (
            self.exponent_numerator / self.exponent_denominator
        )
        return power

    def __rmul__(self, other: Union[RatioProduct, Fraction]) -> "Power":
        msg = "Multiplication not implemented for Power"
        raise NotImplementedError(msg, (self, other))


@dataclass(frozen=True)
class MidiNote:
    """
    Midi representation of a musical note.

    Attributes
    ----------
    pitch : int
        Midi pitch number. Between 0 and 127.
    bend : int, optional
        Midi pitch bend number. Between 0 and 16383.
    ticks : int
        Number of midi ticks that the note lasts.
    velocity : int
        Midi note velocity (often mapped to loudness by synths). Between 0 and 127.
    """

    pitch: int
    bend: Optional[int]
    ticks: int
    velocity: int

    def __post_init__(self) -> None:
        assert 0 <= self.pitch <= 127
        if self.bend is not None:
            assert 0 <= self.bend <= 2**14 - 1
        assert 0 <= self.velocity <= 127


@dataclass
class Note:
    """
    Individual musical note.

    A note here is characterized by its frequency (giving its pitch), its
    duration (giving how long it is played for), and its volume (giving how
    loud it sounds). Frequency, duration, and volume are given as a fraction
    of basic units which are left unspecified.

    Attributes
    ----------
    frequency : RatioProduct or Fraction or Power
        Frequency ratio, e.g. 5/4. Real frequency of note is this frequency
        ratio multiplied by the basic frequency :math:`f_0`.
    duration : RatioProduct or Fraction
        Duration of note as a fraction of a basic time unit :math:`t_0`. The
        basic time unit can be chosen freely, e.g. to be the length of one bar
        or one whole note.
    volume : RatioProduct or Fraction
        Volume of note as a fraction of a reference volume. The reference volume
        1/1 is mapped to midi volume 64.

    Notes
    -----
    A rest is represented by a note with zero frequency.
    """

    frequency: Union[RatioProduct, Fraction, Power]
    duration: Union[RatioProduct, Fraction]
    volume: Union[RatioProduct, Fraction] = Fraction(1)  # noqa: RUF009

    @property
    def cents(self) -> float:
        """
        Calculate number of cents in the interval from 1 to the note's frequency.

        Returns
        -------
        float
            Number of cents in interval from 1 to `frequency` rounded to three decimal
            places. Returns nan if the note has zero frequency (corresponding to
            a rest).

        Examples
        --------
        There are about 700 cents in a just perfect fifth.

        >>> note = parse("3/2:1")[0][0]
        >>> note.cents
        701.955
        """
        frequency = evaluate(self.frequency)
        return (
            float("nan")
            if frequency == constants.REST_FREQUENCY
            else round(1200 * math.log2(frequency), 3)
        )

    def __repr__(self) -> str:
        return (
            f"Note(frequency={self.frequency}, cents={self.cents}, duration={self.duration}"
            + (f", volume={self.volume})" if self.volume != 1 else ")")
        )

    def to_midi(self, *, f0: float, pitch_bend_range: int) -> MidiNote:
        """
        Midi representation of `note`.

        Parameters
        ----------
        f0 : float
            Basic frequency for computing real frequency of `note`.
        pitch_bend_range : int
            Number of semitones to assume max pitch bend corresponds to.

        Returns
        -------
        MidiNote
            Midi representation of `note`.
        """
        duration = evaluate(self.duration)

        # Assume basic jird time unit t0 represents one quarter note
        # Actual value of time unit t0 not needed here; real tempo is set by `tempo_track`.
        ticks = duration * constants.DIVISION
        assert int(ticks) == ticks
        ticks = int(ticks)

        real_frequency = evaluate(self.frequency) * f0

        if real_frequency == 0:
            # Rest
            return MidiNote(
                pitch=0, bend=constants.PITCH_BEND_CENTER, ticks=ticks, velocity=0
            )

        # Express frequency as integer number of semitones (from middle C) plus remainder
        exact_semitones = 12 * math.log2(real_frequency / constants.MIDDLE_C_FREQUENCY)
        integer_semitones = round(exact_semitones)
        remainder = exact_semitones - integer_semitones

        # Pitch 60 is middle C in midi
        pitch = 60 + integer_semitones

        bend = round(
            constants.PITCH_BEND_CENTER
            + remainder
            * (constants.PITCH_BEND_MAX - constants.PITCH_BEND_CENTER)
            / pitch_bend_range
        )

        velocity = min(round(evaluate(self.volume) * 64), 127)
        return MidiNote(pitch=pitch, bend=bend, ticks=ticks, velocity=velocity)


Chord = Tuple[Note, ...]
Part = List[Union[Note, Chord]]
Piece = Tuple[Part, ...]

Music = Union[Note, Chord, Part, Piece]


def apply_to_notes(music: Music, f: Callable[[Note], Any]) -> Any:  # noqa: ANN401
    """
    Apply a function `f` to each note in a `Music` object.

    Parameters
    ----------
    music : Music
        Music containing the notes to apply `f` to.
    f : function
        Function to apply to each note.

    Returns
    -------
    Any
        The `music` object with `f` applied to each note.

    Examples
    --------
    Extract the cents for each note in some music.

    >>> music = parse("5/4:1 <1 3/2>:1")
    >>> apply_to_notes(music, lambda x: x.cents)
    ([386.314, (0.0, 701.955)],)

    Double duration of each note.

    >>> music = parse("7/6:1 4/3:1")[0]
    >>> music
    [Note(frequency=7/6, cents=266.871, duration=1), Note(frequency=4/3, cents=498.045, duration=1)]

    >>> f = lambda x: Note(frequency=x.frequency, duration=evaluate(Fraction(2) * x.duration))
    >>> apply_to_notes(music, f)
    [Note(frequency=7/6, cents=266.871, duration=2), Note(frequency=4/3, cents=498.045, duration=2)]
    """
    if isinstance(music, Note):
        return f(music)

    if isinstance(music, tuple):
        return tuple(apply_to_notes(x, f) for x in music)

    if isinstance(music, list):
        return [apply_to_notes(x, f) for x in music]

    raise ValueError(music)


class NoteTransformer(Transformer[Token, Piece]):
    """
    Transformer to convert an abstract syntax tree (AST) into a `Music` object.

    Each method is called on the corresponding node in the AST, so methods
    have the same names as elements of the grammar. The transformer works up
    the tree from the bottom. For more information see the Lark docs
    `here <https://lark-parser.readthedocs.io/en/latest/visitors.html#transformer>`_.
    """

    def integer(self, children: List[Token]) -> int:
        """
        Convert token (subclass of string) for integer to actual integer.

        Parameters
        ----------
        children : list of Token
            List of exactly one string representing an integer.

        Returns
        -------
        int
            Integer corresponding to single element of `children`.
        """
        assert len(children) == 1
        return int(children[0])

    def ratio(self, children: List[Optional[int]]) -> RatioProduct:
        """
        Convert pair of integers representing a ratio into the actual ratio.

        The ratio is returned as a `RatioProduct` in order to leave any later
        multiplications in a factored form, e.g. 5/4*3/2 will remain 5/4*3/2
        rather than 15/8. This is because the factorization often comes from
        'factoring out the root note' and so is musically useful to know.

        Parameters
        ----------
        children : list of (int or None)
            The numerator and denominator of the ratio. If the denominator is None the
            numerator is returned. This allows handling both "3/2" and "2" as ratios.

        Returns
        -------
        RatioProduct
            Ratio corresponding to integers in `children`.
        """
        x, y = children
        assert x is not None
        return RatioProduct(Fraction(x, y))

    def ratio_product(self, children: List[RatioProduct]) -> RatioProduct:
        """
        Form product of ratios.

        Parameters
        ----------
        children : list of RatioProduct
            Ratios to multiply.

        Returns
        -------
        RatioProduct
            Product of ratios in `children`.
        """
        product = prod(children, RatioProduct())
        assert isinstance(product, RatioProduct)
        return product

    def mult_expr(self, children: List[Union[RatioProduct, Music]]) -> Music:
        """
        Multiply frequencies of notes in music by a ratio.

        Parameters
        ----------
        children : list of RatioProduct or Music
            Last element is the Music containing the notes to multiply the frequencies
            of. Preceding elements are ratios to multiply frequencies in the music by.

        Returns
        -------
        Music
            Music with its note frequencies multiplied by given ratios.
        """
        ratios = children[:-1]
        music = children[-1]

        # Establish types
        ratio_products = []
        for x in ratios:
            assert isinstance(x, RatioProduct)
            ratio_products.append(x)

        assert not isinstance(music, RatioProduct)

        multiplier = prod(ratio_products, RatioProduct())

        new_music: Music = apply_to_notes(
            music,
            lambda x: Note(
                frequency=RatioProduct(multiplier) * x.frequency,
                duration=x.duration,
                volume=x.volume,
            ),
        )

        return new_music

    def power(self, children: List[Union[Music, RatioProduct]]) -> Music:
        """
        Multiply note volume by exponent.

        Parameters
        ----------
        children : list of Music or RatioProduct
            Two element list of music and exponent.

        Returns
        -------
        Music
            Music with its volume multiplied.
        """
        music, volume_multiplier = children
        assert not isinstance(music, RatioProduct)
        assert isinstance(volume_multiplier, RatioProduct)
        new_music: Music = apply_to_notes(
            music,
            lambda x: Note(
                frequency=x.frequency,
                duration=x.duration,
                volume=volume_multiplier * x.volume,  # type: ignore[operator]
            ),
        )
        return new_music

    def note(self, children: List[Optional[RatioProduct]]) -> List[Note]:
        """
        Convert frequency, duration, and volume into corresponding note.

        Parameters
        ----------
        children : list of RatioProduct
            Three element list containing frequency, duration, and volume of a note.
            Volume can be None.

        Returns
        -------
        list of Note
            List containing a single `Note` of given frequency, duration, and
            volume. Volume is defaulted to one.
        """
        frequency, duration, volume = children
        assert frequency is not None
        assert duration is not None
        return [
            Note(
                frequency=frequency,
                duration=duration,
                volume=volume if volume is not None else Fraction(1),
            ),
        ]

    def chord(self, children: List[Optional[RatioProduct]]) -> List[Tuple[Note, ...]]:
        """
        Convert list of frequencies, duration, and volume into the corresponding chord.

        Parameters
        ----------
        children : list of RatioProduct
            List containing the frequencies of the notes in the chord along with
            the duration of the chord as the second last element and the volume as
            the last element. Volume can be None.

        Returns
        -------
        list of tuple of Note
            List containing a single tuple of notes making up the given chord.
        """
        frequencies = children[:-2]
        duration = children[-2]
        volume = children[-1]

        assert duration is not None
        notes = []
        for f in frequencies:
            assert f is not None
            notes.append(
                Note(
                    frequency=f,
                    duration=duration,
                    volume=volume if volume is not None else Fraction(1),
                )
            )
        return [tuple(notes)]

    def part(self, children: List[List[Music]]) -> List[Music]:
        """
        Combine musics sequentially by forming a single list from them.

        Parameters
        ----------
        children : list of list of Music
            List of individual musics to combine sequentially.

        Returns
        -------
        list of Music
            Single list of all musics joined together.
        """
        return list(chain.from_iterable(children))

    def music(self, children: List[Music]) -> Tuple[Music, ...]:
        """
        Combine musics simultaneously by forming a tuple of them.

        Parameters
        ----------
        children : list of Music
            List of musics to combine simultaneously.

        Returns
        -------
        tuple of Music
            Tuple of individual musics to be played simultaneously.
        """
        return tuple(children)


def parse(input_string: str) -> Piece:
    """
    Parse text into music.

    Parameters
    ----------
    input_string: str
        String containing the musical notation as text.

    Returns
    -------
    Piece
        Music corresponding to the text in `input_string`

    Examples
    --------
    One note.

    >>> parse("7/5:1")
    ([Note(frequency=7/5, cents=582.512, duration=1)],)

    Two notes in succession.

    >>> print_music(parse("2:1/4 6/5:1/4"))
    (
      [
        Note(frequency=2, cents=1200.0, duration=1/4),
        Note(frequency=6/5, cents=315.641, duration=1/4),
      ],
    ),

    A chord.

    >>> print_music(parse("<1 7/6 16/9>:1/4"))
    (
      [
        (
          Note(frequency=1, cents=0.0, duration=1/4),
          Note(frequency=7/6, cents=266.871, duration=1/4),
          Note(frequency=16/9, cents=996.09, duration=1/4),
        ),
      ],
    ),
    """
    tree = PARSER.parse(input_string)
    music = NoteTransformer().transform(tree)
    logger.info("Parsed music of total duration %d", total_duration(music))
    return music


def temper_note(note: Note, *, edo: int) -> Note:
    """
    Temper single note.

    Approximates frequency of `note` by one of the frequencies obtained by
    splitting the octave into `edo` parts.

    Parameters
    ----------
    note : Note
        Note to temper.
    edo : int
        Number of Equal Divisions of the Octave to select the tempered frequency
        from. For example `edo = 12` is the common equal temperament. Other
        popular values are 19, 31, and 53, but anything is possible and perhaps
        interesting.

    Returns
    -------
    Note
        Closest approximation to `note` in a system of `edo` equal divisions of
        the octave.

    Examples
    --------
    Consider a minor third (frequency ratio 6/5):

    >>> note = parse("6/5:1")[0][0]
    >>> note
    Note(frequency=6/5, cents=315.641, duration=1)

    Tempering with twelve notes gives three ordinary semitones, exactly
    300 cents.

    >>> temper_note(note, edo=12)
    Note(frequency=2**3/12, cents=300.0, duration=1)

    Tempering with nineteen notes gives a very close approximation to the
    just frequency.

    >>> temper_note(note, edo=19)
    Note(frequency=2**5/19, cents=315.789, duration=1)

    Notes
    -----
    A ratio product has each term tempered separately (rather than first
    multiplying terms then tempering). This is to preserve the tempered
    intervals within a chord when its frequency is multiplied. For example
    <1 5/4 11/8>:1 is tempered in 12EDO to 0, 4, 6 steps, but 80/81*<1
    5/4 11/8>:1 would be tempered to 0, 4, 5 steps. From listening to
    automatically tempered just intonation music (e.g. megamorsel in music dir
    in this repo), this shifting of chord quality can sound strange. Tempering
    each term in a product separately makes sure that the intervals within
    the chord remain unchanged by multiplication.
    """
    frequency = evaluate(note.frequency)
    if frequency == 0:
        return note
    if isinstance(note.frequency, RatioProduct):
        n = sum(round(edo * math.log2(x)) for x in note.frequency.ratios)
    else:
        n = round(edo * math.log2(frequency))
    new_frequency = Power(2, n, edo)
    return Note(frequency=new_frequency, duration=note.duration, volume=note.volume)


def temper(music: Piece, *, edo: Optional[int]) -> Piece:
    """
    Temper all notes in music.

    Parameters
    ----------
    music : Piece
        Music to temper.
    edo : int, optional
        Number of Equal Divisions of the Octave to use for tempering. No tempering
        done if `edo` is None.

    Returns
    -------
    Piece
        Tempered version of `music`.
    """
    if edo is None:
        return music
    logger.info("Tempering to %d edo", edo)
    tempered_music: Piece = apply_to_notes(music, partial(temper_note, edo=edo))
    return tempered_music


def evaluate(quantity: Union[Unevaluated, Number]) -> Number:
    """
    Evaluate a quantity.

    For quantities which are `Unevaluated` call their `evaluate` to force evaluation.

    Parameters
    ----------
    quantity : Unevaluated or Number
        quantity to evaluate.

    Returns
    -------
    Number
        Evaluated quantity

    Examples
    --------
    >>> quantity = RatioProduct((Fraction(5, 4), Fraction(6, 5)))
    >>> quantity
    5/4*6/5
    >>> evaluate(quantity)
    Fraction(3, 2)

    >>> evaluate(Fraction(7, 6))
    Fraction(7, 6)
    """
    if isinstance(quantity, Unevaluated):
        return quantity.evaluate()
    return quantity


def total_duration(music: Music) -> Number:
    """
    Find total duration of music.

    Takes largest duration if `music` contains simultaneous pieces of
    different duration.

    Parameters
    ----------
    music : Music
        Music to find duration of.

    Returns
    -------
    Number
        Total duration of music.

    Examples
    --------
    >>> music = parse("7/6:1/4 4/3:1/4")
    >>> total_duration(music)
    Fraction(1, 2)

    >>> music = parse("2:1 3/2:1; 1/2:2")
    >>> total_duration(music)
    Fraction(2, 1)
    """
    if isinstance(music, Note):
        return evaluate(music.duration)

    if isinstance(music, tuple):
        return max(total_duration(x) for x in music) if music else 0

    if isinstance(music, list):
        return sum(total_duration(x) for x in music) if music else 0

    raise ValueError(music)


def frequencies_set(music: Music) -> Set[Number]:
    """
    Find set of all frequencies used in `music`.

    Parameters
    ----------
    music : Music
        Music to find frequencies in.

    Returns
    -------
    set of {fraction or float}
        Set of all frequencies in `music`
    """
    if isinstance(music, Note):
        frequency = evaluate(music.frequency)
        return {frequency} if frequency != 0 else set()
    return set(chain.from_iterable(frequencies_set(x) for x in music))


def all_frequencies(music: Music) -> List[Number]:
    """
    Find all frequencies in `music`.

    Parameters
    ----------
    music : Music
        Music to find frequencies in.

    Returns
    -------
    list of [Fraction or float]
        List of all frequencies in `music` sorted from lowest to highest.

    Examples
    --------
    Any products are evaluated so frequencies are given in their simplest form.

    >>> music = parse("1:1 5/4:1 4/3*5/4:1")
    >>> all_frequencies(music)
    [Fraction(1, 1), Fraction(5, 4), Fraction(5, 3)]

    This can be used to find a scale in which all notes in `music` can be found.

    >>> music = parse("10/9*<1 6/5 9/5>:1 3/2*<1 5/4>:1")
    >>> all_frequencies(music)
    [Fraction(10, 9), Fraction(4, 3), Fraction(3, 2), Fraction(15, 8), Fraction(2, 1)]
    """
    return sorted(frequencies_set(music))


def height(music: Music) -> int:
    """
    Measure of number of simultaneous notes in `music`.

    Used for example to assign enough midi channels to each part in
    :func:`jird.midi.music_to_midi_file`.

    Parameters
    ----------
    music : Music
        Music to measure height of.

    Returns
    -------
    int
        Measure of simultaneous height of `music`.

    Examples
    --------
    >>> height(parse("<1 5/4 3/2 7/4>:1"))
    4

    >>> height(parse("<1 5/4 3/2 7/4>:1; 1/2:1"))
    5

    >>> height(parse("1:1/4 9/8:1/4 5/4:1/2; 1/2:1/2 3/4:1/2"))
    2
    """
    if not music:
        return 0

    if isinstance(music, Note):
        return 1

    if isinstance(music, tuple):
        return sum(height(x) for x in music)

    if isinstance(music, list):
        return max(height(x) for x in music)

    raise ValueError(music)


def lowest(music: Music) -> Number:
    """
    Find lowest frequency in `music`.

    Parameters
    ----------
    music : Music
        Music to containing frequencies to consider.

    Returns
    -------
    Number
        Lowest frequency in `music`.
    """
    if not music:
        return float("inf")

    if isinstance(music, Note):
        frequency = evaluate(music.frequency)
        # Rests have zero frequency so we should ignore them
        return frequency if frequency != 0 else float("inf")

    return min(lowest(x) for x in music)


def print_music(music: Music, level: int = 0) -> None:
    """
    Pretty print `music`.

    Parameters
    ----------
    music : Music
        Music to be printed.
    level : int
        Indentation level. Defaults to 0. Used to indent nested pieces of music
        when `print_music` is called recursively.
    """
    indent = "  "
    if isinstance(music, Note):
        print(level * indent + f"{music},")
    elif isinstance(music, tuple):
        print(level * indent + "(")
        for x in music:
            print_music(x, level + 1)
        print(level * indent + "),")
    elif isinstance(music, list):
        print(level * indent + "[")
        for y in music:
            print_music(y, level + 1)
        print(level * indent + "],")
    else:
        raise ValueError(music)


def interval_table(frequencies: Iterable[Number]) -> List[List[Number]]:
    """
    Find interval between each pair of frequencies in `frequencies`.

    Parameters
    ----------
    frequencies : iterable of Ratio
        Frequencies to find intervals between.

    Returns
    -------
    list of list of Ratio
        All intervals between frequencies.

    Examples
    --------
    >>> table = interval_table([Fraction(1), Fraction(5, 4), Fraction(3, 2)])
    >>> for row in table: print(row)
    [Fraction(1, 1), Fraction(5, 4), Fraction(3, 2)]
    [Fraction(4, 5), Fraction(1, 1), Fraction(6, 5)]
    [Fraction(2, 3), Fraction(5, 6), Fraction(1, 1)]
    """
    return [[evaluate(x / y) for x in frequencies] for y in frequencies]


def print_interval_table(music: Music) -> None:
    """
    Print interval table built from all frequencies in `music`.

    Parameters
    ----------
    music : Music
        Music containing frequencies to build intervals from.

    Examples
    --------
    >>> print_interval_table(parse("<1 7/6 4/3>:1"))
    <BLANKLINE>
             1  7/6  4/3
         ---------------
      1  |   1  7/6  4/3
    7/6  | 6/7    1  8/7
    4/3  | 3/4  7/8    1
    <BLANKLINE>
    """
    frequencies = all_frequencies(music)
    if not frequencies:
        return
    table = interval_table(frequencies)
    table_width = max(len(str(x)) for x in chain.from_iterable(table))
    music_width = max(len(str(x)) for x in frequencies)
    width = max(table_width, music_width)
    separator = "  "
    border = "  | "
    header = separator.join(f"{x!s:>{width}}" for x in frequencies)
    spaces = (width + len(border)) * " "
    overlap = 2
    print()
    print(spaces + header)
    print(spaces[:-overlap] + (len(header) + overlap) * "-")
    for i, row in enumerate(table):
        print(
            f"{frequencies[i]!s:>{width}}"
            + border
            + separator.join(f"{x!s:>{width}}" for x in row)
        )
    print()


T = TypeVar("T", int, Fraction, RatioProduct)


def prod(quantities: Iterable[T], initializer: T) -> T:
    """
    Compute product.

    Used instead of math.prod to support Python 3.7.

    Parameters
    ----------
    quantities : iterable of T
        Things to multiply.
    initializer : T
        First element to use in product.

    Returns
    -------
    T
        Product of `quantities`.
    """
    return reduce(operator.mul, quantities, initializer)
