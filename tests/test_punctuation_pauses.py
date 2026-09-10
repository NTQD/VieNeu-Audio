"""pipeline.punctuation_pauses - test bang du lieu bang tra gia lap (khong
phu thuoc data/punctuation_pauses.json that de test doc lap voi viec doi so
lieu do doi ngu tai len sau nay)."""
from pipeline.punctuation_pauses import split_chunk_by_punctuation

TABLE = {
    ",": 150, ".": 400, "!": 400, "?": 400, "...": 700, "…": 700,
    ";": 300, ":": 300, "-": 200, "–": 200, "—": 250,
    "(": 100, ")": 100, "\"": 50, "'": 50, "“": 50, "”": 50,
    "?!": 500, "!?": 500, "dialogue_dash_line_start": 350,
}


def test_no_punctuation_returns_single_piece_no_pauses():
    pieces, pauses = split_chunk_by_punctuation("Trời đẹp quá", table=TABLE)
    assert pieces == ["Trời đẹp quá"]
    assert pauses == []


def test_simple_comma_period():
    text = "Cô ấy hỏi, giọng đầy lo lắng."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert pieces == ["Cô ấy hỏi", "giọng đầy lo lắng"]
    assert pauses == [150]


def test_punctuation_stripped_from_pieces():
    pieces, _ = split_chunk_by_punctuation("Anh có chắc không? Đừng làm vậy!", table=TABLE)
    for p in pieces:
        assert "?" not in p and "!" not in p


def test_longer_mark_not_matched_as_shorter_substring():
    """"..." phai duoc nhan dien nhu 1 khoi, khong bi 3 dau "." rieng le bat
    nham (se cho ra 700ms dung 1 lan, khong phai 400ms x 3 lan)."""
    text = "Cô ấy níu tay anh lại... rồi im lặng."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert pauses[0] == 700
    assert pieces == ["Cô ấy níu tay anh lại", "rồi im lặng"]


def test_question_exclaim_combo_mark():
    pieces, pauses = split_chunk_by_punctuation("Cái gì?! Không thể nào.", table=TABLE)
    assert pauses[0] == 500
    assert pieces == ["Cái gì", "Không thể nào"]


def test_dialogue_dash_line_start_uses_its_own_duration():
    text = "Trời đã tối.\n- Anh đi đâu đấy?\nCô ấy hỏi."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert pieces == ["Trời đã tối", "Anh đi đâu đấy", "Cô ấy hỏi"]
    # Dau "." va dialogue-dash chi cach nhau boi 1 dong trong (khong co chu
    # nao o giua) - gop thanh 1 ranh gioi duy nhat, lay max(400, 350)=400
    # (xem test_consecutive_punctuation_no_text_between_merges_pause). Dau
    # "?" o cuoi dung mot minh, khong bi gop.
    assert pauses == [400, 400]


def test_dialogue_dash_directly_after_sentence_end_merges_via_max():
    """"lạnh." va dong thoai moi chi cach nhau 1 dau xuong dong (khong co
    chu o giua) - dung 1 diem noi duy nhat trong audio (khong co gi de doc
    giua 2 dau cau), nen gop thanh 1 khoang lang = max(400, 350) = 400,
    giong het truong hop 2 dau cau lien tiep khong co chu o giua (xem test
    o tren) - day la hanh vi CO CHU DICH, khong phai loi."""
    text = "Trời đã tối. Gió bắt đầu lạnh.\n- Anh đi đâu đấy?\nCô ấy hỏi."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert pieces == ["Trời đã tối", "Gió bắt đầu lạnh", "Anh đi đâu đấy", "Cô ấy hỏi"]
    assert pauses == [400, 400, 400]


def test_dialogue_dash_gets_its_own_350ms_when_preceded_by_real_content():
    """Khi dong TRUOC dialogue-dash CO chu that su (khong phai chi khoang
    trang/xuong dong), dash phai duoc gan dung 350ms cua rieng no, khong bi
    gop/ghi de boi dau cau nao khac."""
    text = "Cô ấy hỏi\n- Anh đi đâu đấy?\nCô ấy hỏi lại."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert pieces == ["Cô ấy hỏi", "Anh đi đâu đấy", "Cô ấy hỏi lại"]
    assert pauses == [350, 400]


def test_generic_dash_not_confused_with_dialogue_dash():
    """Dau gach ngang KHONG o dau dong (vd. dung nhu 1 dau ngoac don-tam
    trong cau) phai dung quy tac "-" thong thuong (200ms), khong phai
    dialogue_dash_line_start (350ms)."""
    text = "Anh ấy - một người lạ mặt - bước vào phòng."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert 200 in pauses
    assert 350 not in pauses


def test_dialogue_dash_at_very_start_of_chunk_no_leading_empty_piece():
    text = "- Anh đi đâu đấy?\nCô ấy hỏi."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert pieces == ["Anh đi đâu đấy", "Cô ấy hỏi"]
    assert pauses == [400]  # khong co khoang lang "truoc" manh dau tien


def test_pieces_and_pauses_length_invariant():
    text = "A, b, c. D! E? F... G."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert len(pauses) == len(pieces) - 1


def test_consecutive_punctuation_no_text_between_merges_pause():
    """2 dau cau lien tiep khong co chu o giua (vd. do loi go van ban) -
    khong duoc lam mat khoang lang, ma gop lai (lay max) vao khoang lang
    ke truoc/sau gan nhat con hop le."""
    text = "Thật à?!."
    pieces, pauses = split_chunk_by_punctuation(text, table=TABLE)
    assert len(pauses) == len(pieces) - 1
