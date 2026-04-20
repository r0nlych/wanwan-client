from flask import Blueprint, request, send_file
import os

from src.wanwan_client.infrastructure.http.response_builder import ResponseBuilder
from src.wanwan_client.infrastructure.file_system.file_store import FileStore
from src.wanwan_client.services.stt.local_stt_client import LocalSttClient

# 创建蓝图
api_router = Blueprint('api', __name__, url_prefix='/api')

# 懒加载 STT 客户端
stt_client = None

def get_stt_client():
    """获取 STT 客户端（懒加载）"""
    global stt_client
    if stt_client is None:
        stt_client = LocalSttClient(model_size="tiny")
    return stt_client

@api_router.route('/record', methods=['POST'])
def record_upload():
    """录音文件上传接口"""
    # 初始化默认值，防止异常时变量未定义
    trace_id = ""
    session_id = ""
    
    try:
        # 获取参数
        trace_id = request.form.get('trace_id') or ""
        session_id = request.form.get('session_id') or ""
        audio_file = request.files.get('audio')
        
        # 参数校验
        if not trace_id:
            return ResponseBuilder.error(
                trace_id="",
                session_id=session_id,
                step="record_upload",
                error_code="RECORD_UPLOAD_NO_TRACE_ID",
                error_message="未提供 trace_id"
            ), 400, {'Content-Type': 'application/json'}
        
        if not session_id:
            return ResponseBuilder.error(
                trace_id=trace_id,
                session_id="",
                step="record_upload",
                error_code="RECORD_UPLOAD_NO_SESSION_ID",
                error_message="未提供 session_id"
            ), 400, {'Content-Type': 'application/json'}
        
        if not audio_file:
            return ResponseBuilder.error(
                trace_id=trace_id,
                session_id=session_id,
                step="record_upload",
                error_code="RECORD_UPLOAD_NO_AUDIO",
                error_message="未检测到 audio 文件"
            ), 400, {'Content-Type': 'application/json'}
        
        # 保存文件（使用 FileStore）
        file_path = FileStore.save_recording(audio_file, trace_id)
        
        # 返回成功响应
        return ResponseBuilder.success(
            trace_id=trace_id,
            session_id=session_id,
            step="record_upload",
            payload={
                "audio_path": file_path,
                "format": "webm"
            },
            meta={
                "source": "frontend_media_recorder"
            }
        ), 200, {'Content-Type': 'application/json; charset=utf-8'}
        
    except Exception as e:
        # 异常处理（使用已初始化的变量）
        return ResponseBuilder.error(
            trace_id=trace_id,
            session_id=session_id,
            step="record_upload",
            error_code="RECORD_UPLOAD_SAVE_FAILED",
            error_message=f"保存失败: {str(e)}"
        ), 500, {'Content-Type': 'application/json'}

@api_router.route('/stt', methods=['POST'])
def stt():
    """STT 语音转文字接口"""
    # 初始化默认值，防止异常时变量未定义
    data = {}
    trace_id = ""
    session_id = ""
    
    try:
        data = request.get_json() or {}
        
        # 获取参数
        trace_id = data.get('trace_id') or ""
        session_id = data.get('session_id') or ""
        
        # 参数校验
        if not trace_id:
            return ResponseBuilder.error(
                trace_id="",
                session_id=session_id,
                step="stt",
                error_code="STT_NO_TRACE_ID",
                error_message="未提供 trace_id"
            ), 400, {'Content-Type': 'application/json'}
        
        if not session_id:
            return ResponseBuilder.error(
                trace_id=trace_id,
                session_id="",
                step="stt",
                error_code="STT_NO_SESSION_ID",
                error_message="未提供 session_id"
            ), 400, {'Content-Type': 'application/json'}
        
        # 获取音频路径（严格遵循接口规范，只使用 payload.input_audio_path）
        audio_path = data.get('payload', {}).get('input_audio_path')
        
        if not audio_path:
            return ResponseBuilder.error(
                trace_id=trace_id,
                session_id=session_id,
                step="stt",
                error_code="STT_NO_AUDIO_PATH",
                error_message="未提供音频路径"
            ), 400, {'Content-Type': 'application/json'}
        
        # 调用 STT 服务（使用纯化后的接口）
        stt_result = get_stt_client().transcribe(audio_path)
        
        # 根据服务结果组装响应
        if stt_result["success"]:
            # 成功：返回识别结果
            return ResponseBuilder.success(
                trace_id=trace_id,
                session_id=session_id,
                step="stt",
                payload={
                    "input_audio_path": audio_path,
                    "text": stt_result["text"],
                    "language": stt_result["language"]
                },
                meta={
                    "provider": "local",
                    "model": "whisper"
                }
            ), 200, {'Content-Type': 'application/json; charset=utf-8'}
        else:
            # 失败：返回错误信息
            return ResponseBuilder.error(
                trace_id=trace_id,
                session_id=session_id,
                step="stt",
                error_code="STT_RECOGNIZE_FAILED",
                error_message=stt_result["error_message"]
            ), 500, {'Content-Type': 'application/json'}
            
    except Exception as e:
        # 异常处理（使用已初始化的变量）
        return ResponseBuilder.error(
            trace_id=trace_id,
            session_id=session_id,
            step="stt",
            error_code="STT_PROCESSING_FAILED",
            error_message=f"STT 处理失败: {str(e)}"
        ), 500, {'Content-Type': 'application/json'}