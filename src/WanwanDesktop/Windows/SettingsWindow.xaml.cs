using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using WanwanDesktop.Models;
using WanwanDesktop.Services;

namespace WanwanDesktop.Windows;

public partial class SettingsWindow : Window
{
    private readonly string _settingsPath;
    private readonly string _projectRoot;
    private readonly PythonBackendService _python;
    private readonly AudioPlayerService _player;
    private AppSettings? _appSettings;
    private string _currentTab = "llm";
    private readonly Dictionary<string, TextBox> _fieldBoxes = new();

    private static readonly string[] LlmFields =
    {
        "api_host", "api_path", "api_key", "default_model_id",
        "current_model_id", "temperature", "max_output_tokens",
        "reasoning_enabled", "system_prompt"
    };

    private static readonly string[] SttFields =
    {
        "api_host", "api_path", "api_key", "default_model_id",
        "current_model_id", "resource_id", "auth_mode", "app_id",
        "language_hint", "response_format", "audio_format",
        "request_mode", "prompt"
    };

    private static readonly string[] TtsFields =
    {
        "api_host", "api_path", "api_key", "default_model_id",
        "current_model_id", "resource_id", "auth_mode", "app_id",
        "voice", "voice_type", "language", "response_format", "sample_rate",
        "speed", "volume", "emotion"
    };

    public SettingsWindow(PythonBackendService python, AudioPlayerService player)
    {
        InitializeComponent();

        _python = python;
        _player = player;

        _projectRoot = AppDomain.CurrentDomain.BaseDirectory;
        while (!string.IsNullOrEmpty(_projectRoot) &&
               !File.Exists(Path.Combine(_projectRoot, "AGENTS.md")))
        {
            var parent = Directory.GetParent(_projectRoot);
            if (parent == null) break;
            _projectRoot = parent.FullName;
        }
        _settingsPath = Path.Combine(_projectRoot, "data", "config", "app_settings.json");

        Loaded += (_, _) => LoadSettings();
    }

