using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using WanwanDesktop.Models;

namespace WanwanDesktop.Windows;

public partial class SettingsWindow : Window
{
    private readonly string _settingsPath;
    private readonly string _projectRoot;
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
        "voice_type", "language", "response_format", "sample_rate",
        "speed", "volume"
    };

    public SettingsWindow()
    {
        InitializeComponent();

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
                textBox.ToolTip = "留空则保留原 key";
                textBox.Text = "";
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
            "temperature" => provider.Extra?.GetValueOrDefault("temperature")?.ToString() ?? "",
            "max_output_tokens" => model?.MaxOutputTokens ?? "",
            "reasoning_enabled" => model?.Extra?.GetValueOrDefault("reasoning_enabled")?.ToString() ?? "",
            "system_prompt" => provider.Extra?.GetValueOrDefault("system_prompt")?.ToString() ?? "",
            "resource_id" => provider.Extra?.GetValueOrDefault("resource_id")?.ToString() ?? "",
            "auth_mode" => provider.Extra?.GetValueOrDefault("auth_mode")?.ToString() ?? "",
            "app_id" => provider.Extra?.GetValueOrDefault("app_id")?.ToString() ?? "",
            "language_hint" => provider.Extra?.GetValueOrDefault("language_hint")?.ToString() ?? "",
            "response_format" => provider.Extra?.GetValueOrDefault("response_format")?.ToString() ?? "",
            "audio_format" => provider.Extra?.GetValueOrDefault("audio_format")?.ToString() ?? "",
            "request_mode" => provider.Extra?.GetValueOrDefault("request_mode")?.ToString() ?? "",
            "prompt" => provider.Extra?.GetValueOrDefault("prompt")?.ToString() ?? "",
            "voice_type" => provider.Extra?.GetValueOrDefault("voice_type")?.ToString() ?? "",
            "language" => provider.Extra?.GetValueOrDefault("language")?.ToString() ?? "",
            "sample_rate" => provider.Extra?.GetValueOrDefault("sample_rate")?.ToString() ?? "",
            "speed" => provider.Extra?.GetValueOrDefault("speed")?.ToString() ?? "",
            "volume" => provider.Extra?.GetValueOrDefault("volume")?.ToString() ?? "",
            _ => ""
        };
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (_appSettings == null)
            {
                MessageBox.Show("无设置数据", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            var provider = GetActiveProvider(_currentTab);
            if (provider == null)
            {
                MessageBox.Show("无法获取配置", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            ApplyFieldToProvider(provider, "api_host");
            ApplyFieldToProvider(provider, "api_path");

            var apiKey = _fieldBoxes.GetValueOrDefault("api_key")?.Text?.Trim();
            if (!string.IsNullOrEmpty(apiKey))
                provider.ApiKey = apiKey;

            provider.DefaultModelId = _fieldBoxes.GetValueOrDefault("default_model_id")?.Text?.Trim() ?? provider.DefaultModelId;

            provider.Extra ??= new Dictionary<string, object?>();
            ApplyExtraField(provider, "temperature");
            ApplyExtraField(provider, "language_hint");
            ApplyExtraField(provider, "response_format");
            ApplyExtraField(provider, "audio_format");
            ApplyExtraField(provider, "request_mode");
            ApplyExtraField(provider, "prompt");
            ApplyExtraField(provider, "resource_id");
            ApplyExtraField(provider, "auth_mode");
            ApplyExtraField(provider, "app_id");
            ApplyExtraField(provider, "voice_type");
            ApplyExtraField(provider, "language");
            ApplyExtraField(provider, "sample_rate");
            ApplyExtraField(provider, "speed");
            ApplyExtraField(provider, "volume");

            if (provider.Models.Count > 0)
            {
                var model = provider.Models[0];
                model.MaxOutputTokens = _fieldBoxes.GetValueOrDefault("max_output_tokens")?.Text?.Trim() ?? model.MaxOutputTokens;
                model.Extra ??= new Dictionary<string, object?>();
                ApplyModelExtra(model, "reasoning_enabled");
                ApplyModelExtra(model, "system_prompt");
            }

            var json = JsonSerializer.Serialize(_appSettings,
                new JsonSerializerOptions { WriteIndented = true, PropertyNameCaseInsensitive = true });
            File.WriteAllText(_settingsPath, json);

            MessageBox.Show("设置已保存", "成功", MessageBoxButton.OK, MessageBoxImage.Information);
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

    private void Cancel_Click(object sender, RoutedEventArgs e) => Close();
}
