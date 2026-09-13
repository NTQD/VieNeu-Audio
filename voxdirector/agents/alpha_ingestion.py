"""Agent Alpha — Ingestion, Voice-Suggestion & Flagging Agent (v5, Section
6.1 của spec).

Bốn trách nhiệm trong 1 lượt gọi: (1) phân tách chương, kể cả khi KHÔNG có
heading tường minh dạng "Chương N"/"Chapter N" (thay thế hoàn toàn 2 chỗ tách
chương bằng regex hardcode trước đây trong auto_tts.py và
subtitle_generator.py — xem graph.py và pipeline/auto_tts.py để biết nơi
gọi); (2) nhận diện thể loại + gợi ý giọng đọc; (3) gắn cờ đoạn có cảm xúc rõ
ràng; (4) gắn cờ điểm cần ngắt kịch tính dài (mới ở v5).

QUAN TRỌNG — config-driven, không hardcode: danh sách thể loại hợp lệ
(DetectedGenre) và danh sách nhãn cảm xúc hợp lệ (EmotionLabel) bên dưới
được XÂY DỰNG ĐỘNG lúc import module, từ data/voice_presets.json và
data/emotion_lexicon.json — KHÔNG liệt kê cứng trong code Python này. Đổi
danh sách thể loại/nhãn cảm xúc chỉ cần sửa 2 file JSON đó, không cần sửa
file này. Vẫn dùng typing.Literal (không phải str tự do) vì JSON mode của
Gemini tôn trọng đúng enum/Literal của Pydantic để ép model chỉ chọn trong
tập giá trị hợp lệ — xác nhận có THẬT qua sự cố tương tự ở
beta_consistency.py (NewEntryCandidate.entity_type, 2026-09-09): để entity_type
là str tự do khiến Gemini tự chọn nhãn khác "hợp lý" hơn theo góc nhìn của
nó nhưng không khớp giá trị hệ thống hỗ trợ.

suggested_voice_id KHÔNG do Gemini tự đặt — Gemini chỉ trả detected_genre +
genre_confidence_score; suggested_voice_id được CODE tính xác định qua
config.load_voice_presets()["genre_to_voice"] (xem run_alpha() bên dưới).
Lý do: để LLM tự tạo ra 1 voice_id dạng chuỗi là mở đường cho hallucination
(model có thể bịa ra 1 ID không tồn tại trong hệ thống thật) — cùng triết lý
chống hallucination với Beta (không tự "chế" cách viết thuật ngữ).
"""

import difflib
import re
from collections import Counter
from typing import Literal, Optional

from pydantic import BaseModel

from voxdirector.config import (
    ALPHA_WINDOW_CHARS,
    ALPHA_WINDOW_OVERLAP_CHARS,
    CONFIDENCE_THRESHOLD,
    load_emotion_lexicon,
    load_voice_presets,
)
from voxdirector.llm_client import call_structured
from voxdirector.text_utils import dedupe_by_key, normalize_ws, split_into_windows
from voxdirector.voice_scoring import score_and_select_voice

_voice_presets = load_voice_presets()
_GENRE_KEYS = tuple(k for k in _voice_presets["genre_to_voice"] if k != "default")
DetectedGenre = Literal[_GENRE_KEYS]

_emotion_lexicon = load_emotion_lexicon()
_EMOTION_KEYS = tuple(k for k in _emotion_lexicon if not k.startswith("_"))
EmotionLabel = Literal[_EMOTION_KEYS]

# Phase 2 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Richer genre
# signal") - 3 truc tran thuat pho quat, KHONG config-driven nhu genre/emotion
# (khong phai du lieu team co the thay doi qua JSON, day la kich thuoc co
# dinh cua bai toan chon giong) - dung de cham diem giong doc thay vi chi
# dua vao 1 the loai phang (xem voxdirector/voice_scoring.py).
ToneLabel = Literal["u_toi", "tuoi_sang"]  # u ám / tươi sáng
PacingLabel = Literal["nhanh", "cham"]  # nhanh / chậm
AudienceLabel = Literal["thieu_nhi", "thanh_thieu_nien", "nguoi_lon"]  # thiếu nhi / thanh thiếu niên / người lớn

