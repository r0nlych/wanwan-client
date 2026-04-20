from flask import Flask, send_file, render_template
import os
import json
from datetime import datetime

from src.wanwan_client.desktop.routes.api_router import api_router
from src.wanwan_client.infrastructure.file_system.file_store import FileStore
from src.wanwan_client.infrastructure.http.response_builder import ResponseBuilder

# 初始化Flask应用，设置静态文件目录
app = Flask(__name__, static_folder='static')

# 配置
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key')

# 注册 API 路由
app.register_blueprint(api_router)

# 确保必要的目录存在（统一由 FileStore 管理）
FileStore.ensure_dirs_exist()

@app.route('/chat')
def chat_page():
    # 使用Flask模板渲染机制
    return render_template('chat_page.html')





@app.route('/api/audio/<trace_id>.wav')
def audio_playback(trace_id):
    # 查找文件（统一使用 FileStore 管理）
    file_path = FileStore.find_audio_file(trace_id, "wav")
    
    if file_path:
        return send_file(file_path, mimetype='audio/wav')
    
    # 文件不存在
    return ResponseBuilder.error(
        trace_id=trace_id,
        session_id="",
        step="playback",
        error_code="AUDIO_FILE_NOT_FOUND",
        error_message=f"音频文件不存在: {trace_id}.wav"
    ), 404, {'Content-Type': 'application/json; charset=utf-8'}



# 全局错误处理
@app.errorhandler(404)
def not_found_error(error):
    return ResponseBuilder.error(
        trace_id="",
        session_id="",
        step="error",
        error_code="NOT_FOUND",
        error_message="请求的资源不存在"
    ), 404, {'Content-Type': 'application/json; charset=utf-8'}

@app.errorhandler(500)
def internal_error(error):
    return ResponseBuilder.error(
        trace_id="",
        session_id="",
        step="error",
        error_code="INTERNAL_ERROR",
        error_message="服务器内部错误"
    ), 500, {'Content-Type': 'application/json; charset=utf-8'}

if __name__ == '__main__':
    # 通过环境变量控制调试模式（生产环境应设置 FLASK_DEBUG=False）
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)