"""Testing code to use for all jird tests."""
import os

if os.environ.get("TYPEGUARD"):
    # Use typeguard to check types at runtime
    #   Auto-generated standalone parser throws some runtime type errors so
    #   import this before installing the typeguard import hook.
    from typeguard import install_import_hook

    from jird.parser import Lark_StandAlone, Token, Transformer  # noqa: F401

    # Generic subprocess.Popen type not accepted
    from jird.process import run_async  # noqa: F401

    install_import_hook("jird")

import pytest

import jird.midi


@pytest.fixture(autouse=True)
def no_play(monkeypatch):
    """Mock play_music to avoid playing sound during tests."""

    def mock_play(music, **kwargs):  # noqa: ARG001
        print("mock_play")

    monkeypatch.setattr(jird.midi, "play_music", mock_play)


@pytest.fixture(
    params=[
        [""],
        ["1:1"],
        ["0:1"],
        ["1/4:1"],
        ["1:1/32"],
        ["1:1/3"],
        ["1:2/7"],
        ["1:1 5/4:1"],
        ["<1 5/4>:1"],
        ["<1 5/4>:1 9/8*<1 7/6>:3"],
        ["1:1", "<1 5/4>:1"],
        ["1:1;", "<1 5/4>:1"],
        10 * ["5/4:1;"],
    ]
)
def music_file(tmp_path, request):
    """Text file containing music written with ratios."""
    music_file_path = tmp_path / "music.txt"
    music_text = "\n".join(request.param) + "\n"
    music_file_path.write_text(music_text)
    return music_file_path
