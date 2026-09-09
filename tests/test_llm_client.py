"""voxdirector.llm_client — test retry-with-backoff logic bang mock, KHONG
goi Gemini API that. Xac nhan hanh vi them vao sau khi test Agent Alpha that
gap 503 UNAVAILABLE ngau nhien tren gemini-3.6-flash (2026-09-08)."""
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors
from pydantic import BaseModel

from voxdirector.llm_client import call_structured


class _Dummy(BaseModel):
    value: str


def _server_error(code=503):
    return errors.ServerError(code, {"error": {"message": "high demand", "status": "UNAVAILABLE"}})


def _client_error(code=429):
    return errors.ClientError(code, {"error": {"message": "quota exhausted", "status": "RESOURCE_EXHAUSTED"}})


def test_succeeds_first_try_no_retry_needed():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.parsed = _Dummy(value="ok")
    mock_client.models.generate_content.return_value = mock_response

    with patch("voxdirector.llm_client._get_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        result = call_structured("sys", "user", _Dummy)

    assert result.value == "ok"
    mock_client.models.generate_content.assert_called_once()
    mock_sleep.assert_not_called()


def test_retries_on_server_error_then_succeeds():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.parsed = _Dummy(value="ok-after-retry")
    # 2 lan dau bao 503, lan 3 thanh cong.
    mock_client.models.generate_content.side_effect = [
        _server_error(), _server_error(), mock_response,
    ]

    with patch("voxdirector.llm_client._get_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        result = call_structured("sys", "user", _Dummy)

    assert result.value == "ok-after-retry"
    assert mock_client.models.generate_content.call_count == 3
    assert mock_sleep.call_count == 2  # backoff truoc lan thu 2 va lan thu 3


def test_raises_after_exhausting_all_retries_on_server_error():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = _server_error()

    with patch("voxdirector.llm_client._get_client", return_value=mock_client), \
         patch("time.sleep"):
        with pytest.raises(errors.ServerError):
            call_structured("sys", "user", _Dummy)

    assert mock_client.models.generate_content.call_count == 3  # _MAX_RETRIES


def test_client_error_is_not_retried():
    """Loi 4xx (vd. het quota/billing, sai model) KHONG duoc retry - retry
    khong giai quyet duoc van de va chi ton them quota."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = _client_error()

    with patch("voxdirector.llm_client._get_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(errors.ClientError):
            call_structured("sys", "user", _Dummy)

    mock_client.models.generate_content.assert_called_once()
    mock_sleep.assert_not_called()
