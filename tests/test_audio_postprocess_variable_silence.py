"""pipeline.audio_postprocess.concat_with_variable_silence() - test THAT voi
ffmpeg that (khong mock subprocess), vi day la logic ghep file quan trong,
loi o day se lam sai hoan toan timing cua Section 7.2/7.3."""
import wave

import pytest

from pipeline.audio_postprocess import (
    concat_with_silence,
    concat_with_variable_silence,
    generate_silence,
    get_ffmpeg,
)


def _make_tone_wav(ffmpeg, duration_s, path, sample_rate=24000):
    import subprocess

    cmd = [
        ffmpeg, "-y", "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate={sample_rate}",
        "-t", str(duration_s), "-c:a", "pcm_s16le", path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return path


def _wav_duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


@pytest.fixture
def ffmpeg():
    return get_ffmpeg()


def test_concat_with_variable_silence_total_duration(tmp_path, ffmpeg):
    wav1 = _make_tone_wav(ffmpeg, 1.0, str(tmp_path / "a.wav"))
    wav2 = _make_tone_wav(ffmpeg, 1.0, str(tmp_path / "b.wav"))
    wav3 = _make_tone_wav(ffmpeg, 1.0, str(tmp_path / "c.wav"))
    out = str(tmp_path / "out.wav")

    concat_with_variable_silence(ffmpeg, [wav1, wav2, wav3], [0.15, 0.4], out)

    dur = _wav_duration(out)
    # 3 x 1.0s tone + 0.15s + 0.4s khoang lang = 3.55s (cho phep sai so nho
    # do lam tron sample o buoc encode).
    assert abs(dur - 3.55) < 0.05


def test_concat_with_variable_silence_wrong_count_raises(tmp_path, ffmpeg):
    wav1 = _make_tone_wav(ffmpeg, 0.2, str(tmp_path / "a.wav"))
    wav2 = _make_tone_wav(ffmpeg, 0.2, str(tmp_path / "b.wav"))
    out = str(tmp_path / "out.wav")

    with pytest.raises(ValueError):
        # 2 file can dung 1 khoang lang, o day truyen nham 2.
        concat_with_variable_silence(ffmpeg, [wav1, wav2], [0.1, 0.2], out)


def test_concat_with_silence_backward_compatible_wrapper(tmp_path, ffmpeg):
    """concat_with_silence() (ham cu) van hoat dong dung nhu truoc - ap dung
    1 khoang lang DEU cho moi cap file, qua wrapper goi
    concat_with_variable_silence()."""
    wav1 = _make_tone_wav(ffmpeg, 0.5, str(tmp_path / "a.wav"))
    wav2 = _make_tone_wav(ffmpeg, 0.5, str(tmp_path / "b.wav"))
    out = str(tmp_path / "out.wav")

    concat_with_silence(ffmpeg, [wav1, wav2], 0.3, out)

    dur = _wav_duration(out)
    assert abs(dur - 1.3) < 0.05


def test_single_file_no_silence_needed(tmp_path, ffmpeg):
    wav1 = _make_tone_wav(ffmpeg, 0.5, str(tmp_path / "a.wav"))
    out = str(tmp_path / "out.wav")

    concat_with_variable_silence(ffmpeg, [wav1], [], out)

    dur = _wav_duration(out)
    assert abs(dur - 0.5) < 0.05
