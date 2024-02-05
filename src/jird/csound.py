"""
Translate jird music into a Csound score.

For more information on Csound see the `Csound website <https://csound.com/>`_.
"""
from pathlib import Path
from typing import List, Tuple, Union

from jird.core import Chord, Note, Part, Piece, evaluate


def csound_chord(
    chord: Chord, f0: float, t0: float, t: float, instrument: int
) -> Tuple[List[str], float]:
    """
    Build Csound score representation of `chord`.

    Parameters
    ----------
    chord : Chord
        Chord to represent.
    f0 : float
        Base frequency in Hz.
    t0 : float
        Base time unit in seconds.
    t : float
        Start time of the chord in seconds.
    instrument : int
        Csound instrument number to use for this chord.

    Returns
    -------
    (list of str, float)
        First element is list of Csound lines to play the notes in `chord`. Second
        element is the duration of `chord` in seconds.
    """
    notes = []
    for note in chord:
        real_duration = float(evaluate(note.duration) * t0)
        real_frequency = float(evaluate(note.frequency) * f0)
        volume = float(evaluate(note.volume))
        notes.append(f"i {instrument} {t} {real_duration} {volume} {real_frequency}")
    return notes, real_duration


def csound_part(part: Part, f0: float, t0: float, instrument: int) -> str:
    """
    Build Csound score representing `music` with one part.

    Parameters
    ----------
    part : Part
        Music to represent.
    f0 : float
        Base frequency in Hz.
    t0 : float
        Base time unit in seconds.
    instrument : int
        Csound instrument number to use for this part.

    Returns
    -------
    str
        Csound representation of `music`.
    """
    t = 0.0
    lines = []
    for x in part:
        chord = (x,) if isinstance(x, Note) else x
        notes, real_duration = csound_chord(chord, f0, t0, t, instrument)
        lines.extend(notes)
        t += real_duration
    return "\n".join(lines)


def csound_score(music: Piece, f0: float, t0: float) -> str:
    """
    Build Csound score representing `music` with multiple parts.

    Parameters
    ----------
    music : Piece
        Music to represent.
    f0 : float
        Base frequency in Hz.
    t0 : float
        Base time unit in seconds.

    Returns
    -------
    str
        Csound representation of `music`.
    """
    return "\n\n".join(
        csound_part(x, f0, t0, instrument=i + 1) for i, x in enumerate(music)
    )


def write_csound_score(
    music: Piece, f0: float, t0: float, output_path: Union[str, Path]
) -> None:
    """
    Write Csound score representing `music` to a file.

    Parameters
    ----------
    music : Piece
        Music to represent.
    f0 : float
        Base frequency in Hz.
    t0 : float
        Base time unit in seconds.
    output_path : str or Path
        Filename for writing output.
    """
    with open(output_path, "w", encoding="utf8") as f:
        f.write(csound_score(music, f0, t0))
