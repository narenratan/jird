"""
Code to interact with the `Surge XT synth <https://github.com/surge-synthesizer/surge.>`_.

Uses surgepy, the Surge XT Python API. This can be installed by cloning
the surge repo and pip installing, e.g.

    $ git clone https://github.com/surge-synthesizer/surge.git
    $ python3 -m pip install surge/src/surge-python

There is an example surgepy Jupyter notebook at

    https://github.com/surge-synthesizer/surge/blob/main/scripts/ipy/
"""
import logging
import wave
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np
except ModuleNotFoundError:
    logger.debug("Could not import numpy")

try:
    import surgepy
except ModuleNotFoundError:
    logger.debug("Could not import surgepy")

SURGE = None

# pylint: disable=wrong-import-position
from jird.config import Config, PartConfig
from jird.constants import PITCH_BEND_CENTER, REST_FREQUENCY, TuningMethod
from jird.core import Note, Part, Piece, all_frequencies, evaluate, total_duration
from jird.process import run
from jird.scala import scala_midi_note, write_scala_files_for_midi


def setup_surge(sample_rate: int) -> None:
    """
    Set up SurgeSynthesizer instance.

    At most one SurgeSynthesizer is set up in a given Python process.

    Parameters
    ----------
    sample_rate : int
        Sample rate to use in the synth.

    Raises
    ------
    ModuleNotFoundError
        If surgepy could not be imported.
    """
    # Sorry for the global. This was the best way I could think of to create
    # at most one SurgeSynthesizer instance with the sample rate configurable
    # at runtime.
    global SURGE  # noqa: PLW0603 pylint: disable=global-statement
    if SURGE is not None:
        assert (
            SURGE.getSampleRate() == sample_rate
        ), "Surge already created with different sample rate"
        return
    logger.info("Creating Surge with sample rate %d", sample_rate)
    try:
        SURGE = surgepy.createSurge(sample_rate)
    except NameError as e:
        msg = "No module named 'surgepy'"
        raise ModuleNotFoundError(msg) from e


def play_with_surge(music: Piece, config: Config, filepath: Path) -> None:
    """
    Play music with Surge XT.

    Use surgepy to render music to an array. Write array to wav file. Play
    wav file with aplay.

    Parameters
    ----------
    music : Piece
        Music to play.
    config : Config
        Config specifying details of playback.
    filepath : Path
        Path used as base of output wav-file name.
    """
    # Return early if music just contains rests
    if not all_frequencies(music):
        return

    wav_data = render_with_surge(music, config)
    wav_file = filepath.with_suffix(".wav")
    wav_file.unlink(missing_ok=True)
    logger.info("Writing %s", wav_file)
    with wave.open(str(wav_file), "w") as f:
        f.setnchannels(2)  # pylint: disable=E1101
        f.setsampwidth(4)  # pylint: disable=E1101
        f.setframerate(config.sample_rate)  # pylint: disable=E1101
        f.writeframesraw(wav_data.tobytes())  # pylint: disable=E1101
    run(["aplay", wav_file], verbose=config.verbose)


class RenderError(Exception):
    """Exception thrown if rendering fails."""


def render_with_surge(
    music: Piece, config: Config, amplitude: float = 0.8
) -> "np.ndarray[Tuple[int, int], np.dtype[np.int16]]":
    """Render piece to array."""
    arrays = [process_part(x, config, index=i) for (i, x) in enumerate(music)]
    logger.info("Combining parts")
    # Add arrays in longest array
    arrays = sorted(arrays, key=lambda x: x.shape[1], reverse=True)  # type: ignore[no-any-return]
    output = arrays[0]
    for x in arrays[1:]:
        output[:, : x.shape[1]] += x
    output = amplitude * output / np.max(np.abs(output))
    if np.isnan(output).sum():
        raise RenderError(output)
    assert isinstance(output, np.ndarray)
    wav_data: "np.ndarray[Tuple[int, int], np.dtype[np.int16]]" = (
        output.T * (2**31 - 1)
    ).astype("<i4")
    return wav_data


def process_part(
    part: Part, config: Config, index: int = 0
) -> "np.ndarray[Tuple[int, int], np.dtype[np.float64]]":
    """
    Render individual part.

    Uses scala files to retune Surge.

    Parameters
    ----------
    part : Part
        Part to render.
    config : Config
        Config controlling playback.
    index : int
        Number of part within piece.

    Returns
    -------
    2d ndarray of float
        Rendered part.

    Raises
    ------
    RenderError
        If rendering fails despite retries.
    """
    process = {
        TuningMethod.PITCH_BEND: process_part_bend,
        TuningMethod.SCALA: process_part_scala,
    }[config.tuning_method]
    if not all_frequencies(part):
        return np.zeros((2, 0))
    n = 0
    while n < 10:
        try:
            return process(part, config, index)
        except RenderError:
            logger.debug("Retrying n=%s", n)
            n += 1
    raise RenderError


