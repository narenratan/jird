"""Tests for jird.config."""
import pytest

from jird.config import DEFAULT_SURGE_PATCH, DEFAULT_ZYN_PATCH, Config, _to_enum
from jird.constants import Synth


@pytest.mark.parametrize(
    "config_dict",
    [
        {
            "f": 440,
            "t": 1,
            "tuning_method": "pitch_bend",
            "synth": "surge_xt",
            "volume": 0.0,
            "sample_rate": 44100,
            "parts": [
                {
                    "instrument": DEFAULT_SURGE_PATCH,
                    "volume": 0.0,
                    "panning": 0,
                }
            ],
        },
        {
            "f": 440,
            "t": 1,
            "tuning_method": "pitch_bend",
            "synth": "surge_xt",
            "volume": 0.0,
            "sample_rate": 44100,
            "parts": [{}],
        },
        {
            "f": 440,
            "t": 1,
            "tuning_method": "scala",
            "synth": "zynaddsubfx",
            "volume": 0.0,
            "sample_rate": 44100,
            "parts": [
                {
                    "instrument": DEFAULT_ZYN_PATCH,
                    "volume": 0.0,
                    "panning": 64,
                }
            ],
        },
        {
            "f": 440,
            "t": 1,
            "tuning_method": "scala",
            "synth": "zynaddsubfx",
            "volume": 0.0,
            "sample_rate": 44100,
            "parts": [{}],
        },
    ],
)
def test_config_from_dict(config_dict):
    Config.from_dict(config_dict)


def test_to_enum(capfd):
    with pytest.raises(KeyError):
        _to_enum("foo", Synth)
    out, _ = capfd.readouterr()
    assert "Synth 'foo' not recognized" in out
