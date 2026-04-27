"""
Doubao TTS V3 one-way streaming adapter.
"""

from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path
from typing import Any

import requests

from src.wanwan_client.infrastructure.http.http_client import ProviderHttpClient
from src.wanwan_client.services.tts.providers.base import (
    TtsProviderError,
    TtsProviderRequest,
    TtsProviderResult,
)


class DoubaoTtsProvider:
    ADAPTER_VERSION = "phase6.tts.doubao_v3.v1"

    def synthesize_to_file(self, request: TtsProviderRequest) -> TtsProviderResult:
        provider_config = request.provider_config
        model_config = request.model_config
        text = request.text.strip()
        if not text:
            raise ValueError("TTS text is empty")

        transport = ProviderHttpClient(provider_config)
        api_key = transport.resolve_api_key()
        if not api_key:
            raise ValueError(f"Missing API key for provider: {provider_config.provider_id}")

        voice_type = self._resolve_voice_type(provider_config=provider_config, model_config=model_config)
        response_format = self._resolve_string(
            model_config.extra.get("response_format"),
            provider_config.extra.get("response_format"),
            default="wav",
        )
        sample_rate = self._resolve_int(
            model_config.extra.get("sample_rate"),
            provider_config.extra.get("sample_rate"),
            default=24000,
        )
        speed = self._resolve_float(
            model_config.extra.get("speed"),
            provider_config.extra.get("speed"),
            default=1.0,
        )
        volume = self._resolve_float(
            model_config.extra.get("volume"),
            provider_config.extra.get("volume"),
            default=1.0,
        )
        language = self._resolve_optional_string(
            model_config.extra.get("language"),
            provider_config.extra.get("language"),
        )
        emotion = self._resolve_optional_string(
            model_config.extra.get("emotion"),
            provider_config.extra.get("emotion"),
        )

        payload = self._build_payload(
            request=request,
            voice_type=voice_type,
            response_format=response_format,
            sample_rate=sample_rate,
            speed=speed,
            volume=volume,
            language=language,
            emotion=emotion,
        )
        headers = self._build_headers(request=request, api_key=api_key)
        response = requests.post(
            transport.build_url(),
            json=payload,
            headers=headers,
            timeout=self._resolve_timeout_seconds(provider_config.timeout_seconds),
            stream=True,
        )
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"{response.status_code} Client Error: {response.reason} for url: {response.url}",
                response=response,
            )

        audio_bytes, event_meta = self._collect_audio_bytes(response)
        if not audio_bytes:
            raise TtsProviderError(
                code="TTS_EMPTY_AUDIO",
                message="Doubao TTS returned no audio bytes",
                error_type="provider_error",
                retryable=False,
                details=event_meta,
            )

        output_path = self._normalize_output_path(request.output_path, response_format)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        return TtsProviderResult(
            audio_ref={
                "type": "local_path",
                "value": str(output_path).replace("\\", "/"),
                "mime_type": self._guess_mime_type(response_format),
            },
            voice=voice_type,
            voice_type=voice_type,
            response_format=response_format,
            request_id=event_meta.get("request_id"),
            logid=event_meta.get("logid"),
            byte_size=output_path.stat().st_size,
            duration_ms=self._safe_int(event_meta.get("audio_duration_ms")),
            raw_details=event_meta,
        )

    def _build_payload(
        self,
        *,
        request: TtsProviderRequest,
        voice_type: str,
        response_format: str,
        sample_rate: int,
        speed: float,
        volume: float,
        language: str | None,
        emotion: str | None,
    ) -> dict[str, Any]:
        uid = self._resolve_optional_string(
            request.options.get("uid"),
            request.session_id,
            request.trace_id,
            "wanwan-client",
        )
        audio_params: dict[str, Any] = {
            "format": self._normalize_encoding(response_format),
            "sample_rate": sample_rate,
        }
        if emotion:
            audio_params["emotion"] = emotion
        if speed != 1.0:
            audio_params["speech_rate"] = self._to_rate_value(speed)
        if volume != 1.0:
            audio_params["loudness_rate"] = self._to_rate_value(volume)

        model_name = self._resolve_optional_string(
            request.model_config.extra.get("model"),
            request.provider_config.extra.get("model"),
        )
        req_params: dict[str, Any] = {
            "text": request.text,
            "speaker": voice_type,
            "audio_params": audio_params,
        }
        additions: dict[str, Any] = {}
        if language:
            additions["explicit_language"] = self._normalize_language(language)
        if additions:
            req_params["additions"] = json.dumps(additions, ensure_ascii=False)
        if model_name:
            req_params["model"] = model_name

        return {
            "user": {
                "uid": uid,
            },
            "req_params": req_params,
        }

    def _build_headers(self, *, request: TtsProviderRequest, api_key: str) -> dict[str, str]:
        provider_config = request.provider_config
        auth_mode = self._resolve_string(provider_config.extra.get("auth_mode"), default="x_api_key")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        resource_id = self._resolve_optional_string(provider_config.extra.get("resource_id"))
        if resource_id:
            headers["X-Api-Resource-Id"] = resource_id

        request_id = str(request.options.get("request_id") or request.trace_id or uuid.uuid4())
        headers["X-Api-Request-Id"] = request_id

        if auth_mode == "x_api_key":
            headers["X-Api-Key"] = api_key
            return headers

        if auth_mode == "legacy_app_access":
            app_id = self._resolve_optional_string(provider_config.extra.get("app_id"))
            if not app_id:
                raise ValueError(
                    f"Missing TTS app_id for provider using legacy_app_access: {provider_config.provider_id}"
                )
            headers["X-Api-App-Id"] = app_id
            headers["X-Api-Access-Key"] = api_key
            return headers

        if auth_mode == "bearer_token":
            headers["Authorization"] = f"Bearer {api_key}"
            app_id = self._resolve_optional_string(provider_config.extra.get("app_id"))
            if app_id:
                headers["X-Api-App-Id"] = app_id
            return headers

        raise ValueError(f"Unsupported TTS auth_mode: {auth_mode}")

    def _collect_audio_bytes(self, response: requests.Response) -> tuple[bytes, dict[str, Any]]:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/event-stream" not in content_type:
            return self._collect_non_sse_audio(response)

        audio_chunks: list[bytes] = []
        pending_data: list[str] = []
        latest_meta: dict[str, Any] = {
            "request_id": response.headers.get("X-Api-Request-Id"),
            "logid": response.headers.get("X-Tt-Logid"),
        }

        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line.strip()
            if not line:
                self._flush_event_data(pending_data, audio_chunks, latest_meta)
                pending_data = []
                continue
            if line.startswith("data:"):
                pending_data.append(line[5:].strip())
                continue

        self._flush_event_data(pending_data, audio_chunks, latest_meta)
        return b"".join(audio_chunks), latest_meta

    def _collect_non_sse_audio(self, response: requests.Response) -> tuple[bytes, dict[str, Any]]:
        if response.content:
            return response.content, {
                "request_id": response.headers.get("X-Api-Request-Id"),
                "logid": response.headers.get("X-Tt-Logid"),
            }

        try:
            body = response.json()
        except ValueError as error:
            raise TtsProviderError(
                code="TTS_INVALID_RESPONSE",
                message="Doubao TTS returned neither audio bytes nor JSON body",
                error_type="provider_error",
                retryable=False,
                details={},
            ) from error

        raise self._build_provider_error(body, response=response)

    def _flush_event_data(
        self,
        pending_data: list[str],
        audio_chunks: list[bytes],
        latest_meta: dict[str, Any],
    ) -> None:
        if not pending_data:
            return
        joined = "\n".join(pending_data).strip()
        if not joined:
            return
        if joined == "[DONE]":
            return
        try:
            payload = json.loads(joined)
        except json.JSONDecodeError:
            latest_meta["raw_event"] = joined
            return

        if not isinstance(payload, dict):
            latest_meta["raw_event"] = payload
            return

        latest_meta.update(
            {
                "request_id": payload.get("reqid") or latest_meta.get("request_id"),
                "logid": payload.get("logid") or latest_meta.get("logid"),
            }
        )
        code = self._safe_int(payload.get("code"))
        if code not in (None, 0, 3000, 20000000):
            raise self._build_provider_error(payload)

        data = payload.get("data")
        if isinstance(data, str) and data:
            try:
                audio_chunks.append(base64.b64decode(data))
            except (ValueError, TypeError) as error:
                raise TtsProviderError(
                    code="TTS_INVALID_AUDIO_CHUNK",
                    message="Failed to decode TTS audio chunk",
                    error_type="provider_error",
                    retryable=False,
                    details={"event": payload},
                ) from error

        additions = payload.get("addition") or payload.get("additions") or {}
        if isinstance(additions, dict):
            latest_meta["audio_duration_ms"] = additions.get("duration") or latest_meta.get("audio_duration_ms")
        status_code = self._safe_int(payload.get("status_code"))
        if status_code == 20000000:
            latest_meta["provider_status_code"] = status_code
            latest_meta["provider_message"] = payload.get("message")

    def _build_provider_error(
        self,
        payload: dict[str, Any],
        *,
        response: requests.Response | None = None,
    ) -> TtsProviderError:
        code = self._safe_int(payload.get("code")) or self._safe_int(payload.get("status_code")) or -1
        message = str(payload.get("message") or payload.get("msg") or "Doubao TTS provider error")
        details = {
            "provider_code": code,
            "request_id": payload.get("reqid") or (response.headers.get("X-Api-Request-Id") if response else None),
            "logid": payload.get("logid") or (response.headers.get("X-Tt-Logid") if response else None),
            "payload": payload,
        }
        return TtsProviderError(
            code=f"TTS_PROVIDER_{code}" if code >= 0 else "TTS_PROVIDER_ERROR",
            message=message,
            error_type="provider_error",
            retryable=False,
            details=details,
        )

    def _resolve_voice_type(self, *, provider_config: Any, model_config: Any) -> str:
        value = self._resolve_optional_string(
            model_config.extra.get("voice_type"),
            provider_config.extra.get("voice_type"),
            model_config.extra.get("voice"),
            provider_config.extra.get("voice"),
        )
        if not value:
            raise ValueError(f"Missing voice_type/voice for provider: {provider_config.provider_id}")
        return value

    def _normalize_output_path(self, output_path: Path, response_format: str) -> Path:
        extension = response_format.lower().strip() or "wav"
        suffix = f".{extension}"
        if output_path.suffix.lower() == suffix:
            return output_path
        return output_path.with_suffix(suffix)

    def _resolve_timeout_seconds(self, raw_timeout: Any) -> float:
        try:
            return float(raw_timeout)
        except (TypeError, ValueError):
            raise ValueError("Invalid TTS timeout_seconds") from None

    def _resolve_string(self, *values: Any, default: str | None = None) -> str:
        resolved = self._resolve_optional_string(*values)
        if resolved is None:
            if default is None:
                raise ValueError("Missing required TTS string value")
            return default
        return resolved

    def _resolve_optional_string(self, *values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.startswith("("):
                continue
            return text
        return None

    def _resolve_int(self, *values: Any, default: int) -> int:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.startswith("("):
                continue
            try:
                return int(float(text))
            except ValueError:
                continue
        return default

    def _resolve_float(self, *values: Any, default: float) -> float:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.startswith("("):
                continue
            try:
                return float(text)
            except ValueError:
                continue
        return default

    def _to_rate_value(self, scale: float) -> int:
        normalized = int(round((scale - 1.0) * 100))
        return max(-50, min(100, normalized))

    def _resolve_optional_int(self, *values: Any) -> int | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.startswith("("):
                continue
            try:
                return int(text)
            except ValueError:
                continue
        return None

    def _safe_int(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _guess_mime_type(self, response_format: str) -> str:
        mapping = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "ogg_opus": "audio/ogg",
            "opus": "audio/ogg",
            "pcm": "audio/pcm",
        }
        return mapping.get(response_format.lower(), "application/octet-stream")

    def _normalize_encoding(self, response_format: str) -> str:
        normalized = response_format.lower().strip()
        if normalized == "ogg":
            return "ogg_opus"
        return normalized

    def _normalize_language(self, language: str) -> str:
        normalized = language.strip().lower()
        mapping = {
            "zh": "zh-cn",
        }
        return mapping.get(normalized, normalized)
