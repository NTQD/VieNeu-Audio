"""Bo dem token Gemini thuc te da dung, gop theo job_id - phuc vu uoc tinh
chi phi/job (muc 18 cua master plan). Chi ghi lai SO LIEU DO TU
response.usage_metadata cua chinh Gemini API (khong tu uoc tinh/lam tron) -
xem llm_client.call_structured().

Dung dict toan cuc + lock (CUNG 1 kieu voi JOBS trong backend/app/main.py),
KHONG dung contextvars de luu tong so - vi 1 job trai qua 2 request HTTP/WS
TACH BIET (POST /api/submit chay Alpha, sau do WS /api/ws/{job_id} chay
Beta/QA), contextvars khong song sot qua ranh gioi 2 request doc lap nhu
vay. contextvars CHI dung de truyen job_id hien tai XUONG qua cac ham trung
gian (run_alpha/run_beta/process_chapter) ma KHONG can sua chu ky (signature)
cua tung ham do de nhan them 1 tham so job_id - moi ham trung gian khong can
biet gi ve viec dem token ca."""

import contextvars
import threading

_current_job_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_job_id", default=None
)
_lock = threading.Lock()
_usage_by_job: dict[str, dict[str, dict[str, int]]] = {}


def set_current_job(job_id: str | None) -> None:
    """Goi 1 lan o dau moi request se thuc su goi call_structured() (POST
    /api/submit truoc khi chay Alpha; ws_progress() truoc vong lap chuong) -
    de moi lan goi Gemini ben trong biet ghi token vao job nao. An toan qua
    asyncio.to_thread() (Python tu copy contextvars.copy_context() sang
    thread moi) va qua nhieu request dong thoi (moi request/Task co context
    rieng, khong lech nhau)."""
    _current_job_id.set(job_id)


def record(model: str, prompt_tokens: int, output_tokens: int) -> None:
    """Ghi 1 lan goi Gemini vao tong cua job dang chay (set_current_job() da
    goi truoc do trong cung ngu canh). Khong co job dang chay (vd. goi
    call_structured() tu 1 script test doc lap) -> bo qua, khong loi."""
    job_id = _current_job_id.get()
    if job_id is None:
        return
    with _lock:
        bucket = _usage_by_job.setdefault(job_id, {})
        per_model = bucket.setdefault(model, {"prompt_tokens": 0, "output_tokens": 0, "calls": 0})
        per_model["prompt_tokens"] += prompt_tokens
        per_model["output_tokens"] += output_tokens
        per_model["calls"] += 1


def get_totals(job_id: str) -> dict:
    """Tong hop token da dung cho 1 job (goi 1 lan luc job vua xong, truoc
    khi clear_job()). Job khong co lan goi Gemini nao (vd. Alpha/Beta deu
    tat) tra ve tong = 0, khong phai loi."""
    with _lock:
        per_model = _usage_by_job.get(job_id, {})
        return {
            "by_model": {k: dict(v) for k, v in per_model.items()},
            "total_prompt_tokens": sum(v["prompt_tokens"] for v in per_model.values()),
            "total_output_tokens": sum(v["output_tokens"] for v in per_model.values()),
            "total_calls": sum(v["calls"] for v in per_model.values()),
        }


def clear_job(job_id: str) -> None:
    """Xoa bo dem cua 1 job khoi bo nho sau khi da doc get_totals() - khong
    lam vay se ro ri bo nho dan qua nhieu job (tich luy vinh vien trong _usage_by_job,
    khac voi JOBS/_jobs da co gioi han vong doi rieng)."""
    with _lock:
        _usage_by_job.pop(job_id, None)
