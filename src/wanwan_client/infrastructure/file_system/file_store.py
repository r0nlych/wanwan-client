import os
from typing import Optional


class FileStore:
    """统一文件操作类，负责音频文件保存和目录管理。"""

    @staticmethod
    def ensure_dirs_exist():
        """确保所有必要目录存在。"""
        dirs = [
            os.path.join("data", "temp"),
            os.path.join("data", "tts"),
            os.path.join("data", "rvc"),
        ]

        for directory in dirs:
            os.makedirs(directory, exist_ok=True)

    @staticmethod
    def save_recording(file_obj, trace_id: str) -> str:
        """
        保存录音文件。

        Args:
            file_obj: 提供 ``save(path)`` 方法的文件对象。
            trace_id: 追踪 ID，用于生成文件名。

        Returns:
            保存后的文件路径。
        """
        FileStore.ensure_dirs_exist()

        filename = f"{trace_id}.webm"
        file_path = os.path.join("data", "temp", filename)

        file_obj.save(file_path)

        return file_path

    @staticmethod
    def find_audio_file(trace_id: str, file_type: str = "wav") -> Optional[str]:
        """
        查找音频文件。

        Args:
            trace_id: 追踪 ID。
            file_type: 文件类型，如 wav、webm。

        Returns:
            文件路径；如果不存在则返回 None。
        """
        possible_dirs = [
            os.path.join("data", "rvc"),
            os.path.join("data", "tts"),
            os.path.join("data", "temp"),
        ]

        for directory in possible_dirs:
            file_path = os.path.join(directory, f"{trace_id}.{file_type}")
            if os.path.exists(file_path):
                return file_path

        return None
