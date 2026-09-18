"""会话 JSONL 存储的文本/语音兼容性测试。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.wanwan_client.services.storage.conversation_store import ConversationStore


class FakeHistoryFile:
    """只提供 ConversationStore 所需的 read_text，避免测试依赖磁盘权限。"""

    def __init__(self, records: list[dict[str, object]]) -> None:
        self._content = "\n".join(
            json.dumps(record, ensure_ascii=False) for record in records
        )

    def read_text(self, encoding: str) -> str:
        return self._content


class FakeConversationsDirectory:
    """最小目录替身：声明存在并返回按日期排序后的假 JSONL 文件。"""

    def __init__(self, *files: FakeHistoryFile) -> None:
        self._files = files

    def exists(self) -> bool:
        return True

    def glob(self, pattern: str) -> list[FakeHistoryFile]:
        return list(self._files)


class ConversationStoreRecordTests(unittest.TestCase):

    def test_text_result_keeps_user_text_and_input_type(self) -> None:
        """文本链路应保存用户原文，供桌面历史窗口直接展示。"""
        record = ConversationStore._build_record(
            {
                "trace_id": "trace_text",
                "session_id": "session_text",
                "status": "success",
                "stages": [],
                "final": {
                    "user_text": "你好，晚晚",
                    "reply_text": "你好呀",
                    "audio_ref": {
                        "type": "local_path",
                        "value": "data/tts/text.wav",
                        "mime_type": "audio/wav",
                    },
                },
            }
        )

        self.assertEqual("text", record["input_type"])
        self.assertEqual("你好，晚晚", record["user_text"])
        self.assertEqual("你好呀", record["reply_text"])

    def test_voice_result_uses_stt_text_as_user_text(self) -> None:
        """旧语音结果没有 user_text 时，应使用 STT 文本兼容补齐。"""
        record = ConversationStore._build_record(
            {
                "trace_id": "trace_voice",
                "session_id": "session_voice",
                "status": "success",
                "stages": [],
                "final": {
                    "stt_text": "你能听到吗",
                    "reply_text": "可以听到",
                },
            }
        )

        self.assertEqual("voice", record["input_type"])
        self.assertEqual("你能听到吗", record["user_text"])

    def test_old_text_result_can_read_user_message_from_llm_stage(self) -> None:
        """升级前的文本结果仍可从 LLM payload 恢复用户输入。"""
        record = ConversationStore._build_record(
            {
                "status": "success",
                "stages": [
                    {
                        "step": "llm",
                        "payload": {
                            "input": {
                                "messages": [
                                    {"role": "user", "content": "旧记录输入"}
                                ]
                            }
                        },
                    }
                ],
                "final": {"reply_text": "旧记录回复"},
            }
        )

        self.assertEqual("text", record["input_type"])
        self.assertEqual("旧记录输入", record["user_text"])

    def test_load_session_messages_isolates_session_and_skips_failures(self) -> None:
        """上下文只能包含目标 session 的完整成功轮次。"""
        records = [
            {"session_id": "session_a", "status": "success", "user_text": "第一问", "reply_text": "第一答"},
            {"session_id": "session_b", "status": "success", "user_text": "串线问", "reply_text": "串线答"},
            {"session_id": "session_a", "status": "failed", "user_text": "失败问", "reply_text": "失败答"},
            {"session_id": "session_a", "status": "success", "user_text": "第二问", "reply_text": "第二答"},
        ]

        conversations_dir = FakeConversationsDirectory(FakeHistoryFile(records))
        with patch(
            "src.wanwan_client.services.storage.conversation_store.CONVERSATIONS_DIR",
            conversations_dir,
        ):
            messages = ConversationStore.load_session_messages("session_a")

        self.assertEqual(
            [
                {"role": "user", "content": "第一问"},
                {"role": "assistant", "content": "第一答"},
                {"role": "user", "content": "第二问"},
                {"role": "assistant", "content": "第二答"},
            ],
            messages,
        )

    def test_load_session_messages_respects_turn_and_character_limits(self) -> None:
        """上下文只能取连续的最近完整轮次，且不能超过字符预算。"""
        records = [
            {
                "session_id": "session_limit",
                "status": "success",
                "user_text": f"问{i}",
                "reply_text": f"答{i}",
            }
            for i in range(8)
        ]

        conversations_dir = FakeConversationsDirectory(FakeHistoryFile(records))
        with patch(
            "src.wanwan_client.services.storage.conversation_store.CONVERSATIONS_DIR",
            conversations_dir,
        ):
            messages = ConversationStore.load_session_messages(
                "session_limit",
                max_turns=2,
                max_characters=8,
            )

        self.assertEqual(
            [
                {"role": "user", "content": "问6"},
                {"role": "assistant", "content": "答6"},
                {"role": "user", "content": "问7"},
                {"role": "assistant", "content": "答7"},
            ],
            messages,
        )


if __name__ == "__main__":
    unittest.main()
