using System.Text.Json.Serialization;

namespace WanwanDesktop.Models;

/// <summary>
/// Python TextAudioPipeline 的最终返回结构。
/// 文本链路没有 STT 字段，因此不复用 VoiceChainResult，避免把文本输入伪装成语音结果。
/// </summary>
public sealed class TextAudioResult
{
    [JsonPropertyName("trace_id")]
    public string TraceId { get; set; } = "";

    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("stages")]
    public List<VoiceChainStage>? Stages { get; set; }

    [JsonPropertyName("final")]
    public TextAudioFinal? Final { get; set; }

    [JsonPropertyName("conversation_save")]
    public ConversationSave? ConversationSave { get; set; }
}

/// <summary>
/// 文本链路的最小可用结果：助手回复和统一音频资源引用。
/// </summary>
public sealed class TextAudioFinal
{
    [JsonPropertyName("user_text")]
    public string? UserText { get; set; }

    [JsonPropertyName("reply_text")]
    public string? ReplyText { get; set; }

    [JsonPropertyName("audio_ref")]
    public AudioResourceRef? AudioRef { get; set; }
}

/// <summary>
/// 对应内部协议 v0.3 的 audio_ref，当前 WPF MVP 只播放 local_path。
/// 保留 type 与 mime_type，后续支持远程 URL 时无需修改协议模型。
/// </summary>
public sealed class AudioResourceRef
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("value")]
    public string Value { get; set; } = "";

    [JsonPropertyName("mime_type")]
    public string MimeType { get; set; } = "";
}
