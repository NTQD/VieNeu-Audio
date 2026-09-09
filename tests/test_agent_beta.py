"""Agent Beta (voxdirector.agents.beta_consistency) — test bang mock LLM +
mock ChromaDB, KHONG can GEMINI_API_KEY hay chromadb that."""
from unittest.mock import patch

from voxdirector.agents.beta_consistency import (
    AppliedTerm,
    BetaOutput,
    NewEntryCandidate,
    _build_user_content,
    approve_new_entries,
    run_beta,
)


def _mock_output(corrected_text="", applied=None, new=None):
    return BetaOutput(
        corrected_text=corrected_text,
        applied_terms=[AppliedTerm(**a) for a in (applied or [])],
        new_entry_candidates=[NewEntryCandidate(**n) for n in (new or [])],
    )


def test_build_user_content_empty_glossary():
    content = _build_user_content("Văn bản chương.", [])
    assert "glossary hiện đang trống" in content
    assert "Văn bản chương." in content


def test_build_user_content_with_entries():
    glossary = [{"original_term": "Red Matt", "canonical_form": "Red Matt", "entity_type": "character"}]
    content = _build_user_content("Văn bản chương.", glossary)
    assert "Red Matt -> Red Matt (character)" in content


def test_run_beta_returns_corrected_text_and_terms():
    mocked = _mock_output(
        corrected_text="Red Matt bước vào phòng.",
        applied=[{"original": "Red Matt", "canonical_form": "Red Matt"}],
        new=[{"term": "Huyết Nguyệt Tông", "entity_type": "term", "confidence_score": 0.83}],
    )
    with patch("voxdirector.agents.beta_consistency.query_glossary", return_value=[]) as mock_query, \
         patch("voxdirector.agents.beta_consistency.call_structured", return_value=mocked):
        result = run_beta("Red Matt bước vào phòng.", chapter_number=1)

    mock_query.assert_called_once_with("Red Matt bước vào phòng.")
    assert result["corrected_text"] == "Red Matt bước vào phòng."
    assert result["applied_terms"] == [{"original": "Red Matt", "canonical_form": "Red Matt"}]
    assert result["new_entry_candidates"][0]["term"] == "Huyết Nguyệt Tông"


def test_run_beta_queries_glossary_before_calling_llm():
    """query_glossary() phai duoc goi TRUOC call_structured() - dung thu tu
    RAG: truy xuat roi moi dua vao prompt (khong phai nguoc lai)."""
    call_order = []
    mocked = _mock_output(corrected_text="ok")

    def _fake_query(*a, **kw):
        call_order.append("query")
        return []

    def _fake_call_structured(*a, **kw):
        call_order.append("llm")
        return mocked

    with patch("voxdirector.agents.beta_consistency.query_glossary", side_effect=_fake_query), \
         patch("voxdirector.agents.beta_consistency.call_structured", side_effect=_fake_call_structured):
        run_beta("text", chapter_number=1)

    assert call_order == ["query", "llm"]


def test_approve_new_entries_writes_valid_candidates():
    candidates = [
        {"term": "Huyết Nguyệt Tông", "entity_type": "term", "confidence_score": 0.9},
        {"term": "Lý Phong", "entity_type": "character", "confidence_score": 0.95, "canonical_form": "Lý Phong"},
    ]
    with patch("voxdirector.agents.beta_consistency.add_entry") as mock_add:
        approve_new_entries(candidates, chapter_number=3)

    assert mock_add.call_count == 2
    written = [call.args[0] for call in mock_add.call_args_list]
    assert written[0].original_term == "Huyết Nguyệt Tông"
    assert written[0].canonical_form == "Huyết Nguyệt Tông"  # fallback = term khi khong co canonical_form
    assert written[0].first_seen_chapter == 3
    assert written[1].canonical_form == "Lý Phong"


def test_approve_new_entries_skips_invalid_entity_type():
    """entity_type khong nam trong {"character","place","term"} (vd. LLM tra
    ve gia tri la, hoac curator go nham khi sua bang) phai bi bo qua thay vi
    lam GlossaryEntry validation crash ca ham."""
    candidates = [
        {"term": "Ổn", "entity_type": "character", "confidence_score": 0.9},
        {"term": "Lỗi", "entity_type": "not_a_real_type", "confidence_score": 0.9},
    ]
    with patch("voxdirector.agents.beta_consistency.add_entry") as mock_add:
        approve_new_entries(candidates, chapter_number=1)

    assert mock_add.call_count == 1
    assert mock_add.call_args_list[0].args[0].original_term == "Ổn"


def test_approve_new_entries_empty_list_does_nothing():
    with patch("voxdirector.agents.beta_consistency.add_entry") as mock_add:
        approve_new_entries([], chapter_number=1)
    mock_add.assert_not_called()
