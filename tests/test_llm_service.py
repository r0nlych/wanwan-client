"""
验证 LlmService._normalize_error 对 requests.HTTPError 的归类：

- 401 / 403 必须映射为 LLM_AUTH_ERROR / authentication_error / retryable=False；
- 其他 HTTP 状态码保持 LLM_PROVIDER_ERROR / provider_error / retryable=False；
- details 只保留 status_code，不解析第三方响应正文，不携带请求头与凭据。

全部用例完全离线：只构造 requests.Response / requests.HTTPError，不访问网络、不读取真实配置、
不调用任何真实 Provider。
"""

from __future__ import annotations

import json
import unittest

import requests

from src.wanwan_client.services.llm.service import LlmService

# 故意塞进响应头与响应正文的假凭据哨兵，用来验证它们不会被带进内部错误结构。
# 刻意不使用任何真实密钥的前缀特征，避免被仓库密钥扫描器误报。
FAKE_CREDENTIAL = "fake-credential-sentinel-0001"
FAKE_AUTH_HEADER = f"Bearer {FAKE_CREDENTIAL}"
FAKE_BODY_MARKER = "fake-response-body-marker"
FAKE_URL = "https://example.invalid/v1/chat/completions"

# 内部协议外层错误结构的固定字段，所有分支必须保持一致。
EXPECTED_ERROR_KEYS = {"code", "message", "type", "retryable", "details", "raw_ref"}


def _make_http_error(status_code: int) -> requests.HTTPError:
    """构造一个携带响应头、响应正文和 URL 的 HTTPError，模拟真实第三方失败。"""
    response = requests.Response()
    response.status_code = status_code
    response.url = FAKE_URL
    response.reason = "Unauthorized" if status_code in (401, 403) else "Server Error"
    # 伪造请求头（含 Authorization）与响应正文，验证实现不会把它们带出去
    response.headers["Authorization"] = FAKE_AUTH_HEADER
    response.headers["Content-Type"] = "application/json"
    response.request = requests.Request(
        method="POST",
        url=FAKE_URL,
        headers={"Authorization": FAKE_AUTH_HEADER},
    ).prepare()
    response._content = (
        '{"error": {"message": "' + FAKE_BODY_MARKER + '", "token": "' + FAKE_AUTH_HEADER + '"}}'
    ).encode("utf-8")

    # 错误消息本身也刻意带上 URL，用来确认 URL 不会泄漏到 details
    return requests.HTTPError(f"{status_code} Error for url: {FAKE_URL}", response=response)


def _make_service() -> LlmService:
    """不注入 RuntimeConfig / Provider，只验证纯错误归类逻辑。"""
    return LlmService(runtime_config=None)


class LlmServiceNormalizeErrorTest(unittest.TestCase):
    def test_401_maps_to_auth_error(self) -> None:
        result = _make_service()._normalize_error(_make_http_error(401))
        self.assertEqual(result["code"], "LLM_AUTH_ERROR")

    def test_403_maps_to_auth_error(self) -> None:
        result = _make_service()._normalize_error(_make_http_error(403))
        self.assertEqual(result["code"], "LLM_AUTH_ERROR")

    def test_auth_error_type_is_authentication_error(self) -> None:
        for status_code in (401, 403):
            with self.subTest(status_code=status_code):
                result = _make_service()._normalize_error(_make_http_error(status_code))
                self.assertEqual(result["type"], "authentication_error")

    def test_auth_error_is_not_retryable(self) -> None:
        for status_code in (401, 403):
            with self.subTest(status_code=status_code):
                result = _make_service()._normalize_error(_make_http_error(status_code))
                self.assertFalse(result["retryable"])

    def test_500_maps_to_provider_error(self) -> None:
        result = _make_service()._normalize_error(_make_http_error(500))
        self.assertEqual(result["code"], "LLM_PROVIDER_ERROR")

    def test_500_type_is_provider_error(self) -> None:
        result = _make_service()._normalize_error(_make_http_error(500))
        self.assertEqual(result["type"], "provider_error")
        self.assertFalse(result["retryable"])

    def test_details_only_contains_status_code(self) -> None:
        for status_code in (401, 403, 500):
            with self.subTest(status_code=status_code):
                result = _make_service()._normalize_error(_make_http_error(status_code))
                self.assertEqual(result["details"], {"status_code": status_code})
                self.assertIsNone(result["raw_ref"])
                self.assertEqual(set(result.keys()), EXPECTED_ERROR_KEYS)

    def test_result_does_not_leak_credentials_or_headers(self) -> None:
        for status_code in (401, 403, 500):
            with self.subTest(status_code=status_code):
                result = _make_service()._normalize_error(_make_http_error(status_code))
                serialized = json.dumps(result, ensure_ascii=False)

                # 请求头、凭据、响应正文内容都不允许出现在返回结构里
                self.assertNotIn(FAKE_CREDENTIAL, serialized)
                self.assertNotIn("Bearer", serialized)
                self.assertNotIn("Authorization", serialized)
                self.assertNotIn(FAKE_BODY_MARKER, serialized)

                # details 里除了 status_code 之外不应有任何请求头类字段
                self.assertEqual(set(result["details"].keys()), {"status_code"})


if __name__ == "__main__":
    unittest.main()