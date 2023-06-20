"""Tests for jird.surge."""

import os
from pathlib import Path

import pytest

from jird.config import DEFAULT_SURGE_PATCH, Config
from jird.core import all_frequencies, parse
from jird.surge import play_with_surge

try:
    import surgepy  # noqa: F401
except ModuleNotFoundError:
    pytestmark = pytest.mark.skip


@pytest.mark.parametrize(
    "music_text",
    [
        "<1 7/6 4/3 9/5 9/4>:8",
        "0:1",
        "",
        "1:1; 2:2",
        "0:1; 2:2",
        "1:1 0:1",
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        Config.from_dict(
            {
                "f": 440,
                "t": 1,
                "tuning_method": "pitch_bend",
                "synth": "surge_xt",
                "volume": 0.0,
                "parts": [
                    {
                        "instrument": DEFAULT_SURGE_PATCH,
                        "volume": 0.0,
                        "panning": 0,
                    }
                ],
            }
        ),
        Config.from_dict(
            {
                "f": 440,
                "t": 1,
                "tuning_method": "scala",
                "synth": "surge_xt",
                "volume": 0.0,
                "parts": [
                    {
                        "instrument": DEFAULT_SURGE_PATCH,
                        "volume": 0.0,
                        "panning": 0,
                    }
                ],
            }
        ),
    ],
)
def test_play_with_surge(music_text, config, tmp_path, monkeypatch):
    orig_dir = Path.cwd()
    try:
        os.chdir(tmp_path)
        monkeypatch.setattr(
            "subprocess.run", lambda *args, **kwargs: print(args, kwargs)
        )
        music = parse(music_text)
        output_path = tmp_path / "tasty_chord"
        play_with_surge(music, config, output_path)
        if all_frequencies(music):
            assert output_path.with_suffix(".wav").exists()
    finally:
        os.chdir(orig_dir)
