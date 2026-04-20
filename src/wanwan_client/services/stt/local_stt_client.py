import whisper
import os
import json
from datetime import datetime

class LocalSttClient:
    def __init__(self, model_size="tiny"):
        self.model_size = model_size
        self.model = None
    
    def _load_model(self):
        if self.model is None:
            try:
                self.model = whisper.load_model(self.model_size)
                return True
            except Exception as e:
                print(f"模型加载失败: {str(e)}")
                return False
        return True
    
    def transcribe(self, audio_path):
        try:
            if not self._load_model():
                return {
                    "success": False,
                    "text": "",
                    "language": "",
                    "error_message": "模型加载失败"
                }
            
            if not os.path.exists(audio_path):
                return {
                    "success": False,
                    "text": "",
                    "language": "",
                    "error_message": f"音频文件不存在: {audio_path}"
                }
            
            result = self.model.transcribe(audio_path, language="zh")
            text = result["text"].strip()
            
            return {
                "success": True,
                "text": text,
                "language": "zh",
                "error_message": ""
            }
        except Exception as e:
            return {
                "success": False,
                "text": "",
                "language": "",
                "error_message": f"识别失败: {str(e)}"
            }