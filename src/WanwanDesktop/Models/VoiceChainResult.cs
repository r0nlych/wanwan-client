using System.Text.Json.Serialization;

namespace WanwanDesktop.Models;

public class VoiceChainResult
{
    [JsonPropertyName("trace_id")]
    public string TraceId { get; set; } = "";

    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = "";

    [JsonPropertyName("step")]
    public string Step { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = "";

    [JsonPropertyName("final")]
    public VoiceChainFinal? Final { get; set; }

    [JsonPropertyName("stages")]
    public List<VoiceChainStage>? Stages { get; set; }

    [JsonPropertyName("conversation_save")]
    public ConversationSave? ConversationSave { get; set; }

    [JsonPropertyName("error")]
    public object? Error { get; set; }
}

public class VoiceChainFinal
{
    [JsonPropertyName("stt_text")]
    public string? SttText { get; set; }

    [JsonPropertyName("reply_text")]
    public string? ReplyText { get; set; }

    [JsonPropertyName("llm_reply_text")]
    public string? LlmReplyText { get; set; }

    [JsonPropertyName("tts_audio_path")]
    public string? TtsAudioPath { get; set; }

    [JsonPropertyName("playback")]
    public VoiceChainPlayback? Playback { get; set; }

    [JsonPropertyName("failed_stage")]
    public VoiceChainFailedStage? FailedStage { get; set; }
}

public class VoiceChainPlayback
{
    [JsonPropertyName("played")]
    public bool? Played { get; set; }

    [JsonPropertyName("error_code")]
    public string? ErrorCode { get; set; }

    [JsonPropertyName("error_message")]
    public string? ErrorMessage { get; set; }
}

public class VoiceChainStage
{
    [JsonPropertyName("trace_id")]
    public string TraceId { get; set; } = "";

    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = "";

    [JsonPropertyName("step")]
    public string Step { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = "";

    [JsonPropertyName("error")]
    public VoiceChainError? Error { get; set; }
}

public class VoiceChainFailedStage
{
    [JsonPropertyName("step")]
    public string Step { get; set; } = "";

    [JsonPropertyName("status")]
    public string? Status { get; set; }

    [JsonPropertyName("error")]
    public VoiceChainError? Error { get; set; }
}

public class VoiceChainError
{
    [JsonPropertyName("code")]
    public string? Code { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("type")]
    public string? Type { get; set; }
}

public class ConversationSave
{
    [JsonPropertyName("saved")]
    public bool Saved { get; set; }

    [JsonPropertyName("path")]
    public string? Path { get; set; }
}
