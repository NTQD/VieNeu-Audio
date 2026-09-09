"""voxdirector.graph - kiem tra dispatch flow LangGraph (Section 7 cua spec)
bang cach mock 3 ham Agent that su (segment_chapters/run_beta/tag_segments)
+ text_normalizer/text_splitter that (khong can mock, deterministic thuan
code) - xac nhan graph dieu phoi ĐÚNG THỨ TỰ Alpha -> Beta -> normalize ->
split -> Gamma va gop state dung nhu VoxDirectorState mo ta."""
from unittest.mock import patch

from voxdirector.graph import run_ingestion_pipeline


def test_dispatch_order_and_state_shape():
    call_order = []

    def fake_segment_chapters(raw_text):
        call_order.append("alpha")
        return [
            {"text": "Chương 1. Xin chào các bạn.", "start_index": 0, "end_index": 27,
             "confidence_score": 1.0, "needs_review": False},
        ]

    def fake_run_beta(chapter_text, chapter_number):
        call_order.append("beta")
        assert chapter_number == 1  # current_chapter_index (0) + 1
        return {
            "corrected_text": "Xin chào các bạn.",
            "applied_terms": [], "new_entry_candidates": [],
        }

    def fake_tag_segments(chunk):
        call_order.append("gamma")
        return [{"text": chunk, "segment_type": "narration", "speaker_id": None,
                  "confidence_score": 1.0}]

    with patch("voxdirector.graph.segment_chapters", side_effect=fake_segment_chapters), \
         patch("voxdirector.graph.run_beta", side_effect=fake_run_beta), \
         patch("voxdirector.graph.tag_segments", side_effect=fake_tag_segments):
        final_state = run_ingestion_pipeline("Chương 1. Xin chào các bạn.")

    # Thu tu dispatch dung nhu Section 7: Alpha -> Beta -> ... -> Gamma.
    # normalize/split la code thuan (khong mock), nen khong xuat hien trong
    # call_order nhung van chay xen giua beta va gamma theo dung graph edges.
    assert call_order == ["alpha", "beta", "gamma"]

    # State cuoi cung phai co du cac field ma cac node da tung ghi vao.
    assert final_state["chapters"][0]["text"] == "Chương 1. Xin chào các bạn."
    assert final_state["corrected_text"] == "Xin chào các bạn."
    assert "normalized_text" in final_state
    assert "split_chunks" in final_state
    assert len(final_state["tagged_segments"]) >= 1
    assert final_state["tagged_segments"][0]["segment_type"] == "narration"


def test_only_processes_first_chapter_not_all():
    """run_ingestion_pipeline() la entry point THU NGHIEM/DOC LAP (xem
    docstring graph.py) - CHI xu ly chuong DAU TIEN ma Alpha tach duoc, KHONG
    lap qua toan bo danh sach chapters. Vong lap da chuong THAT su nam o
    pipeline/auto_tts.py (_process_chapter_e2e), khong phai o graph nay."""
    def fake_segment_chapters(raw_text):
        return [
            {"text": "Chương 1 nội dung.", "start_index": 0, "end_index": 18,
             "confidence_score": 1.0, "needs_review": False},
            {"text": "Chương 2 nội dung.", "start_index": 19, "end_index": 37,
             "confidence_score": 1.0, "needs_review": False},
        ]

    def fake_run_beta(chapter_text, chapter_number):
        return {"corrected_text": chapter_text, "applied_terms": [], "new_entry_candidates": []}

    def fake_tag_segments(chunk):
        return []

    with patch("voxdirector.graph.segment_chapters", side_effect=fake_segment_chapters), \
         patch("voxdirector.graph.run_beta", side_effect=fake_run_beta), \
         patch("voxdirector.graph.tag_segments", side_effect=fake_tag_segments):
        final_state = run_ingestion_pipeline("Chương 1 nội dung. Chương 2 nội dung.")

    assert len(final_state["chapters"]) == 2  # Alpha tach ra ca 2 chuong...
    assert final_state["current_chapter_index"] == 0  # ...nhung chi xu ly chuong 0
    assert final_state["corrected_text"] == "Chương 1 nội dung."  # KHONG phai chuong 2
