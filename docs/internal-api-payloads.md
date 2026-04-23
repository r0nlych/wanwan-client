# wanwan-client 各阶段 payload 结构定义 v0.3

## 1. 总原则

所有阶段的 `payload` 推荐使用以下统一子结构：

```json
{
  "input": {},
  "output": {},
  "refs": {},
  "options": {}
}
```

说明：
- `input`：本阶段直接消费的输入
- `output`：本阶段直接产出的结果
- `refs`：资源引用
- `options`：本阶段实际生效的关键参数快照

规则：
1. 可按阶段裁剪，但推荐保留语义一致性
2. 不建议把全部字段平铺到 `payload` 顶层
3. 新增阶段优先复用该结构

---

## 2. record_upload

### 最小成功结果
- 必须产出可供 STT 使用的音频资源引用

### 推荐结构

```json
{
  "input": {
    "source": "microphone",
    "client_format": "webm"
  },
  "output": {
    "accepted": true
  },
  "refs": {
    "audio_ref": {
      "type": "local_path",
      "value": "data/temp/input_001.webm",
      "mime_type": "audio/webm"
    }
  },
  "options": {
    "save_local": true
  }
}
```

---

## 3. stt

### 最小成功结果
- `payload.output.text`

### 推荐结构

```json
{
  "input": {
    "language_hint": "zh"
  },
  "output": {
    "text": "你好，今天天气怎么样",
    "segments": [],
    "is_final": true
  },
  "refs": {
    "audio_ref": {
      "type": "local_path",
      "value": "data/temp/input_001.webm",
      "mime_type": "audio/webm"
    }
  },
  "options": {
    "enable_punctuation": true
  }
}
```

### 说明
- `text` 为最小必填结果
- `segments` 可选，供流式或分段识别使用
- `is_final` 建议保留，兼容部分/最终结果

---

## 4. llm

### 最小成功结果
- `payload.output.reply_text`
- 或 `payload.output.reply_message`

### 推荐结构

```json
{
  "input": {
    "messages": [
      {"role": "system", "content": "你是晚晚。"},
      {"role": "user", "content": "你好"}
    ],
    "attachments": [],
    "tools": []
  },
  "output": {
    "reply_text": "我在，你说吧。",
    "reply_message": {
      "role": "assistant",
      "content": "我在，你说吧。"
    },
    "tool_calls": [],
    "finish_reason": "stop"
  },
  "refs": {},
  "options": {
    "temperature": 0.7,
    "max_output_tokens": 512,
    "reasoning_enabled": false
  }
}
```

### 说明
- 长期主结构以 `messages` 为主，不再依赖 `user_text/history/system_prompt` 单一组合
- `attachments` 可承接图片、音频、文件等多模态输入
- `tools`、`tool_calls` 预留工具调用能力
- `reply_text` 是最通用的下游桥接字段

---

## 5. tts

### 最小成功结果
- `payload.output.audio_ref`
- 或 `payload.refs.audio_ref`

### 推荐结构

```json
{
  "input": {
    "text": "我在，你说吧。"
  },
  "output": {
    "audio_ref": {
      "type": "local_path",
      "value": "data/tts/out_001.wav",
      "mime_type": "audio/wav"
    },
    "duration_ms": 2300
  },
  "refs": {},
  "options": {
    "voice": "female_default",
    "speed": 1.0,
    "sample_rate": 24000
  }
}
```

### 说明
- 不要求必须落地为本地文件，但必须提供统一音频引用
- 远程 URL、缓存键、对象 ID 都可作为 `audio_ref`

---

## 6. rvc

### 最小成功结果
- `payload.output.audio_ref`

### 推荐结构

```json
{
  "input": {},
  "output": {
    "audio_ref": {
      "type": "local_path",
      "value": "data/rvc/out_001.wav",
      "mime_type": "audio/wav"
    }
  },
  "refs": {
    "source_audio_ref": {
      "type": "local_path",
      "value": "data/tts/out_001.wav",
      "mime_type": "audio/wav"
    }
  },
  "options": {
    "model": "wanwan_rvc",
    "pitch": 0,
    "index_rate": 0.75
  }
}
```

### 说明
- 未启用 RVC 时，该阶段可返回 `skipped`
- 源音频与结果音频建议分开表达

---

## 7. playback

### 最小成功结果
- `payload.output.playable_ref`
- 或 `payload.output.played = true`

### 推荐结构

```json
{
  "input": {},
  "output": {
    "played": true,
    "playable_ref": {
      "type": "local_path",
      "value": "data/rvc/out_001.wav",
      "mime_type": "audio/wav"
    }
  },
  "refs": {
    "audio_ref": {
      "type": "local_path",
      "value": "data/rvc/out_001.wav",
      "mime_type": "audio/wav"
    }
  },
  "options": {
    "autoplay": true,
    "volume": 1.0
  }
}
```

### 说明
- 若播放是客户端本地行为，`playable_ref` 比 `audio_url` 更通用
- 若未来改为远程音频 URL，也无需改协议，只改 ref 内容

---

## 8. 会话保存建议结构

会话保存不是主阶段之一，但建议统一保存以下内容：

```json
{
  "session_id": "session_abc123",
  "trace_id": "trace_20260421_001",
  "messages": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "我在，你说吧。"}
  ],
  "refs": {
    "audio_ref": null
  },
  "meta": {
    "character_id": "wanwan",
    "provider": "openai_compatible",
    "model": "gpt-4o-mini"
  }
}
```

---

## 9. 最小必填总结

### record_upload
- `refs.audio_ref`

### stt
- `output.text`

### llm
- `output.reply_text` 或 `output.reply_message`

### tts
- `output.audio_ref`

### rvc
- `output.audio_ref`

### playback
- `output.playable_ref` 或 `output.played`

---

## 10. 兼容建议

1. 旧实现若仍使用 `input_audio_path`、`output_audio_path`，建议在适配层转换为 `audio_ref`
2. 旧实现若仍使用 `user_text/history/system_prompt`，建议在进入 llm 阶段前统一转换为 `messages`
3. 不同 provider 的额外字段，优先落入 `meta` 或 `options`
4. 不得把 provider 原始响应直接映射为 `payload.output`
