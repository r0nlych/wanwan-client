#!/usr/bin/env python3
# 验证 LocalSttClient 纯化后的接口
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.wanwan_client.services.stt.local_stt_client import LocalSttClient

def test_transcribe_interface():
    """验证 transcribe 方法返回格式"""
    print("=== 验证 LocalSttClient.transcribe() 接口 ===")
    
    # 创建客户端
    client = LocalSttClient(model_size="tiny")
    
    # 测试1: 验证方法签名
    print("1. 验证方法签名...")
    import inspect
    sig = inspect.signature(client.transcribe)
    params = list(sig.parameters.keys())
    print(f"   参数列表: {params}")
    assert params == ['audio_path'], f"参数应为 ['audio_path']，实际为 {params}"
    print("   [OK] 方法签名正确")
    
    # 测试2: 验证返回结构（使用不存在的文件测试）
    print("\n2. 验证返回结构...")
    result = client.transcribe("non_existent_file.wav")
    print(f"   返回结果: {result}")
    
    # 检查返回字段
    required_keys = {"success", "text", "language", "error_message"}
    actual_keys = set(result.keys())
    assert actual_keys == required_keys, f"字段应为 {required_keys}，实际为 {actual_keys}"
    print("   [OK] 返回字段正确")
    
    # 检查字段类型
    assert isinstance(result["success"], bool), "success 应为 bool 类型"
    assert isinstance(result["text"], str), "text 应为 str 类型"
    assert isinstance(result["language"], str), "language 应为 str 类型"
    assert isinstance(result["error_message"], str), "error_message 应为 str 类型"
    print("   [OK] 字段类型正确")
    
    # 测试3: 验证错误情况
    print("\n3. 验证错误情况...")
    assert result["success"] == False, "文件不存在时应返回 success=False"
    assert result["text"] == "", "失败时 text 应为空字符串"
    assert result["language"] == "", "失败时 language 应为空字符串"
    assert "音频文件不存在" in result["error_message"], "错误信息应包含提示"
    print(f"   错误信息: {result['error_message']}")
    print("   [OK] 错误情况处理正确")
    
    print("\n=== 接口验证通过 ===")
    print("LocalSttClient.transcribe() 返回统一结构: {success, text, language, error_message}")
    return True

if __name__ == "__main__":
    try:
        test_transcribe_interface()
        print("\n[SUCCESS] 验证成功: transcribe 方法符合纯化要求")
    except Exception as e:
        print(f"\n[ERROR] 验证失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)