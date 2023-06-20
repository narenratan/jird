# pylint: disable=too-many-instance-attributes,invalid-name,missing-class-docstring,fixme
# Number and names of fields are determined by Zyn xml format
"""
Code for calling the `ZynAddSubFX synth <https://github.com/zynaddsubfx/zynaddsubfx>`_.

Zyn does not have a Python API but it can:

    #. Save its whole state to a master xml file
    #. Load instruments from xml files

This module implements reading and writing Zyn xml files. It allows jird
to automatically retune and configure Zyn by loading Zyn instruments
and building a Zyn master xml.

It turns out that while the master xml file does contain blocks
corresponding to the xml in the loaded instrument xml, Zyn does quite a
bit of processing of the instrument xml before it is added to the master.
Most of this is implemented here (some of the version-specific adjustments
are not yet implemented).
"""
import gzip
import logging
import math
import struct
import subprocess
import xml.etree.ElementTree as ET  # noqa: N817
from dataclasses import dataclass, field, fields, is_dataclass, replace
from fractions import Fraction
from itertools import chain
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Tuple, Type, TypeVar, Union, get_origin

from jird.config import Config, PartConfig
from jird.constants import TuningMethod
from jird.process import run, run_async
from jird.scala import (
    ScalaData,
    ScalaKeyboardMap,
    ScalaScale,
)

logger = logging.getLogger(__name__)

LOWER_CASE_FIELDS = {"par_no"}

SerializableType = TypeVar("SerializableType", bound="Serializable")


