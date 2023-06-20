"""Constants used in multiple modules."""
from enum import Enum, auto

DIVISION = 960 * 7
"""
Midi ticks per quarter note.
"""

MIDDLE_C_FREQUENCY = 2 ** (-9 / 12) * 440
"""
Take middle C as 9 semitones below A 440 Hz
"""

PITCH_BEND_MAX = 0x3FFF
"""
Largest midi pitch bend value
"""

PITCH_BEND_CENTER = 0x2000
"""
Midi pitch bend value corresponding to no bend
"""

REST_FREQUENCY = 0
"""
Frequency representing a rest.
"""


class TuningMethod(Enum):
    """
    Possible methods for retuning midi notes to just intonation.

    PITCH_BEND uses midi pitch bends before each note to adjust their tuning.
    SCALA uses Scala scale and keyboard map files to retune a compatible synth.
    """

    PITCH_BEND = auto()
    SCALA = auto()


class Synth(Enum):
    """
    Synths wired in to jird.

    These can be used directly with jird (no DAW needed).
    """

    FLUIDSYNTH = auto()
    ZYNADDSUBFX = auto()
    SURGE_XT = auto()
