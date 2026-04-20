import requests
import json
import time
import sys

# 配置终端编码为 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 测试 STT 接口
def test_stt():
    print("=== STT 功能测试 ===\n")
    
    # 测试参数
    trace_id = "trace_" + str(int(time.time() * 1000))
    session_id = "session_001"
    audio_path = "data/temp/trace_1776650460648.webm"
    
    print(f"1. 测试参数：")
    print(f"   - trace_id: {trace_id}")
    print(f"   - session_id: {session_id}")
    print(f"   - audio_path: {audio_path}")
    print()
    
    # 构造请求（遵循接口规范，使用 payload.input_audio_path）
    url = "http://localhost:5000/api/stt"
    payload = {
        "trace_id": trace_id,
        "session_id": session_id,
        "payload": {
            "input_audio_path": audio_path
        }
    }
    
    print(f"2. 发送请求到：{url}")
    print(f"   请求体：{json.dumps(payload, ensure_ascii=False, indent=2)}")
    print()
    
    try:
        # 发送请求
        start_time = time.time()
        response = requests.post(url, json=payload)
        end_time = time.time()
        
        print(f"3. 响应状态：")
        print(f"   - HTTP 状态码: {response.status_code}")
        print(f"   - 响应时间: {(end_time - start_time):.2f} 秒")
        print()
        
        # 解析响应
        result = response.json()
        
        print(f"4. 响应内容：")
        print(f"   - trace_id: {result.get('trace_id')}")
        print(f"   - session_id: {result.get('session_id')}")
        print(f"   - step: {result.get('step')}")
        print(f"   - status: {result.get('status')}")
        print(f"   - timestamp: {result.get('timestamp')}")
        print()
        
        # 第4步：打印原始响应文本
        print(f"[DEBUG] 原始响应 text: {result.get('payload', {}).get('text')}")
        print(f"[DEBUG] 原始响应 text bytes: {result.get('payload', {}).get('text', '').encode('utf-8')}")
        print()
        
        if result.get('status') == 'success':
            payload = result.get('payload', {})
            print(f"5. 识别结果（成功）：")
            print(f"   - input_audio_path: {payload.get('input_audio_path')}")
            print(f"   - text: {payload.get('text')}")
            print(f"   - language: {payload.get('language')}")
            print()
            
            meta = result.get('meta', {})
            print(f"6. 元信息：")
            print(f"   - provider: {meta.get('provider')}")
            print(f"   - model: {meta.get('model')}")
            print()
            
            print("[OK] 测试成功：STT 功能正常")
            return True
        else:
            error = result.get('error', {})
            print(f"5. 错误信息（失败）：")
            print(f"   - code: {error.get('code')}")
            print(f"   - message: {error.get('message')}")
            print()
            
            print("[ERROR] 测试失败：STT 识别失败")
            return False
            
    except Exception as e:
        print("[ERROR] 测试失败：请求异常")
        print(f"   错误信息: {str(e)}")
        return False

if __name__ == "__main__":
    test_stt()