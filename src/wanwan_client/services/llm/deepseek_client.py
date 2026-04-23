import os
import logging
from typing import List, Dict, Any, Optional

# 尝试导入 openai，如果未安装会抛出 ImportError
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    openai = None


class DeepSeekClient:
    """
    DeepSeek 客户端，封装与 DeepSeek API 的交互
    返回纯业务结果，不耦合 HTTP 响应格式
    """
    
    def __init__(self):
        """
        初始化客户端，从环境变量读取 API 密钥
        """
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com"
        self.timeout = 30  # 秒
        
        # 检查 openai 库是否安装
        if not HAS_OPENAI:
            raise ImportError("openai 库未安装，请运行: pip install openai")
        
        # 检查 API 密钥是否配置
        if not self.api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY 环境变量")
        
        # 配置 openai 客户端
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        logging.info("DeepSeekClient 初始化完成")
    
    def generate(self, prompt: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        生成回复文本
        
        Args:
            prompt: 用户当前输入文本
            history: 历史对话记录，格式为 [{"role": "user", "content": "..."}, ...]
        
        Returns:
            纯业务结果结构:
            {
                "success": bool,          # 调用是否成功
                "reply_text": str,        # 成功时的回复文本
                "error_message": str      # 失败时的错误信息
            }
        """
        # 默认历史记录为空列表
        if history is None:
            history = []
        
        try:
            # 构建消息列表：历史记录 + 当前用户输入
            messages = []
            
            # 添加历史消息
            for msg in history:
                # 只保留 role 为 "user" 或 "assistant" 的消息
                if msg.get("role") in ["user", "assistant"]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg.get("content", "")
                    })
            
            # 添加当前用户输入
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # 调用 DeepSeek API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=False
            )
            
            # 提取回复文本
            reply_text = response.choices[0].message.content
            
            # 返回成功结果
            return {
                "success": True,
                "reply_text": reply_text.strip(),
                "error_message": ""
            }
            
        except Exception as e:
            # 记录错误日志
            logging.error(f"DeepSeek API 调用失败: {str(e)}")
            
            # 返回失败结果
            return {
                "success": False,
                "reply_text": "",
                "error_message": f"DeepSeek API 调用失败: {str(e)}"
            }