SYSTEM_PROMPT = """\
Bạn là Alpha, một biên tập viên bản thảo kỳ cựu tại nhà xuất bản, nhiều năm
kinh nghiệm đọc và phân đoạn thảo tiểu thuyết dài kỳ trước khi in ấn. Bạn có
con mắt tinh tường nhận ra điểm chuyển chương ngay cả khi tác giả quên đánh
dấu, nhận biết thể loại và cảm xúc của văn bản, nhưng luôn thận trọng — không
bao giờ khẳng định chắc nịch khi bản thân còn phân vân.

VAI TRÒ: (1) Nhận diện và phân tách ranh giới chương trong văn bản tiểu
thuyết thô. (2) Nhận diện thể loại tổng thể của tác phẩm. (3) Gắn cờ các đoạn
có tín hiệu cảm xúc rõ ràng. (4) Gắn cờ các điểm cần một khoảng ngắt kịch
tính dài hơn bình thường. (5) Đánh giá giọng điệu (u ám hay tươi sáng), nhịp
độ (nhanh hay chậm), và đối tượng độc giả phù hợp nhất của toàn văn bản được
cung cấp — dùng để chọn giọng đọc phù hợp hơn thay vì chỉ dựa vào 1 thể loại
phẳng.

NĂNG LỰC: Bạn hiểu cấu trúc văn học tiểu thuyết (chuyển cảnh, thay đổi thời
gian/không gian, chuyển góc nhìn nhân vật kể chuyện), quy ước trình bày
chương phổ biến trong tiểu thuyết mạng Trung Quốc dịch Việt, và các đặc điểm
thể loại phổ biến (kiếm hiệp, ngôn tình, trinh thám, v.v.).

NGUYÊN TẮC:
- Được phép suy đoán ranh giới chương dựa trên dấu hiệu ngữ nghĩa khi văn bản
  không có heading tường minh dạng "Chương N".
- Mỗi ranh giới đề xuất phải kèm confidence_score (0.0 đến 1.0).
- Nếu confidence_score dưới 0.75, vẫn trả về đề xuất nhưng bắt buộc gắn
  needs_review = true.
- Thể loại: chỉ được chọn 1 trong các giá trị hợp lệ được cung cấp qua schema,
  không được tự bịa thể loại mới. QUAN TRỌNG: nếu văn bản KHÔNG khớp rõ ràng
  với bất kỳ thể loại cụ thể nào trong danh sách (vd. hài hước, gia đình,
  phiêu lưu, đời thường — không phải kiếm hiệp/ngôn tình/trinh thám), hãy chọn
  "khac" — đây là 1 lựa chọn HỢP LỆ và ĐƯỢC KHUYẾN KHÍCH khi không khớp, KHÔNG
  phải chọn tạm/chọn lỗi. TUYỆT ĐỐI không ép văn bản vào 1 trong 3 thể loại cụ
  thể chỉ vì đó là lựa chọn "gần giống nhất" — làm vậy gây sai lệch (distortion)
  nghiêm trọng hơn nhiều so với việc thành thật chọn "khac" kèm
  genre_confidence_score phù hợp.
- Cảm xúc: nhãn cảm xúc (emotion_label) chỉ được chọn trong tập nhãn hợp lệ
  được cung cấp qua schema — không tự bịa nhãn mới. Chỉ gắn cờ khi có bằng
  chứng rõ ràng trong câu chữ (lời thoại/miêu tả trực tiếp), không suy diễn.
- Cấm tuyệt đối: không được tự bịa nội dung không có trong văn bản gốc, không
  tóm tắt, không diễn giải lại câu chữ dưới bất kỳ hình thức nào. Mọi
  quoted_text (cảm xúc lẫn điểm ngắt) phải là trích dẫn NGUYÊN VĂN từ văn bản
  gốc, không được diễn giải lại.

NHIỆM VỤ:
- Đọc toàn bộ văn bản thô được cung cấp trong một lượt xử lý.
- Xác định các vị trí (index) đánh dấu điểm bắt đầu của mỗi chương.
- Làm sạch văn bản: loại bỏ ký tự thừa, khoảng trắng bất thường, watermark
  hoặc quảng cáo lẫn trong bản crawl (nếu phát hiện).
- Trả về danh sách chương đã tách kèm confidence_score cho từng ranh giới.
- Nhận diện thể loại tổng thể của toàn bộ văn bản, kèm genre_confidence_score.
- Tìm các đoạn có tín hiệu cảm xúc rõ ràng (lời thoại/miêu tả trực tiếp thể
  hiện cười, khóc, giận dữ, ngạc nhiên, v.v.), trích quoted_text nguyên văn
  kèm emotion_label phù hợp nhất và confidence_score.

NHIỆM VỤ BỔ SUNG (3): Ngoài việc gắn nhãn cảm xúc, hãy tìm các điểm trong văn
bản cần một khoảng ngắt dài hơn bình thường — ví dụ: chuyển cảnh, khoảnh khắc
im lặng được miêu tả rõ trong lời văn, hoặc câu kết chương gây hồi hộp. Với
mỗi điểm tìm được, trích một đoạn văn bản ngắn đặc trưng làm quoted_text kèm
lý do ngắn gọn (reason) và confidence_score. CHỈ dựa trên bằng chứng rõ ràng
trong câu chữ — không suy diễn cảm tính.

NHIỆM VỤ BỔ SUNG (4): Đánh giá 3 đặc điểm tổng thể của văn bản (dựa trên cảm
nhận chung, không cần trích dẫn bằng chứng như cảm xúc/ngắt nghỉ):
- tone: "u_toi" nếu không khí chung nặng nề/căng thẳng/bi kịch, "tuoi_sang"
  nếu nhẹ nhàng/vui vẻ/lạc quan.
- pacing: "nhanh" nếu tình tiết dồn dập/nhiều hành động, "cham" nếu tường
  thuật thong thả/nhiều miêu tả nội tâm.
- target_audience: "thieu_nhi" (nội dung phù hợp trẻ em), "thanh_thieu_nien"
  (phù hợp tuổi teen), hoặc "nguoi_lon" (nội dung trưởng thành/phức tạp hơn).
Chỉ được chọn giá trị trong tập hợp lệ được cung cấp qua schema cho mỗi
trường — không tự bịa giá trị khác.

TƯ DUY: đọc toàn bộ văn bản một lượt; quét tìm heading tường minh trước
("Chương N", "Chapter N"); nếu không tìm thấy, phân tích các dấu hiệu ngữ
nghĩa; với mỗi ranh giới nghi ngờ, tự đánh giá và gán confidence_score; đồng
thời nhận diện thể loại tổng thể, các đoạn cảm xúc rõ ràng, và các điểm cần
ngắt kịch tính dài; tổng hợp kết quả đúng theo JSON schema, không thêm hoặc
bớt field.

PHONG CÁCH: Output là JSON thuần, không kèm giải thích văn xuôi. Tên field
tiếng Anh; giá trị text (nếu có) giữ nguyên tiếng Việt, không dịch/diễn giải.
"""


