"""
Convert music into a midi file.

See `this page
<http://www.music.mcgill.ca/~ich/classes/mumt306/StandardMIDIfileformat.html>`_
for information on the standard midi file format.
"""
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from jird.config import Config
from jird.constants import DIVISION, Synth, TuningMethod
from jird.core import Chord, Note, Number, Part, Piece, height
from jird.process import run
from jird.scala import ScalaData, scala_midi_note, write_scala_files_for_midi
from jird.surge import play_with_surge
from jird.zyn import play_with_zyn

logger = logging.getLogger(__name__)

END_OF_TRACK = "00FF2F00"
"""
Midi message for end-of-track
"""

DEFAULT_FILENAME = "jird_out.midi"


def track_header(track_hex: str) -> str:
    """
    Compute midi track header for track in `track_hex`.

    The track header is MTrk followed by the number of bytes in the track.

    Parameters
    ----------
    track_hex : str
        Hex string representing the bytes in the track.

    Returns
    -------
    str
        Hex string of midi track header.
    """
    n_bytes, remainder = divmod(len(track_hex), 2)
    assert remainder == 0
    return "MTrk".encode().hex() + f"{n_bytes:08X}"


def tempo_track(t0: float) -> str:
    """
    Generate tempo track corresponding to time unit `t0`.

    Midi tempo is specified in microseconds per beat. The tempo is set
    assuming time unit `t0` corresponds to one beat.

    Parameters
    ----------
    t0 : float
        Basic time unit used by Jird.

    Returns
    -------
    str
        Hex string of tempo track.
    """
    microseconds_per_beat = round(t0 / 1e-6)
    body = f"00FF5103{microseconds_per_beat:06X}" + END_OF_TRACK
    return track_header(body) + body


def set_program(program: int, channels: List[int]) -> str:
    """
    Generate midi events to set program.

    One program change to `program` is sent for each channel in `channels`.
    The program change sets the instrument which will be used when playing
    the midi file.

    Parameters
    ----------
    program : int
        Midi program to change to. Using `program` 1 changes to the first midi
        program, which means sending program number byte 00.
    channels : list of int
        Midi channels on which to send program changes.

    Returns
    -------
    str
        Hex string containing program change events.
    """
    return "".join(f"00C{i:X}{program - 1:02X}" for i in channels)


def variable_length_quantity(n: int) -> str:
    """
    Compute bytes encoding `n` as a midi variable length quantity.

    A midi variable length quantity is the bits of `n` grouped into sevens.
    Each group is placed in a byte with the top bit set to 0 for the
    last byte and 1 for the others.  For more information see `this webpage
    <http://www.music.mcgill.ca/~ich/classes/mumt306/StandardMIDIfileformat.html#BM1_1>`_
    Variable length quantities are used for example to represent the delta
    times between midi events in midi files.

    Parameters
    ----------
    n : int
        Number to encode.

    Returns
    -------
    str
        Hex string of variable length quantity encoding of `n`.
    """
    bit_string = f"{n:b}"
    n_bytes = math.ceil(len(bit_string) / 7)
    padded_bit_string = f"{n:0{n_bytes*7}b}"
    byte_strings = [
        ("1" if i < (n_bytes - 1) else "0") + padded_bit_string[7 * i : 7 * (i + 1)]
        for i in range(n_bytes)
    ]
    hex_bytes = [f"{int(b, base=2):02X}" for b in byte_strings]
    return "".join(hex_bytes)


def chord_to_midi(
    notes: Union[Note, Chord],
    *,
    f0: float,
    channels: List[int],
    pitch_bend_range: int,
) -> str:
    """
    Generate midi events to play the `notes` in a chord.

    Each note in the chord is sent on a separate midi channel to allow pitch
    bending each note independently.  First the pitch bends needed for each
    note are sent (to get their exact just frequencies).  Then the note on
    events for all notes are sent. Finally the note off events for all notes
    are sent.

    Parameters
    ----------
    notes : tuple of Note or Note
        Notes in the chord to be represented as midi. A single note is treated
        as a one note chord.
    f0 : float
        Basic frequency used to convert note frequency ratios into real frequencies.
    channels : list of int
        Midi channels on which to send `notes`. Each note is sent on its own channel.
    pitch_bend_range : int
        Number of semitones to assume max pitch bend corresponds to.

    Returns
    -------
    str
        Hex string of midi events to play `notes`.
    """
    if not isinstance(notes, tuple):
        notes = (notes,)

    midi_notes = [n.to_midi(f0=f0, pitch_bend_range=pitch_bend_range) for n in notes]

    assert len({note.ticks for note in midi_notes}) == 1
    ticks = midi_notes[0].ticks

    assert len(midi_notes) <= len(channels)

    # Send each note on separate channel to allow pitch bend for each one
    notes_with_channels = list(zip(midi_notes, channels))
    pitch_bends = []
    for note, channel in notes_with_channels:
        assert note.bend is not None
        pitch_bends.append("00" + "E" + f"{channel:X}" + fourteen_bit(note.bend))
    note_ons = [
        f"009{channel:X}{note.pitch:02X}{note.velocity:02X}"
        for note, channel in notes_with_channels
    ]
    note_offs = [
        (variable_length_quantity(ticks) if channel == channels[0] else "00")
        + f"8{channel:X}{note.pitch:02X}00"
        for note, channel in notes_with_channels
    ]
    return "".join(pitch_bends + note_ons + note_offs)


