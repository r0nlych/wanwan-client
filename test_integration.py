#!/usr/bin/env python3
"""
集成测试：验证录音上传 → STT 识别 → 回填完整主链路
"""
import requests
import json
import time
import sys
import os

# 配置终端编码为 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_record_upload():
    """测试录音上传接口"""
    print("=== 测试录音上传接口 ===\n")
    
    trace_id = "trace_" + str(int(time.time() * 1000))
    session_id = "session_test"
    
    print(f"1. 测试参数：")
    print(f"   - trace_id: {trace_id}")
    print(f"   - session_id: {session_id}")
    print(f"   - 使用测试音频文件: data/temp/trace_1776650460648.webm")
    print()
    
    # 检查测试文件是否存在
    if not os.path.exists("data/temp/trace_1776650460648.webm"):
        print("[ERROR] 测试音频文件不存在")
        return None, None, None
    
    # 准备文件上传
    url = "http://localhost:5000/api/record"
    files = {
        'audio': open('data/temp/trace_1776650460648.webm', 'rb')
    }
    data = {
        'trace_id': trace_id,
        'session_id': session_id
    }
    
    try:
        print(f"2. 发送请求到：{url}")
        start_time = time.time()
        response = requests.post(url, files=files, data=data)
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
        print()
        
        if result.get('status') == 'success':
            payload = result.get('payload', {})
            print(f"5. 上传成功：")
            print(f"   - audio_path: {payload.get('audio_path')}")
            print(f"   - format: {payload.get('format')}")
            print()
            
            meta = result.get('meta', {})
            print(f"6. 元信息：")
            print(f"   - source: {meta.get('source')}")
            print()
            
            print("[OK] 录音上传成功")
            return trace_id, session_id, payload.get('audio_path')
        else:
            error = result.get('error', {})
            print(f"5. 上传失败：")
            print(f"   - code: {error.get('code')}")
            print(f"   - message: {error.get('message')}")
            print()
            
            print("[ERROR] 录音上传失败")
            return None, None, None
            
    except Exception as e:
        print("[ERROR] 录音上传请求异常")
        print(f"   错误信息: {str(e)}")
        return None, None, None
    finally:
        files['audio'].close()

def test_stt(trace_id, session_id, audio_path):
    """测试 STT 接口"""
    print("\n=== 测试 STT 接口 ===\n")
    
    print(f"1. 测试参数：")
    print(f"   - trace_id: {trace_id}")
    print(f"   - session_id: {session_id}")
    print(f"   - audio_path: {audio_path}")
    print()
    
    # 构造请求
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
            
            print("[OK] STT 识别成功")
            return True
        else:
            error = result.get('error', {})
            print(f"5. 错误信息（失败）：")
            print(f"   - code: {error.get('code')}")
            print(f"   - message: {error.get('message')}")
            print()
            
            print("[ERROR] STT 识别失败")
            return False
            
    except Exception as e:
        print("[ERROR] STT 请求异常")
        print(f"   错误信息: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("集成测试：录音上传 → STT 识别 → 回填完整主链路")
    print("=" * 60)
    print()
    
    # 步骤1：测试录音上传
    trace_id, session_id, audio_path = test_record_upload()
    if not audio_path:
        print("\n[ERROR] 录音上传测试失败，终止测试")
        return False
    
    # 步骤2：测试 STT 识别
    stt_success = test_stt(trace_id, session_id, audio_path)
    
    # 总体结果
    print("\n" + "=" * 60)
    print("测试结果汇总：")
    print("-" * 60)
    print(f"录音上传: {'成功' if trace_id else '失败'}")
    print(f"STT 识别: {'成功' if stt_success else '失败'}")
    print(f"完整链路: {'通过' if (trace_id and stt_success) else '失败'}")
    print("=" * 60)
    
    return trace_id and stt_success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[INFO] 测试被用户中断")
        sys.exit(1)