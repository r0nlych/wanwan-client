"""把 LLM 文本增量合并成适合调用 TTS 的句子段。"""

from __future__ import annotations


class TextSegmenter:
    """按中文结束标点或长度阈值输出文本段，避免逐 token 调用 TTS。"""

    DEFAULT_BOUNDARIES = frozenset("。！？；!?;")

    def __init__(self, max_length: int = 80, boundaries: set[str] | None = None) -> None:
        if max_length <= 0:
            raise ValueError("max_length must be greater than zero")
        self.max_length = max_length
        self.boundaries = frozenset(boundaries or self.DEFAULT_BOUNDARIES)
        self._buffer = ""

    def feed(self, text_chunk: str) -> list[str]:
        """接收一个文本增量，返回本次形成的完整 TTS 文本段。"""
        if not text_chunk:
            return []
        self._buffer += text_chunk
        segments: list[str] = []

        while self._buffer:
            if len(self._buffer) >= self.max_length:
                # 已达到长度上限：max_length 是硬上限，任何输出段都不能超过它。
                # 先只在上限范围内寻找结束标点：阈值内有标点则优先按标点切，
                # 阈值之外的标点本轮不考虑，严格按 max_length 切。
                boundary_index = self._find_boundary(self._buffer[: self.max_length])
                take_length = (
                    boundary_index + 1 if boundary_index is not None else self.max_length
                )
            else:
                # 尚未达到上限：只有缓冲区内出现结束标点才成段，
                # 否则继续等待后续文本增量，避免在句子中间硬切。
                boundary_index = self._find_boundary(self._buffer)
                if boundary_index is None:
                    break
                take_length = boundary_index + 1

            segment = self._take(take_length)
            if segment:
                segments.append(segment)

        return segments

    def flush(self) -> list[str]:
        """流结束时输出尚未达到分段条件的剩余文本。"""
        segment = self._buffer.strip()
        self._buffer = ""
        return [segment] if segment else []

    def reset(self) -> None:
        """取消当前流时丢弃尚未输出的缓存。"""
        self._buffer = ""

    def _find_boundary(self, text: str) -> int | None:
        for index, character in enumerate(text):
            if character in self.boundaries:
                return index
        return None

    def _take(self, length: int) -> str:
        segment = self._buffer[:length].strip()
        self._buffer = self._buffer[length:]
        return segment
