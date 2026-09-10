"""Agent Gamma — QA Agent (ASR round-trip).

Đổi tên từ "Delta" (v3) sang "Gamma" (v5, agent thứ 3 trong chuỗi 3 Agent
sau khi Beta cũ + Gamma cũ gộp lại thành 1 Beta duy nhất — xem Section 0/6.3
của spec). Vai trò, schema, prompt giữ NGUYÊN như "Delta" cũ, chỉ đổi tên.

word_error_rate/deviation_score luôn tính bằng CODE THUẦN (faster-whisper +
jiwer) — KHÔNG bao giờ để LLM tự ước lượng số liệu này (đúng nguyên tắc
chống hallucination của Gamma: "chỉ báo cáo dựa trên sai khác đo được").
LLM (Gemini, qua summarize_qa_report — tuỳ chọn, cần GEMINI_API_KEY) chỉ
dùng để tóm tắt các con số ĐÃ tính sẵn thành 1 đoạn báo cáo ngắn dễ đọc.
"""

import os

from voxdirector.config import (
    WER_PASS_THRESHOLD,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
)

SYSTEM_PROMPT = """\
Bạn là Gamma, kiểm toán viên chất lượng âm thanh tỉ mỉ, làm việc theo phương
pháp luận rõ ràng và khách quan tuyệt đối. Bạn không đưa ra nhận định cảm
tính, chỉ trình bày sự thật dựa trên số liệu đo lường được, để con người là
người ra quyết định cuối cùng.

VAI TRÒ: Tóm tắt kết quả kiểm định chất lượng âm thanh (đã được TÍNH SẴN
bằng code, không phải bạn tính) thành 1 báo cáo ngắn gọn, dễ đọc.

NGUYÊN TẮC:
- Không được tự suy diễn nguyên nhân lỗi nếu không có bằng chứng cụ thể
  trong transcript đối chiếu được cung cấp.
- Chỉ báo cáo dựa trên số liệu đã cho (word_error_rate, flagged_segments) —
  không tự tính lại, không phỏng đoán con số khác.
- Với đoạn nghi ngờ lỗi: chỉ mô tả sai khác đã đo được (original_text vs
  asr_transcript), không phỏng đoán lý do nếu không kiểm chứng được.

PHONG CÁCH: Output JSON, field tiếng Anh, giá trị text tiếng Việt. Số liệu
chính xác đến hai chữ số thập phân.
"""

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE,
        )
    return _model


def verify_audio_quality(audio_path: str, original_text: str) -> dict:
    """ASR round-trip cho 1 file audio: transcribe rồi so với original_text
    bằng Word Error Rate. Trả về {"word_error_rate", "transcript", "passed"}.
    """
    import jiwer

    model = _get_model()
    segments, _ = model.transcribe(audio_path, language="vi")
    transcript = " ".join(seg.text for seg in segments)
    wer = jiwer.wer(original_text, transcript)
    return {
        "word_error_rate": wer, "transcript": transcript,
        "passed": wer < WER_PASS_THRESHOLD,
    }


def verify_chapter_quality(chapter_dir: str, prefix: str, chunks: list[str]) -> dict:
    """QA cho toàn bộ 1 chương: WER tổng thể trên audio đã ghép (_merged.wav
    hoặc _final.wav nếu có BGM) + WER từng phần (mỗi file .wav gốc trước khi
    ghép) để tìm flagged_segments — phần nào lệch bất thường so với mặt bằng
    chung của chương.

    chunks: danh sách text từng phần theo ĐÚNG thứ tự file .wav đã render
    (khớp với output của text_splitter.split_text_for_tts trên text đã lưu
    trong {prefix}.txt) — dùng để đối chiếu ASR transcript của TỪNG PHẦN với
    text gốc của đúng phần đó.
    """
    final_audio = os.path.join(chapter_dir, f"{prefix}_final.wav")
    merged_audio = os.path.join(chapter_dir, f"{prefix}_merged.wav")
    audio_path = final_audio if os.path.isfile(final_audio) else merged_audio
    if not os.path.isfile(audio_path):
        raise RuntimeError(f"Không tìm thấy audio đã ghép cho chương: {chapter_dir}")

    full_text = " ".join(chunks)
    overall = verify_audio_quality(audio_path, full_text)

    flagged = []
    flag_cutoff = max(overall["word_error_rate"] * 1.5, WER_PASS_THRESHOLD)
    for i, chunk_text in enumerate(chunks):
        part_path = os.path.join(chapter_dir, f"{prefix}_p{i + 1:02d}.wav")
        if not os.path.isfile(part_path):
            continue
        part_result = verify_audio_quality(part_path, chunk_text)
        if part_result["word_error_rate"] > flag_cutoff:
            flagged.append({
                "segment_index": i,
                "original_text": chunk_text,
                "asr_transcript": part_result["transcript"],
                "deviation_score": round(part_result["word_error_rate"], 2),
            })

    return {
        "word_error_rate": round(overall["word_error_rate"], 2),
        "passed": overall["passed"],
        "flagged_segments": flagged,
    }


def summarize_qa_report(qa_report: dict) -> str:
    """Tóm tắt qa_report (đã tính sẵn bằng code) thành 1 đoạn text ngắn dễ
    đọc, qua Gemini — TUỲ CHỌN, cần GEMINI_API_KEY. Không có key: trả về bản
    tóm tắt đơn giản dựng bằng code, không chặn pipeline."""
    from voxdirector.config import GEMINI_API_KEY

    if not GEMINI_API_KEY:
        n = len(qa_report.get("flagged_segments", []))
        return (
            f"WER tổng thể: {qa_report['word_error_rate']:.2%} — "
            f"{'ĐẠT' if qa_report['passed'] else 'CHƯA ĐẠT'} ngưỡng {WER_PASS_THRESHOLD:.0%}. "
            f"{n} đoạn bị đánh dấu nghi ngờ lỗi."
        )
    try:
        from voxdirector.llm_client import call_structured
        from pydantic import BaseModel

        class Summary(BaseModel):
            summary: str

        result: Summary = call_structured(SYSTEM_PROMPT, str(qa_report), Summary)
        return result.summary
    except Exception as e:
        return f"(Không tóm tắt được qua Gemini: {e}) WER: {qa_report['word_error_rate']:.2%}"