def chord_to_scala_midi(
    notes: Union[Note, Chord],
    frequency_map: Dict[Number, int],
    channel: int,
) -> str:
    """
    Midi events to play a chord for use with scala files.

    Only note-ons and note-offs are needed since no bends are used when
    using scala files. All notes are sent on the same channel.

    Parameters
    ----------
    notes : Note or tuple of Note
        Notes in the chord.
    frequency_map : dict of {Fraction or float : int}
        Map from frequencies to midi note numbers.
    channel : int
        Channel to send notes on.

    Returns
    -------
    str
        Hex for midi to send the chord.
    """
    if not isinstance(notes, tuple):
        notes = (notes,)

    midi_notes = [scala_midi_note(n, frequency_map) for n in notes]

    assert len({note.ticks for note in midi_notes}) == 1
    ticks = midi_notes[0].ticks

    note_ons = [
        f"009{channel:X}{note.pitch:02X}{note.velocity:02X}" for note in midi_notes
    ]
    note_offs = [
        (variable_length_quantity(ticks) if i == 0 else "00")
        + f"8{channel:X}{note.pitch:02X}00"
        for i, note in enumerate(midi_notes)
    ]
    return "".join(note_ons + note_offs)


def fourteen_bit(n: int) -> str:
    """
    Represent `n` as fourteen bits stored in two bytes.

    The highest and lowest seven bits of `n` are stored in separate bytes,
    with the top bit zero in each.  This representation is used for the size
    of the pitch bend for midi pitch wheel change events.

    Parameters
    ----------
    n : int
        Number to represent.

    Returns
    -------
    str
        Hex string of fourteen bit representation of `n`.
    """
    bit_string = f"{n:016b}"
    least = bit_string[-7:]
    most = bit_string[-14:-7]
    new_bit_string = "0" + least + "0" + most
    return f"{int(new_bit_string, base=2):04X}"


def midi_track(
    music: Part,
    *,
    f0: float,
    channels: List[int],
    program: Optional[int],
    pitch_bend_range: int,
) -> str:
    """
    Build midi track for music.

    The midi track is made up of a track header, program changes, then midi
    events to play chord in `music`.

    Parameters
    ----------
    music : Part
        Music to build midi track for.
    f0 : float
        Basic frequency used to convert note frequency ratios into real frequencies.
    channels : list of int
        Midi channels to use to play `music`.
    program : int, optional
        Midi program to use for playback.
    pitch_bend_range : int
        Number of semitones to assume max pitch bend corresponds to.

    Returns
    -------
    str
        Hex for midi track representing `music`.
    """
    program_change = set_program(program, channels) if program is not None else ""
    body = program_change + "".join(
        chord_to_midi(x, f0=f0, channels=channels, pitch_bend_range=pitch_bend_range)
        for x in music
    )
    body = body + END_OF_TRACK
    header = track_header(body)
    return header + body


def part_midi_tracks(
    music: Piece,
    f0: float,
    programs: Optional[List[Optional[int]]],
    pitch_bend_range: int,
) -> Tuple[List[str], List[List[int]]]:
    """
    Build midi tracks for each part in `music`.

    Parameters
    ----------
    music : Piece
        Music for each part.
    f0 : float
        Basic frequency used to convert note frequency ratios into real frequencies.
    programs : list of int, optional
        Midi programs to use for each part.
    pitch_bend_range : int
        Number of semitones to assume max pitch bend corresponds to.

    Returns
    -------
    list of str
        Midi track hex for each part.
    """
    midi_tracks = []

    # Do not use first midi channel (0) in case it is MPE master channel
    # Do not use tenth midi channel (9) since it is used for percussion in General Midi
    all_channels = [i for i in range(16) if i not in {0, 9}]
    lowest_index = 0

    program = None
    part_channels = []
    for n, part in enumerate(music):
        if programs is not None:
            program = programs[n] if n < len(programs) else programs[-1]
        n_channels = height(part)
        assert lowest_index <= (len(all_channels) - 1), "Not enough channels"
        channels = all_channels[lowest_index : lowest_index + n_channels]
        part_channels.append(channels)
        midi_tracks.append(
            midi_track(
                part,
                f0=f0,
                channels=channels,
                program=program,
                pitch_bend_range=pitch_bend_range,
            )
        )
        lowest_index += n_channels

    return midi_tracks, part_channels


