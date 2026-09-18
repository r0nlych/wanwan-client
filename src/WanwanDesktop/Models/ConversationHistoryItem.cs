using System.Text.Json.Serialization;

namespace WanwanDesktop.Models;

/// <summary>
/// data/conversations/*.jsonl 中的一条本地会话记录。
/// 字段保持可空，确保升级前生成的旧记录也能继续显示。
/// </summary>
public sealed class ConversationHistoryItem
{
    [JsonPropertyName("trace_id")]
    public string TraceId { get; set; } = "";

    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = "";

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "unknown";

    [JsonPropertyName("input_type")]
    public string? InputType { get; set; }

    [JsonPropertyName("user_text")]
    public string? UserText { get; set; }

    [JsonPropertyName("stt_text")]
    public string? SttText { get; set; }

    [JsonPropertyName("reply_text")]
    public string? ReplyText { get; set; }

    [JsonIgnore]
    public string DisplayInputType => InputType switch
    {
        "voice" => "语音",
        "text" => "文本",
        _ => string.IsNullOrWhiteSpace(SttText) ? "文本" : "语音",
    };

    [JsonIgnore]
    public string DisplayUserText => !string.IsNullOrWhiteSpace(UserText)
        ? UserText
        : (!string.IsNullOrWhiteSpace(SttText) ? SttText : "（没有可显示的用户内容）");

    [JsonIgnore]
    public string DisplayReplyText => !string.IsNullOrWhiteSpace(ReplyText)
        ? ReplyText
        : "（本轮没有生成回复）";

    [JsonIgnore]
    public string DisplayTime => DateTimeOffset.TryParse(Timestamp, out var parsed)
        ? parsed.ToLocalTime().ToString("MM-dd HH:mm")
        : Timestamp;
}