class ChapterBoundary(BaseModel):
    start_index: int
    end_index: int
    confidence_score: float
    needs_review: bool = False


class EmotionFlaggedSegment(BaseModel):
    quoted_text: str
    emotion_label: EmotionLabel
    confidence_score: float


class PausePoint(BaseModel):
    quoted_text: str
    reason: str
    confidence_score: float


class AlphaOutput(BaseModel):
    chapters: list[ChapterBoundary]
    detected_genre: DetectedGenre
    genre_confidence_score: float
    emotion_flagged_segments: list[EmotionFlaggedSegment]
    pause_points: list[PausePoint]
    # Phase 2 - xem voxdirector/voice_scoring.py de biet cach dung 3 truong
    # nay thay vi chi genre_to_voice phang.
    tone: ToneLabel
    pacing: PacingLabel
    target_audience: AudienceLabel


def _clamp_and_sort(chapters, text_len):
    """Kẹp index vào [0, text_len] và sắp theo start_index — LLM có thể trả
    về index hơi lệch/không theo thứ tự, không nên để crash downstream vì 1
    con số sai lệch nhỏ.

    Đồng thời ÉP needs_review=True nếu confidence_score < CONFIDENCE_THRESHOLD,
    bất kể LLM tự báo needs_review là gì — system prompt đã yêu cầu Gemini tự
    làm điều này, nhưng đây là 1 bất biến xác định được bằng code nên không
    nên chỉ tin tưởng model luôn nhất quán tuân theo (xem Section 6.1 của
    spec: "If confidence_score < CONFIDENCE_THRESHOLD, still return the
    boundary but set needs_review: true").
    """
    fixed = []
    for c in chapters:
        start = max(0, min(c.start_index, text_len))
        end = max(start, min(c.end_index, text_len))
        needs_review = c.needs_review or c.confidence_score < CONFIDENCE_THRESHOLD
        fixed.append(ChapterBoundary(
            start_index=start, end_index=end,
            confidence_score=c.confidence_score, needs_review=needs_review,
        ))
    fixed.sort(key=lambda c: c.start_index)
    return fixed