def part_scala_midi_tracks(
    music: Piece, frequency_map: Dict[Number, int]
) -> Tuple[List[str], List[List[int]]]:
    """
    Build midi for each track in `music` for use with scala files.

    Each frequency in `music` is mapped to a unique midi note number. This
    allows subsequent retuning with scala scl and kbm files.

    Parameters
    ----------
    music : Piece
        Music containing parts to represent.
    frequency_map : dict of {int : int}
        Mapping from frequency to scala scale degree.

    Returns
    -------
    list of str
        Track hex for each part.
    """
    all_channels = list(range(16))
    part_tracks = [
        "".join(
            chord_to_scala_midi(chord, frequency_map, channel=all_channels[i])
            for chord in part
        )
        + END_OF_TRACK
        for i, part in enumerate(music)
    ]
    part_channels = [[all_channels[i]] for i in range(len(music))]
    return [track_header(x) + x for x in part_tracks], part_channels


def music_to_midi_file(
    music: Piece,
    *,
    config: Config,
    filename: Union[str, Path] = DEFAULT_FILENAME,
) -> Tuple[List[List[int]], Optional[ScalaData]]:
    """
    Write midi file for `music`.

    Parameters
    ----------
    music : Piece
        Music to convert to midi.
    config : Config
        Config controlling playback.
    filename : str or Path
        Name for output midi file.

    Returns
    -------
    tuple of (list of list of int, optional ScalaData)
        First item is the midi channels used for each part in the midi
        file. Second item is the tuning data to be used with the midi file
        (if scala retuning is used).
    """
    scala_data = None
    if config.tuning_method == TuningMethod.SCALA:
        scala_data = write_scala_files_for_midi(
            music, f0=config.f, base_filename=filename
        )
        part_tracks, part_channels = part_scala_midi_tracks(
            music, scala_data.frequency_map
        )
    elif config.tuning_method == TuningMethod.PITCH_BEND:
        programs = None
        if config.parts is not None:
            programs = [part.program for part in config.parts]
        part_tracks, part_channels = part_midi_tracks(
            music, config.f, programs, config.pitch_bend_range
        )
    else:
        raise ValueError(config.tuning_method)

    all_tracks = [tempo_track(config.t), *part_tracks]

    file_header = (
        "MThd".encode().hex()
        + "00000006"
        + "0001"
        + f"{len(all_tracks):04X}"
        + f"{DIVISION:04X}"
    )

    midi_hex_string = file_header + "".join(all_tracks)
    midi_hex_string = midi_hex_string.replace(" ", "")
    midi_bytes = bytes.fromhex(midi_hex_string)

    logger.info("Writing %s", filename)
    with open(filename, "wb") as file:
        file.write(midi_bytes)

    return part_channels, scala_data


def play_music(
    music: Piece,
    *,
    config: Config,
    filename: Union[str, Path] = DEFAULT_FILENAME,
) -> None:
    """
    Play music with chosen synth.

    Parameters
    ----------
    music : Piece
        Music to be played.
    config : Config
        Config controlling playback.
    filename : str or Path
        Filename to use for temporary midi file. Defaults to jird_out.midi.
    """
    # Fluidsynth only works with pitch bend retuning
    if config.synth == Synth.FLUIDSYNTH:
        config.tuning_method = TuningMethod.PITCH_BEND

    part_channels: List[List[int]] = [[]]
    scala_data = None
    if config.synth in {Synth.ZYNADDSUBFX, Synth.FLUIDSYNTH}:
        part_channels, scala_data = music_to_midi_file(
            music,
            config=config,
            filename=filename,
        )
    filepath = Path(filename)

    if config.synth == Synth.ZYNADDSUBFX:
        play_with_zyn(config, part_channels, scala_data, filepath)
    elif config.synth == Synth.FLUIDSYNTH:
        play_with_fluidsynth(config, filepath)
    elif config.synth == Synth.SURGE_XT:
        play_with_surge(music, config, filepath)
    else:
        raise ValueError(config.synth)


def play_with_fluidsynth(
    config: Config,
    filename: Union[str, Path],
) -> None:
    """
    Play midi file using fluidsynth.

    Parameters
    ----------
    config: Config
        Config controlling playback.
    filename : str or Path
        Midi file to play.
    """
    run(
        [
            "fluidsynth",
            "-a",
            "alsa",
            "-ni",
            "-r",
            str(config.sample_rate),
            "-g",
            str(config.volume),
        ]
        + ([str(config.soundfont)] if config.soundfont is not None else [])
        + [str(filename)],
        verbose=config.verbose,
    )