def _configure_surge(
    part_config: PartConfig, scala: bool, base_path: Optional[Path] = None
) -> None:
    logger.info("Loading %s", part_config.instrument)
    assert SURGE is not None
    SURGE.loadPatch(str(part_config.instrument))

    SURGE.tuningApplicationMode = surgepy.TuningApplicationMode.RETUNE_MIDI_ONLY

    if scala:
        assert base_path is not None
        SURGE.loadSCLFile(str(base_path.with_suffix(".scl")))
        SURGE.loadKBMFile(str(base_path.with_suffix(".kbm")))
    else:
        SURGE.mpeEnabled = True

    patch = SURGE.getPatch()
    SURGE.setParamVal(patch["volume"], part_config.volume)
    for scene_index in [0, 1]:
        SURGE.setParamVal(patch["scene"][scene_index]["pan"], part_config.panning)


def process_part_scala(
    part: Part, config: Config, index: int = 0
) -> "np.ndarray[Tuple[int, int], np.dtype[np.float64]]":
    """
    Render individual part.

    Uses scala files to retune Surge.

    Parameters
    ----------
    part : Part
        Part to render.
    config : Config
        Config controlling playback.
    index : int
        Number of part within piece.

    Returns
    -------
    2d ndarray of float
        Rendered part.

    Raises
    ------
    RenderError
        If output buffer contains nans after rendering.
    """
    setup_surge(config.sample_rate)
    assert SURGE is not None
    logger.info("Processing part %d", index)

    base_path = Path(f"jird_{index}")
    scala_data = write_scala_files_for_midi(part, config.f, base_path)

    part_config = config.parts[index] if index < len(config.parts) else config.parts[-1]
    _configure_surge(part_config, scala=True, base_path=base_path)

    block_size = SURGE.getBlockSize()

    n_blocks = int(total_duration(part) * config.t * config.sample_rate / block_size)
    buf: "np.ndarray[Tuple[int, int], np.dtype[np.float64]]" = SURGE.createMultiBlock(
        n_blocks
    )

    logger.info("Rendering")
    pos = 0
    for x in part:
        chord = (x,) if isinstance(x, Note) else x
        blocks = int(
            evaluate(chord[0].duration) * config.t * config.sample_rate / block_size
        )

        if evaluate(chord[0].frequency) == REST_FREQUENCY:
            SURGE.processMultiBlock(buf, pos, blocks)
        else:
            midi_chord = tuple(
                scala_midi_note(n, scala_data.frequency_map) for n in chord
            )
            for note in midi_chord:
                SURGE.playNote(0, note.pitch, note.velocity, 0)
            SURGE.processMultiBlock(buf, pos, blocks)
            for note in midi_chord:
                SURGE.releaseNote(0, note.pitch, 0)
        if np.isnan(buf).sum():
            raise RenderError(buf)

        pos = pos + blocks

    return buf


def process_part_bend(
    part: Part, config: Config, index: int = 0
) -> "np.ndarray[Tuple[int, int], np.dtype[np.float64]]":
    """
    Render individual part.

    Uses pitch bends sent before each note to retune them.

    Parameters
    ----------
    part : Part
        Part to render.
    config : Config
        Config controlling playback.
    index : int
        Number of part within piece.

    Returns
    -------
    2d ndarray of float
        Rendered part.
    """
    setup_surge(config.sample_rate)
    assert SURGE is not None
    logger.info("Processing part %d", index)

    part_config = config.parts[index] if index < len(config.parts) else config.parts[-1]
    _configure_surge(part_config, scala=False)

    block_size = SURGE.getBlockSize()

    n_blocks = int(total_duration(part) * config.t * config.sample_rate / block_size)
    buf: "np.ndarray[Tuple[int, int], np.dtype[np.float64]]" = SURGE.createMultiBlock(
        n_blocks
    )

    pos = 0
    for x in part:
        chord = (x,) if isinstance(x, Note) else x
        blocks = int(
            evaluate(chord[0].duration) * config.t * config.sample_rate / block_size
        )

        if evaluate(chord[0].frequency) == REST_FREQUENCY:
            SURGE.processMultiBlock(buf, pos, blocks)
        else:
            midi_chord = tuple(
                n.to_midi(f0=config.f, pitch_bend_range=48) for n in chord
            )
            # Do not send notes on channel 0, MPE global channel
            for i, note in enumerate(midi_chord):
                assert note.bend is not None
                SURGE.pitchBend(1 + i, note.bend - PITCH_BEND_CENTER)
                SURGE.playNote(1 + i, note.pitch, note.velocity, 0)
            SURGE.processMultiBlock(buf, pos, blocks)
            for i, note in enumerate(midi_chord):
                SURGE.releaseNote(1 + i, note.pitch, 0)

        pos = pos + blocks

    return buf