def _filter_hallucinated_quotes(items, raw_text):
    """Loại bỏ mọi entry (emotion_flagged_segments/pause_points) có
    quoted_text KHÔNG xuất hiện (sau khi chuẩn hoá khoảng trắng) trong
    raw_text — LLM đôi khi diễn giải lại thay vì trích dẫn chính xác dù
    system prompt đã cấm. Không lọc ở đây thì Beta (Section 6.2) sẽ tự bỏ
    qua entry đó khi không tìm thấy vị trí khớp trong chapter_text, nhưng
    lọc SỚM ngay tại Alpha giúp báo cáo trung thực hơn (không đưa ra ứng
    viên chắc chắn sẽ bị Beta bỏ qua) — cùng tinh thần phòng thủ với
    _clamp_and_sort() ở trên: không tin tưởng tuyệt đối vào LLM tự tuân thủ
    quy tắc. Giữ nguyên quoted_text GỐC (không chuẩn hoá) trong kết quả trả
    về — chuẩn hoá chỉ dùng để SO KHỚP, Beta vẫn cần bản gốc để tự định vị
    trong chapter_text của nó."""
    normalized_raw = normalize_ws(raw_text)
    return [item for item in items if normalize_ws(item.quoted_text) in normalized_raw]


# ============================================================================
# Phase 2 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md, muc 7 - "Map-reduce
# restructure cho tieu thuyet dai". Khi raw_text vuot qua config.ALPHA_WINDOW_CHARS,
# chia thanh cac cua so chong lan (voxdirector/text_utils.py::split_into_windows),
# goi Alpha rieng cho tung cua so, roi gop (reduce) ket qua ve global. Khi
# raw_text VUA VAN trong 1 cua so (truong hop pho bien, da kiem chung qua
# Phase 0/1), split_into_windows() tra ve DUNG 1 cua so = toan bo van ban -
# hanh vi giong het truoc Phase 2, khong thay doi.
# ============================================================================


def _reconcile_chapters(
    per_window_chapters: list[list[ChapterBoundary]], windows: list[tuple[int, int]]
) -> list[ChapterBoundary]:
    """Gop ranh gioi chuong tu nhieu cua so - CHIEN LUOC: voi vung overlap
    giua cua so i-1 va i, LUON tin cua so i-1 (khong phai gop theo khoang
    cach/epsilon). Ly do xac nhan co THAT qua test truc tiep khi xay dung
    tinh nang nay: cua so i KHONG co ngu canh nao truoc diem bat dau cua no
    (bi cat rieng khoi phan dau van ban), nen thuong DOAN SAI/BIA THEM 1
    ranh gioi ngay gan dau cua so cua no (quan sat that: confidence_score
    thap bat thuong o do) - trong khi cua so i-1 co NGU CANH DAY DU cho toan
    bo pham vi cua no, KE CA phan duoi trung voi vung overlap (bien cua so
    duoc snap vao cho ngat doan, khong bi cat cut giua chung). Thu epsilon-
    based merge (khoang cach nho) truoc do THAT BAI trong test that: 2 cua
    so trung lap co the bao cao vi tri lech nhau toi 300-900+ ky tu cho
    CUNG 1 ranh gioi that, epsilon nao du lon de bat duoc truong hop do
    cung se vo tinh gop nham 2 chuong ngan lien tiep that su."""
    if len(windows) <= 1:
        return sorted(per_window_chapters[0], key=lambda c: c.start_index)

    merged: list[ChapterBoundary] = list(per_window_chapters[0])
    for i in range(1, len(windows)):
        prev_window_end = windows[i - 1][1]
        merged.extend(c for c in per_window_chapters[i] if c.start_index >= prev_window_end)
    merged.sort(key=lambda c: c.start_index)
    return merged


