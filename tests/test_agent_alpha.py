"""Agent Alpha (voxdirector.agents.alpha_ingestion) — test bằng mock LLM, KHÔNG
gọi Gemini API thật (không cần GEMINI_API_KEY). Kiểm tra phần logic xác định
được bằng code: clamp/sort index, ép needs_review theo CONFIDENCE_THRESHOLD,
fallback khi LLM trả rỗng, cắt text theo index. Việc Gemini thực sự phân đoạn
chương tốt hay không (kể cả trường hợp không có heading "Chương N") cần 1 lần
chạy thật riêng với GEMINI_API_KEY hợp lệ — không thay thế được bằng mock.
"""
from unittest.mock import patch

from voxdirector.agents.alpha_ingestion import (
    AlphaOutput,
    ChapterBoundary,
    segment_chapters,
)
from voxdirector.config import CONFIDENCE_THRESHOLD


def _mock_result(*boundaries):
    return AlphaOutput(chapters=[ChapterBoundary(**b) for b in boundaries])


def test_empty_text_returns_empty_list():
    assert segment_chapters("") == []
    assert segment_chapters("   \n  ") == []


def test_explicit_heading_sample():
    text = "Chương 1\nMột hôm nọ, trời mưa to.\nChương 2\nBầu trời trong xanh."
    mocked = _mock_result(
        {"start_index": 0, "end_index": 30, "confidence_score": 0.95, "needs_review": False},
        {"start_index": 30, "end_index": len(text), "confidence_score": 0.9, "needs_review": False},
    )
    with patch("voxdirector.agents.alpha_ingestion.call_structured", return_value=mocked):
        chapters = segment_chapters(text)
    assert len(chapters) == 2
    assert chapters[0]["text"] == text[0:30].strip()
    assert chapters[1]["text"] == text[30:len(text)].strip()
    assert all(not c["needs_review"] for c in chapters)


def test_no_heading_sample_semantic_boundary():
    """Không có 'Chương N' tường minh — Alpha phải suy đoán ranh giới ngữ
    nghĩa (mô phỏng bằng mock: LLM tự tin thấp hơn cho ranh giới suy đoán)."""
    text = (
        "Trời còn tối đen, gió lạnh thổi qua khe cửa. "
        "Sáng hôm sau, nắng lên rực rỡ, chim hót líu lo khắp vườn."
    )
    split_at = text.index("Sáng hôm sau")
    mocked = _mock_result(
        {"start_index": 0, "end_index": split_at, "confidence_score": 0.6, "needs_review": False},
        {"start_index": split_at, "end_index": len(text), "confidence_score": 0.6, "needs_review": False},
    )
    with patch("voxdirector.agents.alpha_ingestion.call_structured", return_value=mocked):
        chapters = segment_chapters(text)
    assert len(chapters) == 2
    # confidence 0.6 < CONFIDENCE_THRESHOLD (0.75) -> phai bi ep needs_review=True
    # du LLM (mock) tu bao needs_review=False.
    assert all(c["needs_review"] for c in chapters)


def test_low_confidence_forces_needs_review_even_if_llm_says_false():
    text = "Một đoạn văn bản kiểm thử ngắn."
    mocked = _mock_result(
        {"start_index": 0, "end_index": len(text), "confidence_score": CONFIDENCE_THRESHOLD - 0.01,
         "needs_review": False},
    )
    with patch("voxdirector.agents.alpha_ingestion.call_structured", return_value=mocked):
        chapters = segment_chapters(text)
    assert chapters[0]["needs_review"] is True


def test_high_confidence_does_not_force_needs_review():
    text = "Một đoạn văn bản kiểm thử ngắn khác."
    mocked = _mock_result(
        {"start_index": 0, "end_index": len(text), "confidence_score": CONFIDENCE_THRESHOLD + 0.05,
         "needs_review": False},
    )
    with patch("voxdirector.agents.alpha_ingestion.call_structured", return_value=mocked):
        chapters = segment_chapters(text)
    assert chapters[0]["needs_review"] is False


def test_llm_returns_no_chapters_falls_back_to_single_chapter():
    text = "Văn bản không có ranh giới rõ ràng nào cả."
    with patch("voxdirector.agents.alpha_ingestion.call_structured", return_value=_mock_result()):
        chapters = segment_chapters(text)
    assert len(chapters) == 1
    assert chapters[0]["text"] == text
    assert chapters[0]["start_index"] == 0
    assert chapters[0]["end_index"] == len(text)


def test_out_of_range_indices_are_clamped():
    text = "Ngắn."
    mocked = _mock_result(
        {"start_index": -5, "end_index": 9999, "confidence_score": 0.99, "needs_review": False},
    )
    with patch("voxdirector.agents.alpha_ingestion.call_structured", return_value=mocked):
        chapters = segment_chapters(text)
    assert chapters[0]["start_index"] == 0
    assert chapters[0]["end_index"] == len(text)
    assert chapters[0]["text"] == text


def test_chapters_sorted_by_start_index_even_if_llm_returns_out_of_order():
    text = "AAAAABBBBBCCCCC"
    mocked = _mock_result(
        {"start_index": 10, "end_index": 15, "confidence_score": 0.9, "needs_review": False},
        {"start_index": 0, "end_index": 5, "confidence_score": 0.9, "needs_review": False},
        {"start_index": 5, "end_index": 10, "confidence_score": 0.9, "needs_review": False},
    )
    with patch("voxdirector.agents.alpha_ingestion.call_structured", return_value=mocked):
        chapters = segment_chapters(text)
    assert [c["start_index"] for c in chapters] == [0, 5, 10]
