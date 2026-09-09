"""Wrapper duy nhất cho Gemini API — mọi Agent gọi LLM qua đây, không tự
import google-genai riêng lẻ. Giúp đổi model/provider ở 1 chỗ duy nhất nếu
cần sau này.
"""

import json
import time

from voxdirector.config import GEMINI_API_KEY, GEMINI_MODEL

_client = None

# Số lần thử lại tối đa khi gặp lỗi 5xx tạm thời (KHÔNG áp dụng cho lỗi 4xx
# như 429/404 — retry không giải quyết được vấn đề billing/model sai, chỉ
# tốn thêm quota vô ích). Xác nhận CÓ THẬT khi test Agent Alpha
# (2026-09-08): "gemini-3.6-flash" trả 503 UNAVAILABLE ("high demand") ngẫu
# nhiên ở khoảng 1/3 lượt gọi thật — không phải giả định, đo được trực tiếp.
_MAX_RETRIES = 3
_RETRY_BACKOFF_S = 2.0  # nhân đôi mỗi lần thử lại: 2s, 4s, 8s


def _get_client():
    """Khởi tạo Gemini client, cache lại (chỉ tạo 1 lần)."""
    global _client
    if _client is None:
        from google import genai

        if not GEMINI_API_KEY:
            raise RuntimeError(
                "Thiếu GEMINI_API_KEY (hoặc GOOGLE_API_KEY) trong biến môi trường. "
                "Đặt trước khi gọi bất kỳ Agent nào."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def call_structured(system_prompt, user_content, response_schema):
    """Gọi Gemini với JSON mode bắt buộc — trả về dict đã parse theo
    response_schema (Pydantic model class).

    KHÔNG dùng cách "please return JSON" bằng free text — dùng đúng cơ chế
    structured output/JSON mode của Gemini (response_mime_type +
    response_schema) để tránh model trả markdown fences hoặc giải thích xen
    lẫn JSON.

    Model được GHIM CỨNG theo config.GEMINI_MODEL cho MỌI lệnh gọi trong 1
    lần chạy pipeline — không dùng auto-routing/multi-provider, để kết quả
    có thể tái lập (xem Section 7 của spec).
    """
    from google.genai import errors, types

    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=response_schema,
    )

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL, contents=user_content, config=config,
            )
            break
        except errors.ServerError as e:
            # Lỗi 5xx tạm thời (vd. 503 "high demand") — thử lại với backoff
            # tăng dần. Lỗi 4xx (ClientError — sai model, hết quota/billing)
            # KHÔNG retry ở đây, để lộ ra ngay cho người gọi xử lý.
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
    else:
        raise last_error

    # response.parsed đã là instance của response_schema khi SDK parse thành
    # công; fallback về json.loads(response.text) nếu parsed không khả dụng
    # (vd. phiên bản SDK cũ hơn không hỗ trợ .parsed).
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        return parsed
    return response_schema.model_validate(json.loads(response.text))