    private void LoadSettings()
    {
        try
        {
            if (!File.Exists(_settingsPath))
            {
                MessageBox.Show($"设置文件不存在: {_settingsPath}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            var json = File.ReadAllText(_settingsPath);
            _appSettings = JsonSerializer.Deserialize<AppSettings>(json,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

            if (_appSettings == null)
            {
                MessageBox.Show("设置文件解析失败", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            BuildFieldsForTab("llm");
        }
        catch (Exception ex)
        {
            MessageBox.Show($"加载设置失败: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void ServiceTab_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ServiceTab.SelectedIndex == 0) BuildFieldsForTab("llm");
        else if (ServiceTab.SelectedIndex == 1) BuildFieldsForTab("stt");
        else if (ServiceTab.SelectedIndex == 2) BuildFieldsForTab("tts");
    }

    private void BuildFieldsForTab(string tab)
    {
        _currentTab = tab;
        _fieldBoxes.Clear();
        FieldsGrid.Children.Clear();
        FieldsGrid.RowDefinitions.Clear();

        var fields = tab switch
        {
            "llm" => LlmFields,
            "stt" => SttFields,
            "tts" => TtsFields,
            _ => Array.Empty<string>()
        };

        var provider = GetActiveProvider(tab);
        var firstModel = provider?.Models?.FirstOrDefault();

        for (int i = 0; i < fields.Length; i++)
        {
            FieldsGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            var label = new TextBlock
            {
                Text = fields[i].Replace("_", " "),
                Margin = new Thickness(0, 6, 8, 2),
                VerticalAlignment = VerticalAlignment.Center,
                TextAlignment = TextAlignment.Right,
            };
            Grid.SetRow(label, i);
            Grid.SetColumn(label, 0);

            var currentValue = GetFieldValue(provider, firstModel, fields[i]);
            var isPassword = fields[i] == "api_key";

            var textBox = new TextBox
            {
                Margin = new Thickness(0, 4, 0, 2),
                Height = 24,
            };

            if (isPassword)
            {
                // api_key 字段：如已有保存值则显示掩码，用 Tag=true 标记已有值
                var existingApiKey = provider?.ApiKey;
                if (!string.IsNullOrEmpty(existingApiKey))
                {
                    textBox.Text = "••••••••";
                    textBox.Tag = true;
                    textBox.ToolTip = "已设置（已隐藏），留空保留原 key，输入新值覆盖";
                }
                else
                {
                    textBox.Text = "";
                    textBox.Tag = false;
                    textBox.ToolTip = "留空则保留原 key";
                }
            }
            else
            {
                textBox.Text = currentValue;
            }

            if (fields[i] == "current_model_id")
            {
                textBox.ToolTip = "当前 model_id，从 models 列表中取";
                if (firstModel != null)
                    textBox.Text = firstModel.ModelId;
                else
                    textBox.Text = provider?.DefaultModelId ?? "";
            }

            _fieldBoxes[fields[i]] = textBox;

            Grid.SetRow(textBox, i);
            Grid.SetColumn(textBox, 1);

            FieldsGrid.Children.Add(label);
            FieldsGrid.Children.Add(textBox);
        }
    }

    private ProviderConfig? GetActiveProvider(string tab)
    {
        if (_appSettings == null) return null;
        var activeId = _appSettings.ActiveProfileId;
        var profile = _appSettings.Profiles.FirstOrDefault(p => p.ProfileId == activeId);
        if (profile == null) return null;

        var serviceGroup = tab switch
        {
            "llm" => profile.Llm,
            "stt" => profile.Stt,
            "tts" => profile.Tts,
            _ => null
        };

        if (serviceGroup?.Providers == null || serviceGroup.Providers.Count == 0)
            return null;

        return serviceGroup.Providers.FirstOrDefault(p => p.Enabled)
            ?? serviceGroup.Providers[0];
    }

    private static string GetFieldValue(ProviderConfig? provider, ModelConfig? model, string field)
    {
        if (provider == null) return "";

        return field switch
        {
            "api_host" => provider.ApiHost ?? "",
            "api_path" => provider.ApiPath ?? "",
            "api_key" => "",
            "default_model_id" => provider.DefaultModelId ?? "",
            "current_model_id" => model?.ModelId ?? provider.DefaultModelId ?? "",
            "temperature" => ReadModelFirst(model, provider, "temperature"),
            "max_output_tokens" => model?.MaxOutputTokens ?? "",
            "reasoning_enabled" => ReadModelFirst(model, provider, "reasoning_enabled"),
            "system_prompt" => ReadModelFirst(model, provider, "system_prompt"),
            "resource_id" => provider.Extra?.GetValueOrDefault("resource_id")?.ToString() ?? "",
            "auth_mode" => provider.Extra?.GetValueOrDefault("auth_mode")?.ToString() ?? "",
            "app_id" => provider.Extra?.GetValueOrDefault("app_id")?.ToString() ?? "",
            "language_hint" => ReadModelFirst(model, provider, "language_hint"),
            "response_format" => ReadModelFirst(model, provider, "response_format"),
            "audio_format" => ReadModelFirst(model, provider, "audio_format"),
            "request_mode" => ReadModelFirst(model, provider, "request_mode"),
            "prompt" => ReadModelFirst(model, provider, "prompt"),
            "voice" => ReadModelFirst(model, provider, "voice"),
            "voice_type" => ReadModelFirst(model, provider, "voice_type"),
            "language" => ReadModelFirst(model, provider, "language"),
            "sample_rate" => ReadModelFirst(model, provider, "sample_rate"),
            "speed" => ReadModelFirst(model, provider, "speed"),
            "volume" => ReadModelFirst(model, provider, "volume"),
            "emotion" => ReadModelFirst(model, provider, "emotion"),
            _ => ""
        };
    }

    private static string ReadModelFirst(ModelConfig? model, ProviderConfig provider, string key)
    {
        if (model?.Extra?.TryGetValue(key, out var modelValue) == true && modelValue != null)
            return modelValue.ToString() ?? "";

        if (provider.Extra?.TryGetValue(key, out var providerValue) == true && providerValue != null)
            return providerValue.ToString() ?? "";

        return "";
    }

    private bool SaveSettingsToFile()
    {
        if (_appSettings == null) return false;

        var provider = GetActiveProvider(_currentTab);
        if (provider == null) return false;

        // 顶层 provider 字段
        ApplyFieldToProvider(provider, "api_host");
        ApplyFieldToProvider(provider, "api_path");

        // api_key：显示掩码时不覆盖；用户手动输入新值才覆盖
        var apiKeyBox = _fieldBoxes.GetValueOrDefault("api_key");
        var apiKey = apiKeyBox?.Text?.Trim();
        var hasExistingKey = apiKeyBox?.Tag is true;
        var showingMask = hasExistingKey && apiKey == "••••••••";
        if (!string.IsNullOrEmpty(apiKey) && !showingMask)
            provider.ApiKey = apiKey;

        provider.DefaultModelId = _fieldBoxes.GetValueOrDefault("default_model_id")?.Text?.Trim() ?? provider.DefaultModelId;

        provider.Extra ??= new Dictionary<string, object?>();

        // provider-only 字段：只写 provider.extra
        ApplyExtraField(provider, "resource_id");
        ApplyExtraField(provider, "auth_mode");
        ApplyExtraField(provider, "app_id");

        if (provider.Models.Count > 0)
        {
            var model = provider.Models[0];
            model.Extra ??= new Dictionary<string, object?>();

            // LLM 专属：同时写 provider.extra 和 model.extra
            ApplyExtraBoth(provider, model, "temperature");
            model.MaxOutputTokens = _fieldBoxes.GetValueOrDefault("max_output_tokens")?.Text?.Trim() ?? model.MaxOutputTokens;
            ApplyExtraBoth(provider, model, "max_output_tokens");
            ApplyExtraBoth(provider, model, "system_prompt");
            ApplyExtraBoth(provider, model, "reasoning_enabled");

            // STT 专属：同时写 provider.extra 和 model.extra
            ApplyExtraBoth(provider, model, "language_hint");
            ApplyExtraBoth(provider, model, "prompt");
            ApplyExtraBoth(provider, model, "response_format");
            ApplyExtraBoth(provider, model, "audio_format");
            ApplyExtraBoth(provider, model, "request_mode");

            // TTS 专属：同时写 provider.extra 和 model.extra
            ApplyExtraBoth(provider, model, "voice");
            ApplyExtraBoth(provider, model, "voice_type");
            ApplyExtraBoth(provider, model, "language");
            ApplyExtraBoth(provider, model, "sample_rate");
            ApplyExtraBoth(provider, model, "speed");
            ApplyExtraBoth(provider, model, "volume");
            ApplyExtraBoth(provider, model, "emotion");

            // current_model_id 同步：同时写 provider.DefaultModelId 和 model.ModelId
            SyncCurrentModelId(provider, model);
        }

        var json = JsonSerializer.Serialize(_appSettings,
            new JsonSerializerOptions { WriteIndented = true, PropertyNameCaseInsensitive = true });
        File.WriteAllText(_settingsPath, json);

        return true;
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (!SaveSettingsToFile())
            {
                MessageBox.Show("保存失败：无设置数据或无法获取配置", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // 保存后检查当前 tab 的 api_key 是否为空
            var provider = GetActiveProvider(_currentTab);
            var hasApiKey = !string.IsNullOrEmpty(provider?.ApiKey);

            if (!hasApiKey)
            {
                MessageBox.Show(
                    "设置已保存，但当前服务的 API Key 未填写，对应语音功能无法使用。",
                    "保存提示",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
            }
            else
            {
                MessageBox.Show("设置已保存（API Key 已配置）", "成功", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"保存设置失败: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void ApplyFieldToProvider(ProviderConfig provider, string fieldName)
    {
        if (!_fieldBoxes.TryGetValue(fieldName, out var box)) return;
        var value = box.Text?.Trim();

        switch (fieldName)
        {
            case "api_host": provider.ApiHost = value ?? provider.ApiHost; break;
            case "api_path": provider.ApiPath = value ?? provider.ApiPath; break;
            case "default_model_id": provider.DefaultModelId = value ?? provider.DefaultModelId; break;
        }
    }

    private void ApplyExtraField(ProviderConfig provider, string fieldName)
    {
        if (!_fieldBoxes.TryGetValue(fieldName, out var box)) return;
        provider.Extra ??= new Dictionary<string, object?>();
        var value = box.Text?.Trim();
        provider.Extra[fieldName] = string.IsNullOrEmpty(value) ? null : value;
    }

    private void ApplyModelExtra(ModelConfig model, string fieldName)
    {
        if (!_fieldBoxes.TryGetValue(fieldName, out var box)) return;
        model.Extra ??= new Dictionary<string, object?>();
        var value = box.Text?.Trim();
        model.Extra[fieldName] = string.IsNullOrEmpty(value) ? null : value;
    }

    private void ApplyExtraBoth(ProviderConfig provider, ModelConfig model, string fieldName)
    {
        ApplyExtraField(provider, fieldName);
        ApplyModelExtra(model, fieldName);
    }

    private void SyncCurrentModelId(ProviderConfig provider, ModelConfig model)
    {
        if (!_fieldBoxes.TryGetValue("current_model_id", out var box)) return;
        var value = box.Text?.Trim();
        if (string.IsNullOrEmpty(value)) return;

        provider.DefaultModelId = value;
        model.ModelId = value;
    }

    private async void TestTts_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            // ===== 第一阶段：保存前校验必填字段 =====
            var preCheckError = ValidateTtsFieldsBeforeTest();
            if (preCheckError != null)
            {
                MessageBox.Show(preCheckError, "TTS 配置不完整", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ===== 第二阶段：保存当前设置到文件 =====
            if (!SaveSettingsToFile())
            {
                MessageBox.Show("保存设置失败，无法测试 TTS", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // ===== 第三阶段：保存后校验最终 provider 状态 =====
            var provider = GetActiveProvider("tts");
            var postCheckError = ValidateTtsProviderState(provider);
            if (postCheckError != null)
            {
                MessageBox.Show(postCheckError, "TTS 配置不完整", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ===== 第四阶段：禁用按钮，启动测试 =====
            TtsTestButton.IsEnabled = false;
            TtsTestButton.Content = "测试中...";

            var testText = "测试语音配置是否正常";
            var result = await _python.RunTtsTestAsync(testText);

            // ===== 第五阶段：严格判定结果 =====

            // Python 侧必须返回成功
            if (!result.IsSuccess || result.AudioPath == null)
            {
                var errorMsg = result.ErrorMessage ?? "TTS 测试失败，原因未知";
                var fullMsg = string.IsNullOrEmpty(result.ErrorCode)
                    ? errorMsg
                    : $"{errorMsg}\n\n错误码: {result.ErrorCode}";
                MessageBox.Show(fullMsg, "TTS 测试失败", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // 解析音频文件路径（处理相对路径）
            var resolvedPath = result.AudioPath;
            if (!Path.IsPathRooted(resolvedPath))
            {
                var projectRoot = _python.GetProjectRoot();
                resolvedPath = Path.GetFullPath(Path.Combine(projectRoot, resolvedPath));
            }

            // 文件必须存在
            if (!File.Exists(resolvedPath))
            {
                MessageBox.Show(
                    $"TTS 返回了音频路径但文件不存在：{result.AudioPath}",
                    "TTS 测试失败", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // 文件必须非空
            if (new FileInfo(resolvedPath).Length == 0)
            {
                MessageBox.Show(
                    "TTS 生成的音频文件为空（0 字节）",
                    "TTS 测试失败", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // response_format 必须为 wav 才允许播放验证
            var responseFormat = _fieldBoxes.GetValueOrDefault("response_format")?.Text?.Trim()?.ToLower();
            if (!string.IsNullOrEmpty(responseFormat) && responseFormat != "wav")
            {
                MessageBox.Show(
                    $"TTS 已返回音频文件（格式: {responseFormat}），但当前测试只支持 wav 播放验证。\n请将 response_format 改为 wav 后重试。\n\n音频路径: {result.AudioPath}",
                    "TTS 测试未通过", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // WPF 播放必须成功
            var played = await _player.PlayAsync(result.AudioPath);
            if (!played)
            {
                MessageBox.Show(
                    "TTS 生成成功但 WPF 播放失败，请检查音频播放设备",
                    "TTS 测试未通过", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ===== 全部通过 =====
            MessageBox.Show("TTS 测试通过", "TTS 测试", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"TTS 测试异常: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            TtsTestButton.IsEnabled = true;
            TtsTestButton.Content = "测试 TTS";
        }
    }

    private string? ValidateTtsFieldsBeforeTest()
    {
        // api_host 不能为空
        var apiHost = _fieldBoxes.GetValueOrDefault("api_host")?.Text?.Trim();
        if (string.IsNullOrEmpty(apiHost))
            return "api_host 不能为空，请填写 TTS API 地址";

        // api_path 不能为空
        var apiPath = _fieldBoxes.GetValueOrDefault("api_path")?.Text?.Trim();
        if (string.IsNullOrEmpty(apiPath))
            return "api_path 不能为空，请填写 TTS API 路径";

        // voice_type 和 voice 至少一个非空
        var voiceType = _fieldBoxes.GetValueOrDefault("voice_type")?.Text?.Trim();
        var voice = _fieldBoxes.GetValueOrDefault("voice")?.Text?.Trim();
        if (string.IsNullOrEmpty(voiceType) && string.IsNullOrEmpty(voice))
            return "voice_type 和 voice 不能同时为空，请至少填写一个";

        // response_format 不能为空
        var responseFormat = _fieldBoxes.GetValueOrDefault("response_format")?.Text?.Trim();
        if (string.IsNullOrEmpty(responseFormat))
            return "response_format 不能为空，请填写（如 wav）";

        // sample_rate 不能为空且必须是有效整数
        var sampleRateRaw = _fieldBoxes.GetValueOrDefault("sample_rate")?.Text?.Trim();
        if (string.IsNullOrEmpty(sampleRateRaw))
            return "sample_rate 不能为空，请填写（如 24000）";
        if (!int.TryParse(sampleRateRaw, out _))
            return $"sample_rate 不是有效整数：\"{sampleRateRaw}\"，请填写数字（如 24000）";

        // speed 不能为空且必须是有效数字
        var speedRaw = _fieldBoxes.GetValueOrDefault("speed")?.Text?.Trim();
        if (string.IsNullOrEmpty(speedRaw))
            return "speed 不能为空，请填写（如 1.0）";
        if (!double.TryParse(speedRaw, out var speedVal))
            return $"speed 不是有效数字：\"{speedRaw}\"，请填写数字（如 1.0）";
        if (speedVal < 0.5 || speedVal > 2.0)
            return $"speed 值 {speedVal} 超出合理范围（0.5 ~ 2.0）";

        // volume 不能为空且必须是有效数字
        var volumeRaw = _fieldBoxes.GetValueOrDefault("volume")?.Text?.Trim();
        if (string.IsNullOrEmpty(volumeRaw))
            return "volume 不能为空，请填写（如 1.0）";
        if (!double.TryParse(volumeRaw, out var volumeVal))
            return $"volume 不是有效数字：\"{volumeRaw}\"，请填写数字（如 1.0）";
        if (volumeVal < 0.0 || volumeVal > 3.0)
            return $"volume 值 {volumeVal} 超出合理范围（0.0 ~ 3.0）";

        return null;
    }

    private static string? ValidateTtsProviderState(ProviderConfig? provider)
    {
        if (provider == null)
            return "TTS provider 配置缺失，请检查设置文件";

        // api_key 必须最终有效
        if (string.IsNullOrEmpty(provider.ApiKey)
            || (provider.ApiKey.StartsWith("(") && provider.ApiKey.EndsWith(")")))
            return "TTS API Key 未填写或仍为模板值，请在 api_key 字段中输入有效 Key";

        // resource_id 不能为空
        var resourceId = provider.Extra?.GetValueOrDefault("resource_id")?.ToString();
        if (string.IsNullOrEmpty(resourceId)
            || (resourceId.StartsWith("(") && resourceId.EndsWith(")")))
            return "resource_id 未填写或仍为模板值，请填写有效 resource_id";

        // auth_mode 不能为空
        var authMode = provider.Extra?.GetValueOrDefault("auth_mode")?.ToString();
        if (string.IsNullOrEmpty(authMode)
            || (authMode.StartsWith("(") && authMode.EndsWith(")")))
            return "auth_mode 未填写或仍为模板值，请填写（如 x_api_key 或 legacy_app_access）";

        return null;
    }

    private void Cancel_Click(object sender, RoutedEventArgs e) => Close();
}
