"""Agent Gamma (voxdirector.agents.gamma_prosody) - test bang mock LLM,
KHONG can GEMINI_API_KEY that."""
from unittest.mock import patch

from voxdirector.agents.gamma_prosody import GammaOutput, Segment, tag_segments
from voxdirector.config import CONFIDENCE_THRESHOLD


def _mock_result(*segments):
    return GammaOutput(segments=[Segment(**s) for s in segments])


def test_empty_chunk_returns_empty_list():
    assert tag_segments("") == []
    assert tag_segments("   ") == []


def test_narration_and_dialogue_classified():
    mocked = _mock_result(
        {"text": "Trời đã tối.", "segment_type": "narration", "speaker_id": None,
         "confidence_score": 0.95},
        {"text": "Ngươi là ai?", "segment_type": "dialogue", "speaker_id": "Lý Phong",
         "confidence_score": 0.9},
    )
    with patch("voxdirector.agents.gamma_prosody.call_structured", return_value=mocked):
        segments = tag_segments("Trời đã tối. \"Ngươi là ai?\" Lý Phong hỏi.")

    assert len(segments) == 2
    assert segments[0]["segment_type"] == "narration"
    assert segments[0]["speaker_id"] is None
    assert segments[1]["segment_type"] == "dialogue"
    assert segments[1]["speaker_id"] == "Lý Phong"


def test_low_confidence_forces_speaker_id_none_even_if_llm_guessed():
    mocked = _mock_result(
        {"text": "Ai đó nói nhỏ.", "segment_type": "dialogue", "speaker_id": "Lý Phong",
         "confidence_score": CONFIDENCE_THRESHOLD - 0.1},
    )
    with patch("voxdirector.agents.gamma_prosody.call_structured", return_value=mocked):
        segments = tag_segments("Ai đó nói nhỏ.")

    assert segments[0]["speaker_id"] is None


def test_high_confidence_keeps_speaker_id():
    mocked = _mock_result(
        {"text": "Lý Phong bước tới.", "segment_type": "dialogue", "speaker_id": "Lý Phong",
         "confidence_score": CONFIDENCE_THRESHOLD + 0.1},
    )
    with patch("voxdirector.agents.gamma_prosody.call_structured", return_value=mocked):
        segments = tag_segments("Lý Phong bước tới.")

    assert segments[0]["speaker_id"] == "Lý Phong"


def test_narration_never_has_forced_speaker_id_removed_incorrectly():
    """narration voi confidence thap van giu speaker_id=None (von da None) -
    khong lam gi khac thuong khi ep lai None -> None."""
    mocked = _mock_result(
        {"text": "Gió thổi nhẹ.", "segment_type": "narration", "speaker_id": None,
         "confidence_score": 0.5},
    )
    with patch("voxdirector.agents.gamma_prosody.call_structured", return_value=mocked):
        segments = tag_segments("Gió thổi nhẹ.")

    assert segments[0]["speaker_id"] is None
    assert segments[0]["segment_type"] == "narration"
