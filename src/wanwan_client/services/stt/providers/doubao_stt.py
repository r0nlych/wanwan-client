"""
Doubao STT providers.

- standard async provider: submit/query
- flash sync provider: single request / immediate result
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from src.wanwan_client.infrastructure.http.http_client import ProviderHttpClient
from src.wanwan_client.services.stt.providers.base import (
    STT_MODE_ASYNC_BASE64,
    STT_MODE_ASYNC_URL,
    STT_MODE_SYNC_BASE64,
    STT_MODE_SYNC_URL,
    SttProvider,
    SttProviderError,
    SttProviderRequest,
    SttProviderResult,
    SttSegment,
    SttUtterance,
    get_base64_audio_data,
    get_remote_audio_url,
    resolve_request_mode,
)


class _DoubaoSttProviderMixin:
    _SUCCESS_CODE = "20000000"
    _RUNNING_CODES = {"20000001", "20000002"}

    def _build_auth_headers(
        self,
        *,
        request: SttProviderRequest,
        client: ProviderHttpClient,
    ) -> dict[str, str]:
        auth_mode = str(request.provider_config.extra.get("auth_mode", "x_api_key")).strip()
        api_key = client.resolve_api_key()
        if not api_key:
            raise SttProviderError(
                "Missing STT API key or access token.",
                code="STT_VALIDATION_ERROR",
                error_type="validation_error",
                retryable=False,
            )

        resource_id = self._read_required_text(
            request.provider_config.extra.get("resource_id"),
            field_name="resource_id",
        )
        headers = {
            "X-Api-Resource-Id": resource_id,
        }

        if auth_mode == "x_api_key":
            headers["X-Api-Key"] = api_key
            return headers

        if auth_mode == "legacy_app_access":
            app_id = self._read_required_text(
                request.provider_config.extra.get("app_id"),
                field_name="app_id",
            )
            headers["X-Api-App-Key"] = app_id
            headers["X-Api-Access-Key"] = api_key
            return headers

        raise SttProviderError(
            f"Unsupported Doubao auth_mode: {auth_mode}",
            code="STT_VALIDATION_ERROR",
            error_type="validation_error",
            retryable=False,
        )

    def _resolve_user_uid(
        self,
        *,
        request: SttProviderRequest,
        client: ProviderHttpClient,
    ) -> str:
        auth_mode = str(request.provider_config.extra.get("auth_mode", "x_api_key")).strip()
        if auth_mode == "legacy_app_access":
            return self._read_required_text(
                request.provider_config.extra.get("app_id"),
                field_name="app_id",
            )
        if auth_mode == "x_api_key":
            return client.resolve_api_key()
        return request.session_id or request.trace_id

    def _build_audio_payload(
        self,
        *,
        request: SttProviderRequest,
        request_mode: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if request_mode.endswith("_url"):
            payload["url"] = get_remote_audio_url(request.audio_ref)
        elif request_mode.endswith("_base64"):
            payload["data"] = get_base64_audio_data(request.audio_ref)
        else:
            raise SttProviderError(
                f"Unsupported Doubao STT request_mode: {request_mode}",
                code="STT_MODE_UNSUPPORTED",
                error_type="validation_error",
                retryable=False,
            )

        if request.audio_format and not str(request.audio_format).startswith("("):
            payload["format"] = request.audio_format
        return payload

    def _build_common_request_payload(
        self,
        *,
        request: SttProviderRequest,
        request_mode: str,
        client: ProviderHttpClient,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user": {
                "uid": self._resolve_user_uid(request=request, client=client),
            },
            "audio": self._build_audio_payload(
                request=request,
                request_mode=request_mode,
            ),
            "request": {
                "model_name": request.model_config.model_id,
            },
        }

        if request.language_hint and not str(request.language_hint).startswith("("):
            payload["request"]["language"] = request.language_hint
        if request.prompt and not str(request.prompt).startswith("("):
            payload["request"]["prompt"] = request.prompt
        if request.response_format and not str(request.response_format).startswith("("):
            payload["request"]["result_type"] = request.response_format
        return payload

    def _raise_for_http_error(self, error: Exception, *, stage: str) -> None:
        import requests

        if not isinstance(error, requests.HTTPError) or error.response is None:
            raise error

        response = error.response
        provider_code = response.headers.get("X-Api-Status-Code", "")
        provider_message = response.headers.get("X-Api-Message", "") or str(error)
        raise self._build_provider_error(
            code=provider_code,
            message=provider_message,
            details={
                "stage": stage,
                "status_code": response.status_code,
                "request_id": response.headers.get("X-Api-Request-Id"),
                "logid": response.headers.get("X-Tt-Logid"),
            },
        ) from error

    def _normalize_result(
        self,
        *,
        request: SttProviderRequest,
        request_mode: str,
        provider_job_id: str | None,
        request_id: str | None,
        response_json: dict[str, Any],
    ) -> SttProviderResult:
        result = response_json.get("result")
        # result 对象本身缺失/类型错误才是协议结构问题；
        # result 存在但 text 为空属于“没有识别到语音”，语义必须与结构错误区分
        if not isinstance(result, dict):
            raise SttProviderError(
                "Doubao STT response missing result object.",
                code="STT_SCHEMA_MISMATCH",
                error_type="schema_mismatch",
                retryable=False,
            )

        text = str(result.get("text", "")).strip()
        if not text:
            raise SttProviderError(
                "Doubao STT returned no recognized text; no speech detected.",
                code="STT_NO_SPEECH",
                error_type="no_speech",
                retryable=False,
            )

        utterances: list[SttUtterance] = []
        segments: list[SttSegment] = []
        for utterance_item in result.get("utterances", []) or []:
            if not isinstance(utterance_item, dict):
                continue
            utterances.append(
                SttUtterance(
                    text=str(utterance_item.get("text", "")).strip(),
                    start_ms=self._optional_int(
                        utterance_item.get("start_time", utterance_item.get("start_time_ms"))
                    ),
                    end_ms=self._optional_int(
                        utterance_item.get("end_time", utterance_item.get("end_time_ms"))
                    ),
                    speaker=self._optional_str(utterance_item.get("speaker")),
                    confidence=self._optional_float(utterance_item.get("confidence")),
                    raw=utterance_item,
                )
            )
            for word_item in utterance_item.get("words", []) or []:
                if not isinstance(word_item, dict):
                    continue
                segments.append(
                    SttSegment(
                        text=str(word_item.get("text", "")).strip(),
                        start_ms=self._optional_int(
                            word_item.get("start_time", word_item.get("start_time_ms"))
                        ),
                        end_ms=self._optional_int(
                            word_item.get("end_time", word_item.get("end_time_ms"))
                        ),
                        speaker=self._optional_str(word_item.get("speaker")),
                        confidence=self._optional_float(word_item.get("confidence")),
                        raw=word_item,
                    )
                )

        audio_info = response_json.get("audio_info", {})
        return SttProviderResult(
            text=text,
            is_final=True,
            utterances=utterances,
            segments=segments,
            request_id=request_id,
            provider_job_id=provider_job_id,
            meta={
                "provider_status": "success",
                "provider_audio_duration_ms": self._optional_int(audio_info.get("duration")),
                "provider_request_mode": request_mode,
            },
        )

    def _build_provider_error(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> SttProviderError:
        retryable = code in self._RUNNING_CODES or str(code).startswith("55")
        error_type = "provider_error"
        if code == "55000031":
            error_type = "provider_unavailable"
        elif str(code).startswith("45"):
            error_type = "validation_error"
        return SttProviderError(
            message,
            code=f"STT_PROVIDER_{code or 'UNKNOWN'}",
            error_type=error_type,
            retryable=retryable,
            details=details,
        )

    def _read_required_text(self, raw_value: Any, *, field_name: str) -> str:
        value = str(raw_value or "").strip()
        if not value or value.startswith("("):
            raise SttProviderError(
                f"Missing required Doubao STT config field: {field_name}",
                code="STT_VALIDATION_ERROR",
                error_type="validation_error",
                retryable=False,
                details={"field": field_name},
            )
        return value

    def _read_number(self, raw_value: Any, *, default: int | float, field_name: str) -> int | float:
        if raw_value is None:
            return default
        if isinstance(raw_value, (int, float)):
            return raw_value

        text = str(raw_value).strip()
        if not text or text.startswith("("):
            return default
        try:
            return float(text) if "." in text else int(text)
        except ValueError as error:
            raise SttProviderError(
                f"Invalid Doubao STT config field: {field_name}",
                code="STT_VALIDATION_ERROR",
                error_type="validation_error",
                retryable=False,
                details={"field": field_name, "value": raw_value},
            ) from error

    def _to_json_bytes(self, payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _optional_int(self, raw_value: Any) -> int | None:
        if raw_value is None:
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    def _optional_float(self, raw_value: Any) -> float | None:
        if raw_value is None:
            return None
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    def _optional_str(self, raw_value: Any) -> str | None:
        if raw_value is None:
            return None
        value = str(raw_value).strip()
        return value or None


class DoubaoAsyncSttProvider(_DoubaoSttProviderMixin, SttProvider):
    ADAPTER_VERSION = "phase6.stt.doubao_async.v2"
    SUPPORTED_REQUEST_MODES = (
        STT_MODE_ASYNC_URL,
        STT_MODE_ASYNC_BASE64,
    )

    def transcribe(self, request: SttProviderRequest) -> SttProviderResult:
        request_mode = resolve_request_mode(
            audio_ref=request.audio_ref,
            preferred_mode=request.request_mode,
            supported_modes=self.SUPPORTED_REQUEST_MODES,
        )
        client = ProviderHttpClient(request.provider_config)
        task_id = str(uuid.uuid4())

        submit_headers = self._build_auth_headers(request=request, client=client)
        submit_headers["Content-Type"] = "application/json"
        submit_headers["X-Api-Request-Id"] = task_id
        submit_headers["X-Api-Sequence"] = "-1"

        submit_body = self._build_common_request_payload(
            request=request,
            request_mode=request_mode,
            client=client,
        )
        try:
            submit_response = client.request(
                method="POST",
                headers=submit_headers,
                json_body=submit_body,
            )
        except Exception as error:
            self._raise_for_http_error(error, stage="submit")
            raise
        submit_code = submit_response.headers.get("X-Api-Status-Code", "")
        if submit_code != self._SUCCESS_CODE:
            raise self._build_provider_error(
                code=submit_code,
                message=submit_response.headers.get("X-Api-Message", "Doubao submit failed"),
                details={
                    "stage": "submit",
                    "task_id": task_id,
                    "request_mode": request_mode,
                },
            )

        x_tt_logid = submit_response.headers.get("X-Tt-Logid")
        result_body = self._poll_query_until_done(
            request=request,
            client=client,
            task_id=task_id,
            x_tt_logid=x_tt_logid,
        )
        return self._normalize_result(
            request=request,
            request_mode=request_mode,
            provider_job_id=task_id,
            request_id=x_tt_logid,
            response_json=result_body,
        )

    def _poll_query_until_done(
        self,
        *,
        request: SttProviderRequest,
        client: ProviderHttpClient,
        task_id: str,
        x_tt_logid: str | None,
    ) -> dict[str, Any]:
        poll_interval_ms = self._read_number(
            request.provider_config.extra.get("query_interval_ms"),
            default=5000,
            field_name="query_interval_ms",
        )
        poll_timeout_seconds = self._read_number(
            request.provider_config.extra.get("query_timeout_seconds"),
            default=120,
            field_name="query_timeout_seconds",
        )
        deadline = time.monotonic() + float(poll_timeout_seconds)
        query_path = self._read_required_text(
            request.provider_config.extra.get("query_path"),
            field_name="query_path",
        )

        while time.monotonic() < deadline:
            query_headers = self._build_auth_headers(request=request, client=client)
            query_headers["Content-Type"] = "application/json"
            query_headers["X-Api-Request-Id"] = task_id
            if x_tt_logid:
                query_headers["X-Tt-Logid"] = x_tt_logid

            try:
                query_response = client.request(
                    method="POST",
                    api_path=query_path,
                    headers=query_headers,
                    json_body={},
                )
            except Exception as error:
                self._raise_for_http_error(error, stage="query")
                raise
            query_code = query_response.headers.get("X-Api-Status-Code", "")
            if query_code == self._SUCCESS_CODE:
                return query_response.json()
            if query_code in self._RUNNING_CODES:
                time.sleep(float(poll_interval_ms) / 1000.0)
                continue

            raise self._build_provider_error(
                code=query_code,
                message=query_response.headers.get("X-Api-Message", "Doubao query failed"),
                details={
                    "stage": "query",
                    "task_id": task_id,
                },
            )

        raise SttProviderError(
            "Doubao STT query polling timed out.",
            code="STT_TIMEOUT",
            error_type="provider_timeout",
            retryable=True,
            details={
                "stage": "query",
                "task_id": task_id,
                "query_timeout_seconds": poll_timeout_seconds,
            },
        )


class DoubaoFlashSttProvider(_DoubaoSttProviderMixin, SttProvider):
    ADAPTER_VERSION = "phase6.stt.doubao_flash.v1"
    SUPPORTED_REQUEST_MODES = (
        STT_MODE_SYNC_URL,
        STT_MODE_SYNC_BASE64,
    )

    def transcribe(self, request: SttProviderRequest) -> SttProviderResult:
        request_mode = resolve_request_mode(
            audio_ref=request.audio_ref,
            preferred_mode=request.request_mode,
            supported_modes=self.SUPPORTED_REQUEST_MODES,
        )
        client = ProviderHttpClient(request.provider_config)
        request_id = str(uuid.uuid4())

        headers = self._build_auth_headers(request=request, client=client)
        headers["Content-Type"] = "application/json"
        headers["X-Api-Request-Id"] = request_id
        headers["X-Api-Sequence"] = "-1"

        body = self._build_common_request_payload(
            request=request,
            request_mode=request_mode,
            client=client,
        )
        try:
            response = client.request(
                method="POST",
                headers=headers,
                json_body=body,
            )
        except Exception as error:
            self._raise_for_http_error(error, stage="recognize")
            raise
        response_json = response.json()
        return self._normalize_result(
            request=request,
            request_mode=request_mode,
            provider_job_id=None,
            request_id=response.headers.get("X-Tt-Logid") or request_id,
            response_json=response_json,
        )
