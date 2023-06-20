"""Test that just frequency ratios are accurately produced in audio."""
import subprocess
import tempfile
from fractions import Fraction
from functools import partial
from pathlib import Path

import pytest

try:
    import numpy as np
    from hypothesis import given, reject, settings
    from hypothesis import strategies as st
    from scipy.fft import fft
    from scipy.io import wavfile
    from scipy.signal import find_peaks
except ModuleNotFoundError:
    pytest.skip(reason="scipy and/or hypothesis not installed", allow_module_level=True)

from jird.config import Config
from jird.core import Music, parse
from jird.midi import music_to_midi_file
from jird.surge import render_with_surge

pytestmark = pytest.mark.slow

SOUNDFONT = Path.home() / "soundfonts/airfont_380_final.sf2"

if not SOUNDFONT.exists():
    pytest.skip(reason=f"Soundfont {SOUNDFONT} does not exist", allow_module_level=True)


def spectrum_peaks(data: np.ndarray) -> np.ndarray:
    """
    Find peaks in Fourier spectrum.

    Peak frequencies are normalized to lowest-frequency peak.

    Parameters
    ----------
    data : ndarray
        One-dimensional array of sound data.

    Returns
    -------
    ndarray
        Peaks in frequency spectrum. Sorted from low to high frequency. Normalized
        to lowest-frequency peak.
    """
    spectrum = fft(data)
    spectrum = spectrum[: len(spectrum) // 2]
    threshold = 0.1 * np.max(np.abs(spectrum))
    peaks, properties = find_peaks(np.abs(spectrum), height=threshold, width=1)
    if peaks.size <= 1:
        return peaks
    largest_peaks = peaks[np.argsort(properties["peak_heights"])]
    sorted_peaks = np.sort(largest_peaks[-2:])
    return sorted_peaks / sorted_peaks[0]


RATIOS = [
    Fraction(25, 24),
    Fraction(16, 15),
    Fraction(9, 8),
    Fraction(7, 6),
    Fraction(6, 5),
    Fraction(5, 4),
    Fraction(9, 7),
    Fraction(4, 3),
    Fraction(7, 5),
    Fraction(10, 7),
    Fraction(3, 2),
    Fraction(14, 9),
    Fraction(8, 5),
    Fraction(5, 3),
    Fraction(12, 7),
    Fraction(16, 9),
    Fraction(15, 8),
    Fraction(48, 25),
    Fraction(2, 1),
]

RATIO_TRIPLETS = [
    (transpose, lower, upper)
    for transpose in RATIOS
    for lower in RATIOS
    for upper in RATIOS
    if lower < upper
]

SURGE_CONFIG_DICT = {
    "f": 440,
    "t": 1,
    "tuning_method": "pitch_bend",
    "synth": "surge_xt",
    "volume": 0.0,
    "parts": [
        {
            "instrument": "~/repos/surge/resources/data/patches_factory/Templates/Init Sine.fxp",
            "volume": 0.0,
            "panning": 0,
        }
    ],
}

SURGE_BEND_CONFIG = Config.from_dict(SURGE_CONFIG_DICT)

SURGE_SCALA_CONFIG = Config.from_dict(dict(SURGE_CONFIG_DICT, tuning_method="scala"))

FLUIDSYNTH_CONFIG = Config.from_dict(
    dict(
        SURGE_CONFIG_DICT,
        synth="fluidsynth",
        soundfont=SOUNDFONT,
        parts=[{"program": 21, "volume": 0, "panning": 0}],
    )
)
"""
Tests use midi program number 21 (reed organ) because with the airfont
380 soundfont this (experimentally) gives accurate / easy to detect
peaks in the spectrum.
"""


def render_with_fluidsynth(music, config):
    midi_file = Path(tempfile.gettempdir()) / "frequency_test.midi"
    wav_file = midi_file.with_suffix(".wav")
    try:
        music_to_midi_file(
            music,
            config=config,
            filename=midi_file,
        )
        subprocess.run(
            ["fluidsynth", "-ni", "-F", wav_file, config.soundfont, midi_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        _, data = wavfile.read(wav_file)
    finally:
        midi_file.unlink(missing_ok=True)
        wav_file.unlink(missing_ok=True)
    return data


RENDER_FUNCTIONS = [
    partial(render_with_surge, config=SURGE_BEND_CONFIG),
    partial(render_with_surge, config=SURGE_SCALA_CONFIG),
    partial(render_with_fluidsynth, config=FLUIDSYNTH_CONFIG),
]


def check_frequency(
    render_function,
    music: Music,
    expected_ratio: Fraction,
) -> float:
    """
    Test that just frequency ratio is accurately produced.

    Use jird to write a midi file for the just interval. Then call fluidsynth
    to play this midi file into a wav file. Then find frequency spectrum of
    the sound in the wav file and check that the two lowest frequency peaks
    correspond to the just interval.
    """
    data = render_function(music)
    data = data.sum(axis=1)
    peaks = spectrum_peaks(data)
    min_peaks = 2
    if len(peaks) < min_peaks:
        return float("nan")
    cent_diff = 1200 * np.log2(peaks[1] / expected_ratio)

    print()
    print(float(expected_ratio))
    print(peaks)
    print(cent_diff)
    return cent_diff


MAX_CENT_DIFF = 1.0


@pytest.mark.parametrize(
    "transpose, lower, upper",
    RATIO_TRIPLETS,
    ids=str,
)
@pytest.mark.parametrize("render_function", RENDER_FUNCTIONS)
def test_harmonic_interval(
    render_function, transpose: Fraction, lower: Fraction, upper: Fraction
) -> None:
    """Test frequency representation of interval with notes played simultaneously."""
    music = parse(f"{transpose}*<{lower} {upper}>:32")
    expected_ratio = upper / lower
    cent_diff = check_frequency(
        render_function,
        music,
        expected_ratio,
    )
    assert abs(cent_diff) < MAX_CENT_DIFF


@pytest.mark.parametrize(
    "transpose, lower, upper",
    RATIO_TRIPLETS,
    ids=str,
)
@pytest.mark.parametrize("render_function", RENDER_FUNCTIONS)
def test_melodic_interval(
    render_function, transpose: Fraction, lower: Fraction, upper: Fraction
) -> None:
    """Test frequency representation of interval with notes played sequentially."""
    music = parse(f"{transpose}*({lower}:16 0:16 {upper}:16)")
    expected_ratio = upper / lower
    cent_diff = check_frequency(
        render_function,
        music,
        expected_ratio,
    )
    assert abs(cent_diff) < MAX_CENT_DIFF


@settings(deadline=None)
@pytest.mark.parametrize("render_function", RENDER_FUNCTIONS)
@given(
    st.fractions(min_value=Fraction(81, 80), max_value=2),
)
def test_harmonic_interval_property(render_function, ratio):
    print(ratio)
    music = parse(f"<1 {ratio}>:32")
    cent_diff = check_frequency(
        render_function,
        music,
        ratio,
    )
    assert abs(cent_diff) < MAX_CENT_DIFF


@settings(deadline=None)
@pytest.mark.parametrize("render_function", RENDER_FUNCTIONS)
@given(
    st.fractions(min_value=Fraction(81, 80), max_value=2),
)
def test_melodic_interval_property(render_function, ratio):
    print(ratio)
    music = parse(f"1:16 {ratio}:16")
    cent_diff = check_frequency(
        render_function,
        music,
        ratio,
    )
    if np.isnan(cent_diff):
        reject()
    assert abs(cent_diff) < MAX_CENT_DIFF