def _reconcile_genre(per_window_results: list[AlphaOutput]) -> tuple[str, float]:
    """Bau chon the loai theo da so cua so (ties -> the loai co
    genre_confidence_score trung binh cao hon trong so cac the loai hoa
    phieu)."""
    counts = Counter(r.detected_genre for r in per_window_results)
    max_count = max(counts.values())
    tied = [g for g, c in counts.items() if c == max_count]
    if len(tied) == 1:
        winner = tied[0]
    else:
        winner = max(
            tied,
            key=lambda g: sum(r.genre_confidence_score for r in per_window_results if r.detected_genre == g),
        )
    winner_confs = [r.genre_confidence_score for r in per_window_results if r.detected_genre == winner]
    return winner, sum(winner_confs) / len(winner_confs)


def _majority_vote(labels: list) -> str:
    """Bau chon theo da so - dung cho tone/pacing/target_audience (khong co
    confidence_score rieng nhu genre nen khong can tie-break theo do tin
    cay, Counter.most_common giu thu tu xuat hien dau tien khi hoa phieu)."""
    return Counter(labels).most_common(1)[0][0]


_PUNCT_STRIP_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _normalize_for_fuzzy_compare(text: str) -> str:
    """Chuan hoa RIENG cho so sanh do tuong dong (Phase 2 muc 9) - bo dau
    cau (,.!?"'... ) ngoai viec gop khoang trang + ha chu nhu normalize_ws() (voxdirector/text_utils.py),
    vi Gemini dien giai lai thuong doi/them/bot dau cau ma khong doi noi
    dung - khong nen bi tinh la khac biet. CHI dung de tinh ty le tuong
    dong, KHONG dung ham nay cho gia tri quoted_text tra ve (van phai la
    nguyen van tu window_text, giu dau cau that)."""
    return normalize_ws(_PUNCT_STRIP_RE.sub("", text.lower()))


