"""Property based tests using hypothesis."""
import operator
from fractions import Fraction

import pytest

try:
    import hypothesis.strategies as st
    from hypothesis import HealthCheck, given, reject, settings
except ModuleNotFoundError:
    pytest.skip(reason="hypothesis not installed", allow_module_level=True)

from jird.core import (
    Note,
    RatioProduct,
    all_frequencies,
    apply_to_notes,
    evaluate,
    frequencies_set,
    height,
    interval_table,
    lowest,
    parse,
    print_music,
    temper,
    temper_note,
    total_duration,
)
from jird.lilypond import (
    _factorize,
    lilypond_chord,
    lilypond_duration,
    lilypond_note,
    lilypond_pitch,
)
from jird.midi import chord_to_midi

pytestmark = pytest.mark.slow

MAX_EXAMPLES = 1000
PROFILE_NAME = "jird"
settings.register_profile(PROFILE_NAME, max_examples=MAX_EXAMPLES)
settings.load_profile(PROFILE_NAME)

ratio_strings = st.builds(
    lambda x, y: f"{x}/{y}", st.integers(min_value=0), st.integers(min_value=1)
)

note_strings = st.builds(lambda x, y: f"{x}:{y}", ratio_strings, ratio_strings)

chord_strings = st.builds(
    lambda x, y: f"<{' '.join(x)}>:{y}", st.lists(ratio_strings), ratio_strings
)

part_strings = st.lists(st.one_of(note_strings, chord_strings)).map(" ".join)

music_strings = st.lists(part_strings).map(";".join)

musics = music_strings.map(parse)

notes = note_strings.map(lambda x: parse(x)[0][0])

chords = chord_strings.map(lambda x: parse(x)[0][0])

edos = st.integers(min_value=1, max_value=10000)

frequencies = st.floats(min_value=1e-6, max_value=1e12)


@given(music_strings)
def test_fuzz_parse(music_text):
    parse(music_text)


@given(
    musics,
    st.sampled_from(
        [
            lambda x: x,
            lambda x: x.cents,
            lambda x: Note(
                frequency=x.frequency, duration=evaluate(Fraction(2) * x.duration)
            ),
        ]
    ),
)
def test_fuzz_apply_to_notes(music, f):
    apply_to_notes(music, f)


@given(notes, edos)
def test_fuzz_temper_note(note, edo):
    temper_note(note, edo=edo)


@given(notes, edos)
def test_temper_note_idempotent(note, edo):
    note_1 = temper_note(note, edo=edo)
    note_2 = temper_note(note_1, edo=edo)
    assert note_1 == note_2


@given(musics, edos)
def test_fuzz_temper(music, edo):
    temper(music, edo=edo)


@settings(deadline=None)
@given(musics, edos)
def test_temper_idempotent(music, edo):
    music_1 = temper(music, edo=edo)
    music_2 = temper(music_1, edo=edo)
    assert music_1 == music_2


@given(musics)
def test_fuzz_total_duration(music):
    try:
        total_duration(music)
    except ValueError as e:
        assert "Simultaneous durations do not match" in str(e)


@given(musics)
def test_fuzz_frequencies_set(music):
    frequencies_set(music)


@given(musics)
def test_fuzz_all_frequencies(music):
    all_frequencies(music)


@given(musics)
def test_fuzz_height(music):
    height(music)


@given(musics)
def test_fuzz_lowest(music):
    lowest(music)


@given(musics, st.integers(min_value=0, max_value=30))
def test_fuzz_print_music(music, level):
    print_music(music, level)


@given(st.lists(st.fractions().filter(lambda x: x > 0)))
def test_fuzz_interval_table(frequencies):
    interval_table(frequencies)


ops = st.sampled_from(
    [
        operator.mul,
        operator.le,
        operator.le,
        operator.ge,
        operator.gt,
        operator.eq,
    ],
)


@given(
    st.fractions(),
    st.fractions(),
    ops,
)
def test_ratio_product_ops(x, y, op):
    direct = op(x, y)
    via_ratio_product = evaluate(op(RatioProduct(x), RatioProduct(y)))
    assert direct == via_ratio_product


@given(
    st.fractions(),
    st.fractions(),
    ops,
)
def test_ratio_product_ops_2(x, y, op):
    direct = op(x, y)
    via_ratio_product = evaluate(op(x, RatioProduct(y)))
    assert direct == via_ratio_product


@given(
    st.fractions(),
    st.fractions(),
    ops,
)
def test_ratio_product_ops_3(x, y, op):
    direct = op(x, y)
    via_ratio_product = evaluate(op(RatioProduct(x), y))
    assert direct == via_ratio_product


@given(
    notes,
    frequencies,
    edos,
)
def test_fuzz_lilypond_pitch(note, f0, base_edo):
    lilypond_pitch(note, f0, base_edo)


@given(st.integers(min_value=1))
def test_factorize(n):
    a, b = _factorize(n)
    assert a * b == n


# Large durations given very large lilypond strings which kill pytest by
# using too much memory.
MAX_DURATION = 10000


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(notes.filter(lambda x: x.duration <= MAX_DURATION))
def test_fuzz_lilypond_duration(note):
    try:
        lilypond_duration(note)
    except AssertionError:
        reject()


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(notes.filter(lambda x: x.duration <= MAX_DURATION), frequencies)
def test_fuzz_lilypond_note(note, f0):
    try:
        lilypond_note(note, f0)
    except AssertionError:
        reject()


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(chords.filter(lambda x: x and (x[0].duration <= MAX_DURATION)), frequencies)
def test_fuzz_lilypond_chord(chord, f0):
    try:
        lilypond_chord(chord, f0)
    except AssertionError:
        reject()


@given(
    notes,
    frequencies,
    st.integers(min_value=1),
)
def test_fuzz_midi_note(note, f0, pitch_bend_range):
    try:
        note.to_midi(f0=f0, pitch_bend_range=pitch_bend_range)
    except AssertionError:
        reject()


@given(
    st.one_of(notes, chords),
    frequencies,
    st.integers(min_value=1),
)
def test_fuzz_chord_to_midi(notes, f0, pitch_bend_range):
    try:
        chord_to_midi(notes, f0=f0, channels=[1], pitch_bend_range=pitch_bend_range)
    except AssertionError:
        reject()


@settings(deadline=None)
@given(music_strings)
def test_parse_determinism(music_str):
    music_1 = parse(music_str)
    music_2 = parse(music_str)
    assert music_1 == music_2
