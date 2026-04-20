import json
from datetime import datetime
from typing import Any, Dict, Optional


class ResponseBuilder:
    """统一响应组装类，遵循 docs/wanwan_client_internal_api_spec.md 规范"""
    
    @staticmethod
    def success(
        trace_id: str,
        session_id: str,
        step: str,
        payload: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建成功响应
        
        Args:
            trace_id: 全链路唯一标识
            session_id: 会话标识
            step: 阶段名称 (record_upload, stt, llm, tts, rvc, playback)
            payload: 业务数据对象
            meta: 附加信息对象，默认为空字典
        
        Returns:
            符合规范的 JSON 字符串
        """
        if meta is None:
            meta = {}
        
        response = {
            "trace_id": trace_id,
            "session_id": session_id,
            "step": step,
            "status": "success",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "payload": payload,
            "error": None,
            "meta": meta
        }
        
        return json.dumps(response, ensure_ascii=False)
    
    @staticmethod
    def error(
        trace_id: str,
        session_id: str,
        step: str,
        error_code: str,
        error_message: str,
        meta: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建错误响应
        
        Args:
            trace_id: 全链路唯一标识
            session_id: 会话标识
            step: 阶段名称
            error_code: 错误代码
            error_message: 错误说明
            meta: 附加信息对象，默认为空字典
        
        Returns:
            符合规范的 JSON 字符串
        """
        if meta is None:
            meta = {}
        
        response = {
            "trace_id": trace_id,
            "session_id": session_id,
            "step": step,
            "status": "failed",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "payload": {},
            "error": {
                "code": error_code,
                "message": error_message
            },
            "meta": meta
        }
        
        return json.dumps(response, ensure_ascii=False)