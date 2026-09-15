using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace WanwanDesktop.Models;

public class AppSettings
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; set; } = "";

    [JsonPropertyName("active_profile_id")]
    public string ActiveProfileId { get; set; } = "";

    [JsonPropertyName("profiles")]
    public List<ProfileConfig> Profiles { get; set; } = new();
}

public class ProfileConfig
{
    [JsonPropertyName("profile_id")]
    public string ProfileId { get; set; } = "";

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonPropertyName("llm")]
    public ServiceGroup? Llm { get; set; }

    [JsonPropertyName("stt")]
    public ServiceGroup? Stt { get; set; }

    [JsonPropertyName("tts")]
    public ServiceGroup? Tts { get; set; }

    [JsonPropertyName("rvc")]
    public ServiceGroup? Rvc { get; set; }

    [JsonPropertyName("desktop")]
    public DesktopSettings? Desktop { get; set; }
}

public class ServiceGroup
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = true;

    [JsonPropertyName("default_provider_id")]
    public string DefaultProviderId { get; set; } = "";

    [JsonPropertyName("providers")]
    public List<ProviderConfig> Providers { get; set; } = new();
}

public class ProviderConfig
{
    [JsonPropertyName("service_name")]
    public string ServiceName { get; set; } = "";

    [JsonPropertyName("adapter_kind")]
    public string AdapterKind { get; set; } = "";

    [JsonPropertyName("provider_id")]
    public string ProviderId { get; set; } = "";

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = true;

    [JsonPropertyName("api_host")]
    public string ApiHost { get; set; } = "";

    [JsonPropertyName("api_path")]
    public string ApiPath { get; set; } = "";

    [JsonPropertyName("api_key")]
    public string? ApiKey { get; set; }

    [JsonPropertyName("api_key_env")]
    public string? ApiKeyEnv { get; set; }

    [JsonPropertyName("timeout_seconds")]
    public string TimeoutSeconds { get; set; } = "";

    [JsonPropertyName("default_model_id")]
    public string DefaultModelId { get; set; } = "";

    [JsonPropertyName("models")]
    public List<ModelConfig> Models { get; set; } = new();

    [JsonPropertyName("capabilities")]
    public List<string> Capabilities { get; set; } = new();

    [JsonPropertyName("extra")]
    public Dictionary<string, object?>? Extra { get; set; }
}

public class ModelConfig
{
    [JsonPropertyName("model_id")]
    public string ModelId { get; set; } = "";

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = "";

    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = true;

    [JsonPropertyName("capabilities")]
    public List<string> Capabilities { get; set; } = new();

    [JsonPropertyName("context_window")]
    public string ContextWindow { get; set; } = "";

    [JsonPropertyName("max_output_tokens")]
    public string MaxOutputTokens { get; set; } = "";

    [JsonPropertyName("extra")]
    public Dictionary<string, object?>? Extra { get; set; }
}

public class DesktopSettings
{
    [JsonPropertyName("volume")]
    public double? Volume { get; set; }

    // 捕获旧版 desktop.audio 等未映射字段，仅用于旧配置兼容回退（保存时会清理）
    [JsonExtensionData]
    public Dictionary<string, JsonElement>? Extra { get; set; }

    /// <summary>
    /// 解析有效音量：优先顶层 volume（desktop.volume）；
    /// 缺失或不在 [0.1, 2.0] 时回退旧版 desktop.audio.voice_volume；仍无效则返回 null。
    /// </summary>
    public double? ResolveVoiceVolume()
    {
        if (Volume is > 0.09 and <= 2.0) return Volume;

        if (Extra?.TryGetValue("audio", out var audioEl) == true
            && audioEl.ValueKind == JsonValueKind.Object
            && audioEl.TryGetProperty("voice_volume", out var volEl)
            && volEl.TryGetDouble(out var oldVol)
            && oldVol is > 0.09 and <= 2.0)
        {
            return oldVol;
        }

        return null;
    }
}
