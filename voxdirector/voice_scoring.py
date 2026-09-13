"""Phase 2 cua ARCHITECTURE_AND_AGENTS_REVIEW_2026-09-13.md ("Richer genre
signal") - chon giong doc bang 1 ham cham diem nho, minh bach, thay vi tra
bang genre_to_voice PHANG (1 the loai -> DUNG 1 giong co dinh, moi van ban
"khac" luon nhan cung 1 giong mac dinh bat ke tone/nhip/doi tuong that su
cua no).

CANH BAO (giong tinh than _note trong data/voice_presets.json ve chinh
genre_to_voice): day la HEURISTIC DOT DAU (first-pass), CHUA duoc kiem
chung bang 1 lan nghe that - trong so cham diem ben duoi la suy doan hop ly
dua tren nhan gender/region/style CO SAN cua tung giong (KHONG bia them du
lieu moi cho tung giong - dung dung field da co trong data/voice_presets.json),
can doi ngu nghe that roi tinh chinh lai gia tri trong so, giong y het cach
genre_to_voice ban dau cung can lam.
"""

from typing import Optional

# Trong so cham diem - hang so ro rang tach rieng, de doi sau khi co ket
# qua nghe that, khong an trong logic ham _score().
#
# _GENRE_DEFAULT_BONUS = 1.0 (KHONG phai gia tri lon hon, xac nhan co THAT
# qua test truc tiep score_and_select_voice() khi xay dung tinh nang nay):
# voi bonus = 3.0, no LUON AT het 3-4 bonus tag khac cong lai, khien ket qua
# quay lai dung 1 giong mac dinh cho MOI to hop tone/pacing/audience - chinh
# xac cai bug ma tinh nang nay duoc yeu cau de sua ("khac -> luon nhan cung
# 1 giong mac dinh"). Bonus = 1.0 dat genre_to_voice ngang hang 1 tin hieu
# trong so nhieu tin hieu, khong con la mo neo lan at tat ca.
_GENRE_DEFAULT_BONUS = 1.0  # 1 trong nhieu tin hieu, KHONG con la mo neo lan at
_NARRATION_STYLE_BONUS = 1.0  # doc_truyen/ke_chuyen hop tran thuat dai hon tin_tuc/tu_nhien
_PACING_FAST_STYLE_BONUS = 1.0  # nhanh -> uu tien style tin_tuc (nhip doc gon, nhanh)
_PACING_SLOW_STYLE_BONUS = 1.0  # cham -> uu tien style ke_chuyen/doc_truyen
_TONE_DARK_GENDER_BONUS = 1.0  # u_toi -> uu tien giong nam (am vuc tram hon)
_TONE_LIGHT_GENDER_BONUS = 1.0  # tuoi_sang -> uu tien giong nu
_AUDIENCE_CHILD_GENDER_BONUS = 1.0  # thieu_nhi -> uu tien giong nu
_AUDIENCE_ADULT_STYLE_BONUS = 1.0  # nguoi_lon -> uu tien style ke_chuyen (tran thuat truong thanh)
_AUDIENCE_TEEN_STYLE_BONUS = 1.0  # thanh_thieu_nien -> uu tien style doc_truyen

_NARRATION_STYLES = {"doc_truyen", "ke_chuyen"}


def _score(voice: dict, genre_default_id: str, tone: Optional[str], pacing: Optional[str],
           target_audience: Optional[str]) -> float:
    s = 0.0
    if voice["id"] == genre_default_id:
        s += _GENRE_DEFAULT_BONUS
    style = voice.get("style")
    gender = voice.get("gender")
    if style in _NARRATION_STYLES:
        s += _NARRATION_STYLE_BONUS
    if pacing == "nhanh" and style == "tin_tuc":
        s += _PACING_FAST_STYLE_BONUS
    if pacing == "cham" and style in _NARRATION_STYLES:
        s += _PACING_SLOW_STYLE_BONUS
    if tone == "u_toi" and gender == "male":
        s += _TONE_DARK_GENDER_BONUS
    if tone == "tuoi_sang" and gender == "female":
        s += _TONE_LIGHT_GENDER_BONUS
    if target_audience == "thieu_nhi" and gender == "female":
        s += _AUDIENCE_CHILD_GENDER_BONUS
    if target_audience == "nguoi_lon" and style == "ke_chuyen":
        s += _AUDIENCE_ADULT_STYLE_BONUS
    if target_audience == "thanh_thieu_nien" and style == "doc_truyen":
        s += _AUDIENCE_TEEN_STYLE_BONUS
    return s


def score_and_select_voice(
    genre: Optional[str],
    tone: Optional[str],
    pacing: Optional[str],
    target_audience: Optional[str],
    voice_presets: dict,
) -> str:
    """Cham diem tung giong trong voice_presets['voices'] dua tren
    gender/region/style CO SAN, doi chieu voi the loai + 3 nhan phu Alpha
    vua tra ve (tone/pacing/target_audience). Tra ve id giong diem cao nhat;
    hoa diem -> uu tien giong mac dinh cua chinh the loai do (genre_to_voice),
    roi den giong dau tien trong danh sach - luon deterministic, khong bao
    gio ngau nhien giua 2 lan goi cung tham so."""
    voices = voice_presets["voices"]
    if not voices:
        return voice_presets["genre_to_voice"]["default"]

    genre_to_voice = voice_presets["genre_to_voice"]
    genre_default_id = genre_to_voice.get(genre, genre_to_voice["default"])

    scored = [(v, _score(v, genre_default_id, tone, pacing, target_audience)) for v in voices]
    best_score = max(score for _, score in scored)
    top_voices = [v for v, score in scored if score == best_score]

    for v in top_voices:
        if v["id"] == genre_default_id:
            return v["id"]
    return top_voices[0]["id"]
