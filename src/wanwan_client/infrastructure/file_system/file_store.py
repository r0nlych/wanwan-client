import os
from typing import Optional


class FileStore:
    """统一文件操作类，负责录音文件保存和目录管理"""
    
    @staticmethod
    def ensure_dirs_exist():
        """确保所有必要的目录存在"""
        dirs = [
            os.path.join('data', 'temp'),
            os.path.join('data', 'tts'),
            os.path.join('data', 'rvc')
        ]
        
        for directory in dirs:
            os.makedirs(directory, exist_ok=True)
    
    @staticmethod
    def save_recording(file_obj, trace_id: str) -> str:
        """
        保存录音文件
        
        Args:
            file_obj: 文件对象（如 Flask request.files 中的文件）
            trace_id: 追踪ID，用于文件名
        
        Returns:
            保存的文件路径
        """
        # 确保目录存在
        FileStore.ensure_dirs_exist()
        
        # 生成文件名和路径
        filename = f"{trace_id}.webm"
        file_path = os.path.join('data', 'temp', filename)
        
        # 保存文件
        file_obj.save(file_path)
        
        return file_path
    
    @staticmethod
    def find_audio_file(trace_id: str, file_type: str = "wav") -> Optional[str]:
        """
        查找音频文件
        
        Args:
            trace_id: 追踪ID
            file_type: 文件类型（wav, webm等）
        
        Returns:
            文件路径，如果不存在则返回 None
        """
        # 可能的文件路径
        possible_dirs = [
            os.path.join('data', 'rvc'),
            os.path.join('data', 'tts'),
            os.path.join('data', 'temp')
        ]
        
        for directory in possible_dirs:
            file_path = os.path.join(directory, f"{trace_id}.{file_type}")
            if os.path.exists(file_path):
                return file_path
        
        return None