@dataclass
class Serializable:
    """
    Base class for Zyn config blocks.

    Any block can be written-to/loaded-from xml following Zyn's conventions.
    """

    def to_xml(
        self,
        filename: Union[str, Path],
        tag: Optional[str] = None,
        attrib: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Write block to Zyn-format xml.

        Parameters
        ----------
        filename : str or Path
            Output filename.
        tag : str, optional
            Tag to use for root node of xml. Uses the upper-cased class name if no
            tag provided.
        attrib : dict {str : str}, optional
            Attributes for the root note of the xml.
        """
        logger.info("Writing %s", filename)
        root_tag = type(self).__name__.upper() if tag is None else tag
        attrib = {} if attrib is None else attrib
        root_node = ET.Element(root_tag, attrib)
        _add_to_xml(self, root_node)
        tree = ET.ElementTree(root_node)
        tree.write(filename, encoding="UTF-8", xml_declaration=True)

    @classmethod
    def from_xml(
        cls: Type[SerializableType],
        filename: Union[str, Path],
        tag: Optional[str] = None,
    ) -> SerializableType:
        """
        Load config block from Zyn-format xml.

        Parameters
        ----------
        filename : str or Path
            Filename of input xml. Can be gzipped.
        tag : str, optional
            Tag of block to pull from xml. Whole xml is loaded if no tag is provided.

        Returns
        -------
        SerializableType
            Instance of the particular config block being loaded.
        """
        logger.info("Loading %s", filename)
        try:
            with gzip.open(filename, "rt", encoding="utf8") as f:
                string = f.read()
        except gzip.BadGzipFile:
            with open(filename, "r", encoding="utf8") as f:
                string = f.read()
        node = ET.fromstring(string.strip())

        version = None
        if node.tag == "ZynAddSubFX-data":
            version = (
                int(node.attrib["version-major"]),
                int(node.attrib["version-minor"]),
                int(node.attrib.get("version-revision", 0)),
            )

        if tag is not None:
            tag_node = node.find(tag)
            assert tag_node is not None
            node = tag_node

        return _from_xml_node(cls, node, version=version)


@dataclass
class BaseParameters(Serializable):
    max_midi_parts: int = 16
    max_kit_items_per_instrument: int = 16
    max_system_effects: int = 4
    max_insertion_effects: int = 8
    max_instrument_effects: int = 3
    max_addsynth_voices: int = 8


@dataclass
class Degree(Serializable):
    id: int  # noqa: A003
    numerator: Optional[int] = None
    denominator: Optional[int] = None
    cents: Optional[float] = None
    exact_value: Optional[str] = None


@dataclass
class Octave(Serializable):
    octave_size: int
    degree: Tuple[Degree, ...]


@dataclass
class KeyMap(Serializable):
    id: int  # noqa: A003
    degree: int


@dataclass
class KeyboardMapping(Serializable):
    map_size: int
    mapping_enabled: int
    keymap: Tuple[KeyMap, ...]


@dataclass
class Scale(Serializable):
    octave: Octave
    keyboard_mapping: KeyboardMapping

    first_key: int
    last_key: int
    middle_note: int
    scale_shift: int = 64


@dataclass
class Microtonal(Serializable):
    scale: Optional[Scale] = None

    name: str = ""
    comment: str = ""
    invert_up_down: bool = False
    invert_up_down_center: int = 60
    enabled: bool = False
    global_fine_detune: int = 64
    a_note: int = 69
    a_freq: float = 440.0


def build_microtonal_from_scala(
    scale: ScalaScale,
    keyboard_map: ScalaKeyboardMap,
) -> Microtonal:
    """Build Zyn microtonal config from Scala data."""
    # Zyn xmz expects the float frequency ratio in the cents field rather than cents value.
    octave = Octave(
        octave_size=scale.number_of_notes,
        degree=tuple(
            Degree(id=i, numerator=x.numerator, denominator=x.denominator)
            if isinstance(x, Fraction)
            else Degree(id=i, cents=x, exact_value=float_to_hex(x))
            for i, x in enumerate(scale.frequencies)
        ),
    )
    keyboard_mapping = KeyboardMapping(
        map_size=keyboard_map.size,
        mapping_enabled=1,
        keymap=tuple(
            KeyMap(id=i, degree=x) for i, x in enumerate(keyboard_map.mapping)
        ),
    )
    zyn_scale = Scale(
        octave=octave,
        keyboard_mapping=keyboard_mapping,
        first_key=keyboard_map.first_midi_note,
        last_key=keyboard_map.last_midi_note,
        middle_note=keyboard_map.middle_note,
    )
    return Microtonal(
        scale=zyn_scale,
        enabled=True,
        a_note=keyboard_map.reference_note,
        a_freq=keyboard_map.reference_frequency,
    )


@dataclass
class Info(Serializable):
    type: int  # noqa: A003
    name: str
    author: str
    comments: str


@dataclass
class ParNo(Serializable):
    id: int  # noqa: A003
    par: int


@dataclass
class EffectParameters(Serializable):
    par_no: Tuple[ParNo, ...]


@dataclass
class Effect(Serializable):
    type: Optional[int] = None  # noqa: A003
    preset: Optional[int] = None
    numerator: Optional[int] = None
    denominator: Optional[int] = None
    effect_parameters: Optional[EffectParameters] = None

    def __post_init__(self) -> None:
        if self.type != 0:
            self.numerator = 0
            self.denominator = 4


@dataclass
class InstrumentEffect(Serializable):
    id: int  # noqa: A003
    effect: Effect
    route: int
    bypass: bool


@dataclass
class Envelope(Serializable):
    free_mode: bool
    env_points: int
    env_sustain: int
    env_stretch: int
    forced_release: bool
    linear_envelope: bool
    A_dt: float
    D_dt: float
    R_dt: float
    A_val: int
    D_val: int
    S_val: int
    R_val: int
    # TODO add other defaults from zynaddsubfx/src/Params/EnvelopeParams.cpp
    # TODO possibly implement version fix
    repeating_envelope: bool = False

    def __post_init__(self) -> None:
        for x in ["A_dt", "D_dt", "R_dt"]:
            param = getattr(self, x)
            if isinstance(param, int):
                setattr(self, x, (2 ** (param / 127 * 12) - 1) / 100)


@dataclass
class LFO(Serializable):
    freq: float
    intensity: int
    start_phase: int
    lfo_type: int
    randomness_amplitude: int
    randomness_frequency: int
    delay: float
    stretch: int = 64
    continous: bool = False
    cutoff: Optional[int] = 127
    fadein: Optional[float] = 0.0
    fadeout: Optional[float] = 10.0
    numerator: Optional[int] = 0
    denominator: Optional[int] = 4

    def __post_init__(self) -> None:
        if isinstance(self.delay, int):
            self.delay = 4 * self.delay / 127


@dataclass
class AmplitudeParameters(Serializable):
    volume: float
    panning: int
    velocity_sensing: int

    punch_strength: Optional[int] = None
    punch_time: Optional[int] = None
    punch_stretch: Optional[int] = None
    punch_velocity_sensing: Optional[int] = None
    harmonic_randomness_grouping: Optional[int] = None
    amplitude_envelope: Optional[Envelope] = None
    amplitude_lfo: Optional[LFO] = None
    volume_minus: Optional[bool] = None
    fadein_adjustment: Optional[int] = None
    amp_envelope_enabled: Optional[bool] = None
    amp_lfo_enabled: Optional[bool] = None
    stereo: Optional[bool] = None


@dataclass
class FrequencyParameters(Serializable):
    detune: int
    coarse_detune: int
    detune_type: int

    freq_envelope_enabled: Optional[bool] = None
    frequency_envelope: Optional[Envelope] = None

    freq_lfo_enabled: Optional[bool] = None
    frequency_lfo: Optional[LFO] = None

    band_width_envelope_enabled: Optional[bool] = None
    bandwidth_envelope: Optional[Envelope] = None

    bandwidth: Optional[int] = None
    bandwidth_scale: Optional[int] = None
    fixed_freq: Optional[bool] = None
    fixed_freq_et: Optional[int] = None
    bend_adjust: Optional[int] = None
    offset_hz: Optional[int] = None
    overtone_spread_type: Optional[int] = None
    overtone_spread_par1: Optional[int] = None
    overtone_spread_par2: Optional[int] = None
    overtone_spread_par3: Optional[int] = None


@dataclass
class Filter(Serializable):
    category: int
    type: int  # noqa: A003
    stages: int
    gain: float

    freq: Optional[int] = None
    q: Optional[int] = None
    freq_track: Optional[int] = None

    basefreq: Optional[float] = None
    baseq: Optional[float] = None
    freq_tracking: Optional[float] = None

    def __post_init__(self) -> None:
        if self.basefreq is None:
            assert self.freq is not None
            self.basefreq = 2 ** ((self.freq / 64 - 1) * 5 + 9.96578428)
            self.freq = None

            # baseq     = expf(powf((float) Pq / 127.0f, 2) * logf(1000.0f)) - 0.9f;
            assert self.q is not None
            self.baseq = math.exp((self.q / 127) ** 2 * math.log(1000)) - 0.9
            self.q = None

            self.gain = (self.gain / 64 - 1) * 30

            assert self.freq_track is not None
            self.freq_tracking = 100 * (self.freq_track - 64) / 64
            self.freq_track = None


@dataclass
class FilterParameters(Serializable):
    enabled: bool = False
    velocity_sensing_amplitude: Optional[int] = None
    velocity_sensing: Optional[int] = None

    filter: Optional[Filter] = None  # noqa: A003
    filter_envelope: Optional[Envelope] = None
    filter_lfo: Optional[LFO] = None


@dataclass
class Resonance(Serializable):
    enabled: bool


@dataclass
class Harmonic(Serializable):
    id: int  # noqa: A003
    mag: int
    phase: Optional[int] = None
    relbw: Optional[int] = None


@dataclass
class Harmonics(Serializable):
    harmonic: Tuple[Harmonic, ...]


@dataclass
class Oscil(Serializable):
    harmonics: Harmonics

    harmonic_mag_type: int
    base_function: int
    base_function_par: int
    base_function_modulation: int
    base_function_modulation_par1: int
    base_function_modulation_par2: int
    base_function_modulation_par3: int
    modulation: int
    modulation_par1: int
    modulation_par2: int
    modulation_par3: int
    wave_shaping: int
    wave_shaping_function: int
    filter_type: int
    filter_par1: int
    filter_par2: int
    filter_before_wave_shaping: int
    spectrum_adjust_type: int
    spectrum_adjust_par: int
    rand: int
    amp_rand_type: int
    amp_rand_power: int
    harmonic_shift: int
    harmonic_shift_first: bool
    adaptive_harmonics: int
    adaptive_harmonics_base_frequency: int
    adaptive_harmonics_power: int
    adaptive_harmonics_par: Optional[int] = 50


@dataclass
class Voice(Serializable):
    id: int  # noqa: A003
    enabled: bool

    oscil: Optional[Oscil] = None
    amplitude_parameters: Optional[AmplitudeParameters] = None
    frequency_parameters: Optional[FrequencyParameters] = None
    type: Optional[int] = None  # noqa: A003
    unison_frequency_spread: Optional[int] = 60
    unison_invert_phase: Optional[int] = 0
    unison_phase_randomness: Optional[int] = 127
    unison_size: Optional[int] = 1
    unison_stereo_spread: Optional[int] = 64
    unison_vibratto: Optional[int] = 64
    unison_vibratto_speed: Optional[int] = 64
    delay: Optional[int] = None
    resonance: Optional[bool] = None
    ext_oscil: Optional[int] = None
    ext_fm_oscil: Optional[int] = None
    oscil_phase: Optional[int] = None
    oscil_fm_phase: Optional[int] = None
    filter_bypass: Optional[bool] = None
    filter_enabled: Optional[bool] = None
    filter_fcctl_bypass: Optional[bool] = False
    fm_enabled: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.enabled:
            for f in fields(self):
                if f.name not in {"id", "enabled"}:
                    setattr(self, f.name, None)
            return
        # TODO possibly implement version fix for 3.0.5
        # see zynaddsubfx/src/Params/ADnoteParameters.cpp line 976
        if self.amplitude_parameters and isinstance(
            self.amplitude_parameters.volume, int
        ):
            self.amplitude_parameters.volume = -60 * (
                1 - self.amplitude_parameters.volume / 127
            )
        if self.frequency_parameters:
            if self.frequency_parameters.bend_adjust is None:
                self.frequency_parameters.bend_adjust = 88
            if self.frequency_parameters.offset_hz is None:
                self.frequency_parameters.offset_hz = 64


DISABLED_VOICE = Voice(id=0, enabled=False)


@dataclass
class AddSynthParameters(Serializable):
    stereo: bool

    amplitude_parameters: AmplitudeParameters
    frequency_parameters: FrequencyParameters
    filter_parameters: FilterParameters
    resonance: Resonance
    voice: Tuple[Voice, ...]

    def __post_init__(self) -> None:
        # TODO possibly implement version fix for 3.0.5
        # see zynaddsubfx/src/Params/ADnoteParameters.cpp line 976
        if self.amplitude_parameters:
            if isinstance(self.amplitude_parameters.volume, int):
                self.amplitude_parameters.volume = 12.0412 - 60 * (
                    1 - self.amplitude_parameters.volume / 96
                )
            if self.amplitude_parameters.fadein_adjustment is None:
                self.amplitude_parameters.fadein_adjustment = 20
        if self.frequency_parameters and self.frequency_parameters.bandwidth is None:
            self.frequency_parameters.bandwidth = 64


@dataclass
class HarmonicPosition(Serializable):
    parameter1: int
    parameter2: int
    parameter3: int
    type: int  # noqa: A003


@dataclass
class HarmonicProfile(Serializable):
    amplitude_multiplier_mode: int = 0
    amplitude_multiplier_par1: int = 80
    amplitude_multiplier_par2: int = 64
    amplitude_multiplier_type: int = 0
    base_par1: int = 80
    base_type: int = 0
    frequency_multiplier: int = 0
    modulator_frequency: int = 30
    modulator_par1: int = 0
    one_half: int = 0
    width: int = 127
    autoscale: bool = True


@dataclass
class SampleQuality(Serializable):
    basenote: int
    octaves: int
    samples_per_octave: int
    samplesize: int


@dataclass
class PadSynthParameters(Serializable):
    amplitude_parameters: AmplitudeParameters
    filter_parameters: FilterParameters
    frequency_parameters: FrequencyParameters
    oscil: Oscil
    resonance: Resonance
    harmonic_position: HarmonicPosition
    harmonic_profile: HarmonicProfile
    sample_quality: SampleQuality
    bandwidth: int
    bandwidth_scale: int
    mode: int
    stereo: bool

    def __post_init__(self) -> None:
        if self.frequency_parameters:
            if self.frequency_parameters.bend_adjust is None:
                self.frequency_parameters.bend_adjust = 88
            if self.frequency_parameters.offset_hz is None:
                self.frequency_parameters.offset_hz = 64


@dataclass
class SubSynthParameters(Serializable):
    amplitude_parameters: AmplitudeParameters
    filter_parameters: FilterParameters
    frequency_parameters: FrequencyParameters
    harmonics: Harmonics

    harmonic_mag_type: int
    num_stages: int
    start: int

    def __post_init__(self) -> None:
        if self.amplitude_parameters:
            if isinstance(self.amplitude_parameters.volume, int):
                self.amplitude_parameters.volume = -60 * (
                    1 - self.amplitude_parameters.volume / 96
                )
            if self.amplitude_parameters.stereo is None:
                self.amplitude_parameters.stereo = True


@dataclass
class InstrumentKitItem(Serializable):
    id: int  # noqa: A003
    enabled: bool

    name: Optional[str] = None
    muted: Optional[bool] = None
    min_key: Optional[int] = None
    max_key: Optional[int] = None
    send_to_instrument_effect: Optional[int] = None

    add_enabled: Optional[bool] = None
    add_synth_parameters: Optional[AddSynthParameters] = None

    sub_enabled: Optional[bool] = None
    sub_synth_parameters: Optional[SubSynthParameters] = None
    pad_enabled: Optional[bool] = None
    pad_synth_parameters: Optional[PadSynthParameters] = None


@dataclass
class InstrumentKit(Serializable):
    kit_mode: int
    drum_mode: bool

    instrument_kit_item: Tuple[InstrumentKitItem, ...]


@dataclass
class InstrumentEffects(Serializable):
    instrument_effect: Tuple[InstrumentEffect, ...]


@dataclass
class Instrument(Serializable):
    info: Info
    instrument_kit: InstrumentKit
    instrument_effects: InstrumentEffects


def _from_xml_node(
    cls: Type[SerializableType],
    node: ET.Element,
    *,
    id: Optional[int] = None,  # noqa: A002 pylint: disable=W0622
    version: Optional[Tuple[int, int, int]] = None,
) -> SerializableType:
    components = {}
    for f in fields(cls):
        children = node.findall(
            f.name.upper() if f.name not in LOWER_CASE_FIELDS else f.name
        )
        if is_dataclass(f.type) and children:
            components[f.name] = _from_xml_node(f.type, children[0], version=version)
        elif (f.type == Optional[f.type]) and children:
            # Handle Optional[T]
            # Check uses Optional[T] == Optional[Optional[T]]
            components[f.name] = _from_xml_node(
                f.type.__args__[0], children[0], version=version
            )
        elif get_origin(f.type) == tuple:
            components[f.name] = tuple(
                _from_xml_node(
                    f.type.__args__[0], x, id=int(x.attrib["id"]), version=version
                )
                for x in children
            )
        else:
            for x in node:
                if "name" in x.attrib and x.attrib["name"] == f.name:
                    components[f.name] = get_value(x)
    if version is not None and version < (3, 0, 4) and cls == LFO:
        components["freq"] = (2 ** (10 * components["freq"]) - 1) / 12
    if id is not None:
        components["id"] = id
    return cls(**components)


def get_value(node: ET.Element) -> Union[Optional[str], float, int]:
    """Get value from leaf node in Zyn xml."""
    if node.tag == "string":
        return node.text

    value = node.attrib["value"]
    if node.tag == "par_bool":
        return value == "yes"
    if node.tag == "par_real":
        # TODO use exact value field in xml
        return float(value)
    if node.tag == "par":
        return int(value)

    raise ValueError(node)


@dataclass
class Controller(Serializable):
    pitchwheel_bendrange: int = 200
    pitchwheel_bendrange_down: int = 0
    pitchwheel_split: bool = False
    expression_receive: bool = True
    panning_depth: int = 64
    filter_cutoff_depth: int = 64
    filter_q_depth: int = 64
    bandwidth_depth: int = 64
    mod_wheel_depth: int = 80
    mod_wheel_exponential: bool = False
    fm_amp_receive: bool = True
    volume_receive: bool = True
    sustain_receive: bool = True
    portamento_receive: bool = True
    portamento_time: int = 64
    portamento_pitchthresh: int = 3
    portamento_pitchthreshtype: int = 1
    portamento_portamento: int = 0
    portamento_auto: bool = True
    portamento_updowntimestretch: int = 64
    portamento_proportional: int = 0
    portamento_proprate: int = 80
    portamento_propdepth: int = 90
    resonance_center_depth: int = 64
    resonance_bandwidth_depth: int = 64


PartType = TypeVar("PartType", bound="Part")


@dataclass
class Part(Serializable):
    id: int  # noqa: A003
    enabled: bool

    instrument: Optional[Instrument] = None

    volume: Optional[float] = 0.0
    panning: Optional[int] = 64
    min_key: Optional[int] = 0
    max_key: Optional[int] = 127
    key_shift: Optional[int] = 64
    rcv_chn: Optional[int] = 0
    velocity_sensing: Optional[int] = 64
    velocity_offset: Optional[int] = 64
    note_on: Optional[bool] = True
    poly_mode: Optional[bool] = True
    legato_mode: Optional[int] = 0
    key_limit: Optional[int] = 15
    voice_limit: Optional[int] = 0

    controller: Optional[Controller] = field(default_factory=Controller)

    @classmethod
    def from_config(cls: Type[PartType], part: PartConfig) -> PartType:
        """Build Zyn part from jird config."""
        assert part.instrument is not None
        assert isinstance(part.panning, int)
        return cls(
            id=0,
            enabled=True,
            instrument=Instrument.from_xml(part.instrument, tag="INSTRUMENT"),
            volume=part.volume,
            panning=part.panning,
        )


DISABLED_PART = Part(id=0, enabled=False)


@dataclass
class Volume(Serializable):
    id: int  # noqa: A003
    vol: int = 0


@dataclass
class SendTo(Serializable):
    id: int  # noqa: A003
    send_vol: int = 0


@dataclass
class SystemEffect(Serializable):
    id: int  # noqa: A003
    effect: Effect = field(default_factory=Effect)
    volume: Tuple[Volume, ...] = tuple(Volume(id=i) for i in range(16))
    sendto: Tuple[SendTo, ...] = tuple(SendTo(id=i) for i in range(3))


@dataclass
class InsertionEffect(Serializable):
    id: int  # noqa: A003
    effect: Effect = field(default_factory=Effect)

    part: int = -1


@dataclass
class Master(Serializable):
    part: Tuple[Part, ...]

    volume: float = -20 / 3
    key_shift: int = 64
    nrpn_receive: bool = True

    microtonal: Microtonal = field(default_factory=Microtonal)
    automation: None = None
    system_effect: Tuple[SystemEffect, ...] = tuple(
        SystemEffect(id=i) for i in range(4)
    )
    insertion_effect: Tuple[InsertionEffect, ...] = tuple(
        InsertionEffect(id=i) for i in range(8)
    )


@dataclass
class Information(Serializable):
    pass


@dataclass
class ZynConfig(Serializable):
    """Top level Zyn config."""

    master: Master
    information: Information = field(default_factory=Information)
    base_parameters: BaseParameters = field(default_factory=BaseParameters)

    def to_xml(
        self,
        filename: Union[str, Path],
        tag: Optional[str] = None,  # noqa: ARG002
        attrib: Optional[Dict[str, str]] = None,  # noqa: ARG002
    ) -> None:
        """Write Zyn master config to xml."""
        super().to_xml(
            filename,
            tag="ZynAddSubFX-data",
            attrib={
                "version-major": "3",
                "version-minor": "0",
                "version-revision": "7",
                "ZynAddSubFX-author": "Nasca Octavian Paul",
            },
        )


def float_to_hex(f: float) -> str:
    """Convert float to hex showing its binary representation."""
    return f'0x{struct.unpack("<I", struct.pack("<f", f))[0]:08X}'


def _add_to_xml(d: Serializable, parent: ET.Element) -> None:  # noqa: max-complexity=11
    for f in fields(d):
        tag = f.name.upper() if f.name not in LOWER_CASE_FIELDS else f.name
        x = getattr(d, f.name)
        if is_dataclass(x):
            child = ET.SubElement(parent, tag)
            _add_to_xml(x, child)
        elif isinstance(x, tuple):
            for y in x:
                child = ET.SubElement(parent, tag, id=str(y.id))
                _add_to_xml(y, child)
        elif isinstance(x, bool):
            ET.SubElement(parent, "par_bool", name=f.name, value="yes" if x else "no")
        elif isinstance(x, int):
            if f.name != "id":
                ET.SubElement(parent, "par", name=f.name, value=str(x))
        elif isinstance(x, float):
            ET.SubElement(
                parent,
                "par_real",
                name=f.name,
                value=str(x).rstrip("0").rstrip("."),
                exact_value=float_to_hex(x),
            )
        elif isinstance(x, str):
            child = ET.SubElement(parent, "string", name=f.name)
            child.text = x
        elif x is None:
            continue
        else:
            raise ValueError(x)


def play_with_zyn(
    config: Config,
    part_channels: List[List[int]],
    scala_data: Optional[ScalaData],
    filepath: Path,
) -> None:
    """
    Play music with Zyn.

    Generate a Zyn master config from Zyn instruments and any scala tuning
    data. Run Zyn with this config. Send midi to Zyn with aplaymidi. Kill
    Zyn when done.

    Parameters
    ----------
    config : Config
        Config controlling playback.
    part_channels : list of list of int
        Midi channels used for each part.
    scala_data : ScalaData, optional
        Scala tuning files and frequency map.
    filepath : Path
        Path to midi file.
    """
    if config.tuning_method == TuningMethod.SCALA:
        assert scala_data is not None
        microtonal = build_microtonal_from_scala(
            scala_data.scale, scala_data.keyboard_map
        )
    elif config.tuning_method == TuningMethod.PITCH_BEND:
        microtonal = Microtonal()
    else:
        raise ValueError(config.tuning_method)

    assert config.parts is not None
    zyn_parts = [Part.from_config(x) for x in config.parts]
    if len(zyn_parts) < len(part_channels):
        zyn_parts += (len(part_channels) - len(zyn_parts)) * [zyn_parts[-1]]
    assert len(zyn_parts) >= len(part_channels)
    zyn_parts_for_channels = tuple(
        chain.from_iterable(
            [replace(zyn_part, rcv_chn=x) for x in channels]
            for zyn_part, channels in zip(zyn_parts, part_channels)
        )
    )
    zyn_parts_for_channels = tuple(
        replace(x, id=i) for i, x in enumerate(zyn_parts_for_channels)
    )

    max_parts = 16
    unused = max_parts - len(zyn_parts_for_channels)
    if unused > 0:
        zyn_parts_for_channels += unused * (DISABLED_PART,)

    assert len(zyn_parts_for_channels) == max_parts

    zyn_config = ZynConfig(
        master=Master(
            part=zyn_parts_for_channels,
            microtonal=microtonal,
        )
    )
    zyn_config_path = filepath.with_suffix(".xmz")
    zyn_config.to_xml(zyn_config_path)

    # Start Zyn
    p = run_async(
        [
            "zynaddsubfx",
            "-U",
            "-I",
            "alsa",
            "-O",
            "alsa",
            "-l",
            str(zyn_config_path),
            "-r",
            str(config.sample_rate),
        ],
        verbose=config.verbose,
    )

    # Wait for Zyn to be ready to receive midi
    n = 0
    while n < 50 and str(p.pid) not in subprocess.check_output(
        ["aconnect", "-o"],
        encoding="utf8",
    ):
        sleep(0.1)
        n += 1

    # Send midi with aplaymidi
    run(["aplaymidi", "-p", "ZynAddSubFX", filepath], verbose=config.verbose)

    # Kill Zyn once music has finished
    logger.info("Killing %d", p.pid)
    p.kill()
