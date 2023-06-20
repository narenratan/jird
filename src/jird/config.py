"""Config for jird."""
import os
from dataclasses import dataclass, field, fields
from enum import Enum
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import jird.data
from jird.constants import Synth, TuningMethod

with resources.path(jird.data, "default.fxp") as path:
    DEFAULT_SURGE_PATCH = path

with resources.path(jird.data, "default.xiz") as path:
    DEFAULT_ZYN_PATCH = path

_DEFAULT_SOUNDFONT = os.getenv("JIRD_SOUNDFONT")
DEFAULT_SOUNDFONT = Path(_DEFAULT_SOUNDFONT) if _DEFAULT_SOUNDFONT is not None else None


U = TypeVar("U", str, float, int)


def _as_type(t: Type[U], x: Optional[Union[str, float, int]]) -> Optional[U]:
    return t(x) if x is not None else None


def _as_path(x: Optional[str]) -> Optional[Path]:
    return Path(x).expanduser() if x is not None else None


@dataclass
class PartConfig:
    """
    Config for each jird part.

    Attributes
    ----------
    volume : float
        Volume for this part.
    panning : int
        Pan (position left/right in stereo image) for this part.
    instrument : Path, optional
        Path to instrument patch to use for this part. For ZynAddSubFX this is
        an xiz file. For Surge XT this is an fxp file.  Not used by fluidsynth.
    program : int, optional
        Midi program to use for this part. Used with fluidsynth to specify which
        instrument in the soundfont to use.
    """

    volume: float = 0.0
    panning: Optional[Union[float, int]] = None
    instrument: Optional[Path] = None
    program: Optional[int] = None

    def __post_init__(self) -> None:
        if self.program is not None:
            assert self.program > 0
        if self.instrument is not None:
            assert self.instrument.exists(), f"Could not find {self.instrument}"


T = TypeVar("T", bound="Config")


@dataclass
class Config:  # pylint: disable=R0902
    """
    Overall config controlling jird.

    Attributes
    ----------
    t : float
        Basic time in seconds. Real note durations are the jird duration
        multiplied by this basic time. For example the note 1:1 will have duration
        `t` when played back.
    f : float
        Basic frequency in Hz. Real note frequencies are the jird note frequency
        multiplied by this basic frequency. For example the note 1:1 will have
        frequency `f` when played back.
    tuning_method : TuningMethod
        Method to use for tuning midi notes to the desired frequency. Choices are
        `PITCH_BEND`, which sends a pitch bend before each midi note to adjust
        its frequency, and `SCALA`, which uses Scala scl and kbm files to map
        each midi note onto its frequency.
    synth : Synth
        Synth to use for playback. Choices are FLUIDSYNTH, ZYNADDSUBFX, and SURGE_XT.
    volume : float
        Overall volume for playback. Interpretation varies by synth; typical
        values are given in the example configs for each synth.
    pitch_bend_range : int
        Midi pitch bend range, in semitones, to assume when calculating
        bends. Defaults to two.
    edo : int, optional
        If specified, music is tempered using `edo` equal divisions of the octave.
    sample_rate : int
        Sample rate to use when rendering audio. Defaults to 44100
    soundfont : Path, optional
        Path of soundfont to use when using fluidsynth.
    verbose : bool
        Whether to show logs and subprocess output. Defaults to False.
    parts : list of PartConfig
        Part-specific config for each jird part. See PartConfig for details.
    """

    t: float = 0.5
    f: float = 440.0
    tuning_method: TuningMethod = TuningMethod.SCALA
    synth: Synth = Synth.FLUIDSYNTH

    volume: float = 2.0
    pitch_bend_range: int = 2
    edo: Optional[int] = None
    sample_rate: int = 44100
    soundfont: Optional[Path] = DEFAULT_SOUNDFONT
    verbose: bool = False

    parts: List[PartConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        assert self.t > 0
        assert self.f > 0
        if self.edo is not None:
            assert self.edo > 0
        if self.synth == Synth.FLUIDSYNTH:
            self._setup_for_fluidsynth()
        if self.synth == Synth.SURGE_XT:
            self._setup_for_surge()
        if self.synth == Synth.ZYNADDSUBFX:
            self._setup_for_zyn()

    def _setup_for_fluidsynth(self) -> None:
        assert 0 <= self.volume <= 10
        assert 8000 <= self.sample_rate <= 96000

    def _setup_for_surge(self) -> None:
        for p in self.parts:
            assert -48 <= p.volume <= 0
            if p.panning is None:
                p.panning = 0.0
            assert -1 <= p.panning <= 1
            if p.instrument is None:
                p.instrument = DEFAULT_SURGE_PATCH

    def _setup_for_zyn(self) -> None:
        for p in self.parts:
            if p.panning is None:
                p.panning = 64
            else:
                p.panning = int(p.panning)
                assert 0 <= p.panning <= 128
            if p.instrument is None:
                p.instrument = DEFAULT_ZYN_PATCH

    @classmethod
    def from_dict(cls: Type[T], config_dict: Dict[str, Any]) -> T:
        """Build Config from dictionary."""
        field_names = {x.name for x in fields(cls)}
        attrs = {k: v for k, v in config_dict.items() if k in field_names}
        if "soundfont" in attrs:
            attrs["soundfont"] = _as_path(config_dict["soundfont"])
        if "tuning_method" in attrs:
            attrs["tuning_method"] = _to_enum(
                config_dict["tuning_method"], TuningMethod
            )
        if "synth" in attrs:
            attrs["synth"] = _to_enum(config_dict["synth"], Synth)
        if "parts" in config_dict:
            attrs["parts"] = []
            for part in config_dict["parts"]:
                attrs["parts"].append(
                    PartConfig(
                        volume=part.get("volume", 0.0),
                        panning=_as_type(float, part.get("panning")),
                        instrument=_as_path(part.get("instrument")),
                        program=_as_type(int, part.get("program")),
                    )
                )
        elif "programs" in config_dict:
            attrs["parts"] = [
                PartConfig(program=int(x)) for x in config_dict["programs"].split(",")
            ]
        else:
            config_instrument = config_dict.get("instrument")
            attrs["parts"] = [PartConfig(instrument=_as_path(config_instrument))]

            # Infer synth from patch file extension
            if config_instrument is not None:
                if config_instrument.endswith(".fxp"):
                    attrs["synth"] = Synth.SURGE_XT
                if config_instrument.endswith(".xiz"):
                    attrs["synth"] = Synth.ZYNADDSUBFX

        return cls(**attrs)


V = TypeVar("V", bound=Enum)


def _to_enum(x: str, enum: Type[V]) -> V:
    try:
        return enum[x.upper()]
    except KeyError:
        print(
            f"\n{enum.__name__} '{x}' not recognized."
            + f"\n\nSupported {enum.__name__}s: {[x.name for x in enum]}\n"
        )
        raise