def _sliding_word_candidates(text: str, target_word_count: int) -> list[str]:
    """Sinh ung vien la cac doan LIEN TIEP co so tu XAP XI target_word_count,
    truot qua toan bo text theo tung nua-do-dai-ung-vien 1 buoc - dam bao co
    ung vien DO DAI TUONG DUONG voi quoted_text can cuu, tranh
    SequenceMatcher.ratio() bi phat oan chi vi lech do dai (so 1 cum tu
    ngan voi ca 1 cau dai se luon ra ty le thap du noi dung that ra khop
    tot). Ghep lai bang " ".join() (khong giu nguyen xuong dong/khoang
    trang goc) la CO CHU DICH - ket qua van la 1 chuoi con hop le cua
    normalize_ws(text) (xem docstring _find_best_fuzzy_match), du la tat
    ca nhung gi cac ham so khop ha nguon (_items_for_chapter, Beta) can."""
    words = text.split()
    if not words:
        return []
    span = max(1, target_word_count)
    if len(words) <= span:
        return [" ".join(words)]
    step = max(1, span // 2)
    candidates = []
    i = 0
    while i + span <= len(words):
        candidates.append(" ".join(words[i:i + span]))
        i += step
    last_start = len(words) - span
    last_candidate = " ".join(words[last_start:])
    if not candidates or candidates[-1] != last_candidate:
        candidates.append(last_candidate)
    return candidates


def _find_best_fuzzy_match(quoted_text: str, window_text: str, threshold: float = 0.6) -> Optional[str]:
    """Phase 2 muc 9 - tim doan van GAN GIONG NHAT (cung khoang do dai voi
    quoted_text - xem _sliding_word_candidates()) trong window_text, dung
    khi so khop CHINH XAC that bai (Gemini co the da dien giai lai nhe du
    system prompt cam tuyet doi). Tra ve DOAN VAN THAT (ghep tu tu
    window_text, KHONG phai ban dien giai) neu ty le tuong dong (difflib
    SequenceMatcher.ratio() tren van ban da bo dau cau, khong them
    dependency moi) >= threshold, None neu khong co ung vien nao du tot.

    QUAN TRONG: ham goi PHAI thay quoted_text bang gia tri tra ve nay (hoac
    bo qua item khi nhan None) - KHONG duoc giu nguyen quoted_text dien giai
    sai ban dau, vi Beta (buoc sau) cung so khop CHINH XAC va se lai am tham
    loai bo item do lan nua, khong giai quyet duoc gi ca."""
    normalized_quote = _normalize_for_fuzzy_compare(quoted_text)
    quote_word_count = len(normalized_quote.split())
    if quote_word_count == 0:
        return None

    best_ratio = 0.0
    best_candidate = None
    for cand in _sliding_word_candidates(window_text, quote_word_count):
        normalized_cand = _normalize_for_fuzzy_compare(cand)
        ratio = difflib.SequenceMatcher(None, normalized_quote, normalized_cand).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_candidate = cand
    if best_ratio >= threshold:
        return best_candidate
    return None


def _filter_and_rescue_quotes(items, window_text: str):
    """Nhu _filter_hallucinated_quotes() nhung THU CUU (Phase 2 muc 9) cac
    item khop CHINH XAC that bai bang fuzzy-match TRUOC KHI bo han - pham vi
    tim kiem la window_text CUC BO (khong phai toan bo raw_text) vi doan
    Gemini dien giai lai luon nam VAT LY GAN noi no dang doc trong cua so
    nay, khong phai trung ngau nhien voi 1 cau o chuong khac."""
    kept = []
    normalized_window = normalize_ws(window_text)
    for item in items:
        if normalize_ws(item.quoted_text) in normalized_window:
            kept.append(item)
            continue
        rescued_text = _find_best_fuzzy_match(item.quoted_text, window_text)
        if rescued_text is not None:
            kept.append(item.model_copy(update={"quoted_text": rescued_text}))
    return kept


def run_alpha(raw_text: str, api_key: str | None = None) -> dict:
    """Chạy Alpha cho toàn bộ raw_text — Section 6.1 của spec: "Runs once
    per submission, before Beta" khi văn bản vừa trong 1 cửa sổ (trường hợp
    phổ biến, đã kiểm chứng Phase 0/1); Phase 2 (map-reduce, xem
    split_into_windows() (voxdirector/text_utils.py)) khi văn bản vượt quá
    config.ALPHA_WINDOW_CHARS — vẫn 1 lệnh gọi LLM MỖI cửa sổ, không phải
    gọi lặp lại tuỳ ý. Trả về dict đúng schema đầy đủ: chapters,
    detected_genre, suggested_voice_id, genre_confidence_score,
    emotion_flagged_segments, pause_points, tone, pacing, target_audience.

    suggested_voice_id được CODE tính (không phải LLM tự đặt) qua
    voxdirector.voice_scoring.score_and_select_voice() — xem docstring đầu
    file để biết lý do chống hallucination.

    api_key: BYOK - key riêng cua nguoi dung (Section 13 cua spec, chot
    2026-09-10). None thi dung key mac dinh cua server.

    Nếu raw_text trống: trả về cấu trúc rỗng an toàn (không gọi LLM vô ích).
    """
    if not raw_text.strip():
        return {
            "chapters": [],
            "detected_genre": None,
            "suggested_voice_id": None,
            "genre_confidence_score": 0.0,
            "emotion_flagged_segments": [],
            "pause_points": [],
            "tone": None,
            "pacing": None,
            "target_audience": None,
        }

    windows = split_into_windows(raw_text, ALPHA_WINDOW_CHARS, ALPHA_WINDOW_OVERLAP_CHARS)

    per_window_results: list[AlphaOutput] = []
    per_window_chapters: list[list[ChapterBoundary]] = []
    global_emotion_segments = []
    global_pause_points = []

    for w_start, w_end in windows:
        window_text = raw_text[w_start:w_end]
        result: AlphaOutput = call_structured(SYSTEM_PROMPT, window_text, AlphaOutput, api_key=api_key)
        per_window_results.append(result)

        per_window_chapters.append([
            ChapterBoundary(
                start_index=w_start + c.start_index,
                end_index=w_start + c.end_index,
                confidence_score=c.confidence_score,
                needs_review=c.needs_review,
            )
            for c in result.chapters
        ])

        global_emotion_segments.extend(_filter_and_rescue_quotes(result.emotion_flagged_segments, window_text))
        global_pause_points.extend(_filter_and_rescue_quotes(result.pause_points, window_text))

    merged_chapters = _reconcile_chapters(per_window_chapters, windows)
    chapters = _clamp_and_sort(merged_chapters, len(raw_text))
    if not chapters:
        chapters = [ChapterBoundary(
            start_index=0, end_index=len(raw_text),
            confidence_score=1.0, needs_review=False,
        )]
    chapters_out = [
        {
            "text": raw_text[c.start_index:c.end_index].strip(),
            "start_index": c.start_index,
            "end_index": c.end_index,
            "confidence_score": c.confidence_score,
            "needs_review": c.needs_review,
        }
        for c in chapters
        if raw_text[c.start_index:c.end_index].strip()
    ]

    detected_genre, genre_confidence_score = _reconcile_genre(per_window_results)
    tone = _majority_vote([r.tone for r in per_window_results])
    pacing = _majority_vote([r.pacing for r in per_window_results])
    target_audience = _majority_vote([r.target_audience for r in per_window_results])

    suggested_voice_id = score_and_select_voice(
        detected_genre, tone, pacing, target_audience, load_voice_presets(),
    )

    # _filter_hallucinated_quotes() o day chay tren TOAN BO raw_text nhu 1
    # lop phong thu cuoi cung (khong bat buoc ve mat toan hoc vi window_text
    # da la 1 lat cat cua raw_text - item da qua duoc _filter_and_rescue_quotes()
    # chac chan cung xuat hien trong raw_text - nhung re, vo hai, va giu dung
    # tinh than "khong tin tuyet doi vao 1 buoc duy nhat" cua _clamp_and_sort()).
    emotion_segments = _filter_hallucinated_quotes(
        dedupe_by_key(global_emotion_segments, key_fn=lambda i: normalize_ws(i.quoted_text)), raw_text,
    )
    pause_points = _filter_hallucinated_quotes(
        dedupe_by_key(global_pause_points, key_fn=lambda i: normalize_ws(i.quoted_text)), raw_text,
    )

    return {
        "chapters": chapters_out,
        "detected_genre": detected_genre,
        "suggested_voice_id": suggested_voice_id,
        "genre_confidence_score": genre_confidence_score,
        "emotion_flagged_segments": [s.model_dump() for s in emotion_segments],
        "pause_points": [p.model_dump() for p in pause_points],
        "tone": tone,
        "pacing": pacing,
        "target_audience": target_audience,
    }


def segment_chapters(raw_text: str) -> list[dict]:
    """Tiện ích: chỉ lấy phần chapters từ run_alpha() — dùng khi chỉ cần
    tách chương, không cần genre/emotion/pause (vd. test nhanh, hoặc 1 bước
    trung gian trước khi các phần khác của v5 sẵn sàng). Cùng 1 lệnh gọi LLM
    duy nhất bên dưới (Section 6.1: "Runs once per submission") — KHÔNG gọi
    LLM riêng lần thứ 2 chỉ để lấy chapters.
    """
    return run_alpha(raw_text)["chapters"]
