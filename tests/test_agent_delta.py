"""Agent Delta (voxdirector.agents.delta_qa) - test bang mock faster-whisper
+ jiwer, KHONG can tai model that."""
import os
from unittest.mock import MagicMock, patch

from voxdirector.agents.delta_qa import (
    summarize_qa_report,
    verify_audio_quality,
    verify_chapter_quality,
)
from voxdirector.config import WER_PASS_THRESHOLD


def _mock_transcribe(text, wer_override=None):
    """Tra ve (segments, info) gia lap faster-whisper - 1 segment duy nhat
    chua toan bo text de don gian hoa."""
    seg = MagicMock()
    seg.text = text
    return [seg], MagicMock()


def test_verify_audio_quality_perfect_match():
    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_transcribe("xin chào các bạn")
    with patch("voxdirector.agents.delta_qa._get_model", return_value=mock_model):
        result = verify_audio_quality("dummy.wav", "xin chào các bạn")

    assert result["word_error_rate"] == 0.0
    assert result["passed"] is True
    assert result["transcript"] == "xin chào các bạn"


def test_verify_audio_quality_high_wer_fails():
    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_transcribe("hoàn toàn khác biệt")
    with patch("voxdirector.agents.delta_qa._get_model", return_value=mock_model):
        result = verify_audio_quality("dummy.wav", "xin chào các bạn thân mến")

    assert result["word_error_rate"] > WER_PASS_THRESHOLD
    assert result["passed"] is False


def test_verify_chapter_quality_uses_merged_wav_when_no_final(tmp_path):
    chapter_dir = str(tmp_path)
    prefix = "ch01"
    (tmp_path / f"{prefix}_merged.wav").write_bytes(b"fake wav data")
    (tmp_path / f"{prefix}_p01.wav").write_bytes(b"fake wav data")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_transcribe("một câu ví dụ")
    with patch("voxdirector.agents.delta_qa._get_model", return_value=mock_model):
        result = verify_chapter_quality(chapter_dir, prefix, ["một câu ví dụ"])

    assert result["word_error_rate"] == 0.0
    assert result["passed"] is True
    assert result["flagged_segments"] == []


def test_verify_chapter_quality_prefers_final_over_merged(tmp_path):
    """_final.wav (co BGM) uu tien hon _merged.wav khi ca 2 cung ton tai."""
    chapter_dir = str(tmp_path)
    prefix = "ch01"
    (tmp_path / f"{prefix}_merged.wav").write_bytes(b"fake")
    (tmp_path / f"{prefix}_final.wav").write_bytes(b"fake")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = _mock_transcribe("test")
    with patch("voxdirector.agents.delta_qa._get_model", return_value=mock_model):
        verify_chapter_quality(chapter_dir, prefix, ["test"])

    called_path = mock_model.transcribe.call_args[0][0]
    assert called_path.endswith(f"{prefix}_final.wav")


def test_verify_chapter_quality_raises_when_no_audio(tmp_path):
    import pytest

    with pytest.raises(RuntimeError):
        verify_chapter_quality(str(tmp_path), "ch01", ["test"])


def test_verify_chapter_quality_flags_deviant_segment(tmp_path):
    chapter_dir = str(tmp_path)
    prefix = "ch01"
    (tmp_path / f"{prefix}_merged.wav").write_bytes(b"fake")
    (tmp_path / f"{prefix}_p01.wav").write_bytes(b"fake")
    (tmp_path / f"{prefix}_p02.wav").write_bytes(b"fake")

    mock_model = MagicMock()
    # Chuong tong the (_merged.wav) + p01: khop CHINH XAC (WER=0). Rieng p02:
    # transcript sai hoan toan (WER cao) -> phai bi flag, p01 thi khong.
    full_text = "câu một hai ba câu hai bốn năm sáu"

    def _side_effect(path, language):
        if path.endswith("_p02.wav"):
            return _mock_transcribe("hoàn toàn sai lệch không liên quan")
        if path.endswith("_p01.wav"):
            return _mock_transcribe("câu một hai ba")
        return _mock_transcribe(full_text)  # _merged.wav (tong the)

    mock_model.transcribe.side_effect = _side_effect
    with patch("voxdirector.agents.delta_qa._get_model", return_value=mock_model):
        result = verify_chapter_quality(
            chapter_dir, prefix, ["câu một hai ba", "câu hai bốn năm sáu"],
        )

    assert len(result["flagged_segments"]) == 1
    assert result["flagged_segments"][0]["segment_index"] == 1


def test_summarize_qa_report_without_api_key_uses_code_fallback():
    """summarize_qa_report() doc GEMINI_API_KEY qua import CUC BO trong than
    ham (from voxdirector.config import GEMINI_API_KEY) - phai patch dung
    o module goc voxdirector.config, khong phai delta_qa (ten do khong ton
    tai o module-level trong delta_qa.py)."""
    qa_report = {"word_error_rate": 0.05, "passed": True, "flagged_segments": []}
    with patch("voxdirector.config.GEMINI_API_KEY", None):
        summary = summarize_qa_report(qa_report)
    assert "5" in summary or "5.00%" in summary or "5%" in summary
    assert "ĐẠT" in summary


def test_summarize_qa_report_with_api_key_calls_llm():
    qa_report = {"word_error_rate": 0.05, "passed": True, "flagged_segments": []}
    mock_summary = MagicMock()
    mock_summary.summary = "Tóm tắt giả lập"
    with patch("voxdirector.config.GEMINI_API_KEY", "fake-key-for-test"), \
         patch("voxdirector.llm_client.call_structured", return_value=mock_summary):
        summary = summarize_qa_report(qa_report)
    assert summary == "Tóm tắt giả lập"
