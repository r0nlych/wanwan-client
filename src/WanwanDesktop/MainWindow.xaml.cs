using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Microsoft.Win32;
using WanwanDesktop.Models;
using WanwanDesktop.Services;
using WanwanDesktop.Windows;

namespace WanwanDesktop;

public partial class MainWindow : Window
{
    private readonly DesktopLogService _log;
    private readonly PythonBackendService _python;
    private readonly AudioRecorderService _recorder;
    private readonly AudioPlayerService _player;
    private LogWindow? _logWindow;
    private SettingsWindow? _settingsWindow;
    private bool _isRunning;
    private bool _isShuttingDown;

    public MainWindow()
    {
        InitializeComponent();

        // 复用进程级共享日志服务，保证 App 全局兜底与主窗口写入同一份日志
        _log = DesktopLogService.Shared;
        _python = new PythonBackendService(_log);
        _recorder = new AudioRecorderService(_log);
        _player = new AudioPlayerService(_log);

        _log.Info("app.start", "WPF 桌宠启动");
    }

    private void Window_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton == MouseButton.Left)
            DragMove();
    }

    // ======================== Status ========================

    private void SetStatus(string text)
    {
        Dispatcher.Invoke(() => StatusLabel.Text = text);
    }

    private void SetResult(string text)
    {
        Dispatcher.Invoke(() =>
        {
            ResultLabel.Text = text;
            ResultLabel.ToolTip = null;
        });
    }

    private static string TruncateText(string? text, int maxLength)
    {
        if (string.IsNullOrEmpty(text))
            return "";
        return text.Length <= maxLength ? text : text[..maxLength] + "...";
    }

    // ======================== Recording ========================

    private void StartRecord_Click(object sender, RoutedEventArgs e)
    {
        if (_isRunning || _recorder.IsRecording)
        {
            SetStatus(_isRunning ? "运行中..." : "录音中...");
            return;
        }

        try
        {
            _recorder.StartRecording();
            SetStatus("录音中...");
        }
        catch (Exception ex)
        {
            SetStatus("录音失败");
            _log.Error("record.ui_failed", "开始录音失败", new() { ["error"] = ex.Message });
            MessageBox.Show($"录音失败\nstep=recorder\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async void StopRecord_Click(object sender, RoutedEventArgs e)
    {
        if (!_recorder.IsRecording) return;

        string? audioPath;
        try
        {
            audioPath = _recorder.StopRecording();
        }
        catch (Exception ex)
        {
            SetStatus("录音为空");
            _log.Warn("record.ui_empty", "停止录音失败", new() { ["error"] = ex.Message });
            MessageBox.Show($"停止录音失败\nstep=recorder\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }

        await RunVoiceChainAsync(audioPath);
    }

    private void CancelRecord_Click(object sender, RoutedEventArgs e)
    {
        if (!_recorder.IsRecording) return;

        try
        {
            _recorder.CancelRecording();
            SetStatus("已取消");
        }
        catch (Exception ex)
        {
            _log.Warn("record.ui_cancel", "取消录音失败", new() { ["error"] = ex.Message });
        }
    }

    // ======================== Choose Audio ========================

    private async void ChooseAudio_Click(object sender, RoutedEventArgs e)
    {
        // 处理中或录音中都不允许再提交一段音频，防止重复进入链路
        if (_isRunning || _recorder.IsRecording)
        {
            SetStatus(_recorder.IsRecording ? "录音中..." : "处理中...");
            return;
        }

        try
        {
            _log.Info("choose_audio.start", "打开文件选择框");

            var dialog = new OpenFileDialog
            {
                // 当前演示版本录音与 NAudio 播放链路仅可靠支持 WAV，明确限制可选格式
                Title = "选择本地 WAV 音频文件",
                Filter = "WAV 音频文件 (*.wav)|*.wav|所有文件 (*.*)|*.*",
                InitialDirectory = Path.GetFullPath(Path.Combine(_python.GetProjectRoot(), "data", "temp")),
            };

            if (dialog.ShowDialog() != true)
            {
                SetStatus("已取消");
                return;
            }

            // 即使用户通过“所有文件”选了其他格式，也在提交前拦截并提示
            if (!dialog.FileName.EndsWith(".wav", StringComparison.OrdinalIgnoreCase))
            {
                SetStatus("仅支持 WAV");
                _log.Warn("choose_audio.unsupported_format", "选择了非 WAV 文件，已拒绝提交",
                    new() { ["audio_path"] = dialog.FileName });
                MessageBox.Show("当前演示版本仅可靠支持 WAV 音频，请选择 .wav 文件。",
                    "晚晚", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            _log.Info("choose_audio.selected", "用户选择了音频",
                new() { ["audio_path"] = dialog.FileName });

            await RunVoiceChainAsync(dialog.FileName);
        }
        catch (Exception ex)
        {
            SetStatus("失败");
            _log.Error("choose_audio.error", "选择音频异常", new() { ["error"] = ex.Message });
            MessageBox.Show($"选择音频失败\nstep=choose_audio\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    // ======================== Voice Chain ========================

    private async Task RunVoiceChainAsync(string audioPath)
    {
        SetStatus("处理中...");
        SetResult("");
        _isRunning = true;

        try
        {
            // 发送前本地静音检测：纯静音不调用 STT，省一次 API 请求并给出更快反馈
            var silence = AudioSilenceDetector.Analyze(audioPath);
            if (!string.IsNullOrEmpty(silence.Error))
            {
                // 检测自身失败时放行，只记录警告，不阻塞正常链路
                _log.Warn("silence_check.error", "静音检测失败，放行继续发送",
                    new() { ["error"] = silence.Error, ["audio_path"] = audioPath });
            }
            else if (silence.IsSilent)
            {
                SetStatus("没有听到声音");
                SetResult("");
                _log.Info("voice_chain.silence_blocked", "检测到静音，未发送 STT 请求",
                    new()
                    {
                        ["audio_path"] = audioPath,
                        ["duration_seconds"] = Math.Round(silence.DurationSeconds, 1),
                        ["peak"] = silence.Peak,
                        ["max_window_rms"] = silence.MaxWindowRms,
                    });
                MessageBox.Show(
                    "没有听到声音，请靠近麦克风再说一次。",
                    "晚晚", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            // 当前 IPC 只有一次最终结果，无法确认 STT/LLM/TTS 实时阶段，
            // 等待期间统一显示“处理中”，不伪造 TRANSCRIBING/THINKING/SPEAKING
            var outcome = await _python.RunVoiceChainAsync(audioPath);

            if (!outcome.IsSuccess)
            {
                if (outcome.Result == null)
                {
                    // 传输层失败：超时 / 无输出 / JSON 非法 / 进程异常
                    SetStatus(outcome.FailureCode == "TIMEOUT" ? "Python 超时" : "后端失败");
                    SetResult(outcome.FailureMessage ?? "Python 后端调用失败");
                    _log.Error("voice_chain.transport_failed", "语音链路传输层失败",
                        new()
                        {
                            ["failure_code"] = outcome.FailureCode,
                            ["failure_message"] = outcome.FailureMessage,
                        });
                    MessageBox.Show(
                        $"{outcome.FailureMessage}\n\n错误代码：{outcome.FailureCode}",
                        "晚晚", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
                else
                {
                    // 结构化阶段失败：Python 正常返回，但 STT/LLM/TTS 等某阶段失败
                    var failedResult = outcome.Result;
                    var failedStep = ResolveFailedStep(failedResult);
                    var errorCode = ResolveErrorCode(failedResult);

                    // “没听清”是可恢复的输入问题，与系统故障区分开
                    if (ContainsAny(errorCode, "NO_SPEECH"))
                    {
                        SetStatus("没有听到声音");
                        SetResult("没有听清，请靠近麦克风再说一次");
                        _log.Warn("voice_chain.no_speech", "STT 未识别到语音内容",
                            new() { ["trace_id"] = failedResult.TraceId, ["step"] = failedStep });
                        MessageBox.Show(
                            "没有听清，请靠近麦克风再说一次。",
                            "晚晚", MessageBoxButton.OK, MessageBoxImage.Information);
                        return;
                    }

                    var failureMessage = BuildVoiceChainFailureMessage(failedResult);

                    SetStatus(BuildFailureStatus(failedStep));
                    SetResult(failureMessage);
                    _log.Error("voice_chain.failed", "语音链路失败",
                        new()
                        {
                            ["failure"] = failureMessage,
                            ["trace_id"] = failedResult.TraceId,
                            ["step"] = failedStep,
                            ["error_code"] = errorCode,
                            ["step_display"] = GetStepDisplayName(failedStep),
                        });
                }

                // 失败后状态已可继续下一轮录音（_isRunning 由 finally 统一复位）
                return;
            }

            var result = outcome.Result;
            // 理论不可达：IsSuccess 已保证 Result 非空，守卫仅用于让空引用流分析明确
            if (result == null) return;

            var sttText = result.Final?.SttText ?? "";
            var replyText = result.Final?.ReplyText ?? result.Final?.LlmReplyText ?? "";
            var ttsPath = result.Final?.TtsAudioPath ?? "";

            var convSaved = result.ConversationSave?.Saved ?? false;
            _log.Info("voice_chain.result", "语音链路完成",
                new()
                {
                    ["trace_id"] = result.TraceId,
                    ["stt_text"] = sttText,
                    ["tts_audio_path"] = ttsPath,
                    ["conversation_saved"] = convSaved,
                });

            if (!string.IsNullOrEmpty(ttsPath))
            {
                // 当前演示版本 NAudio 播放链路仅可靠支持 WAV；
                // TTS 若配置成其他格式，明确提示，而不是静默“播放失败”
                if (!ttsPath.EndsWith(".wav", StringComparison.OrdinalIgnoreCase))
                {
                    const string formatMessage = "TTS 输出不是 WAV，当前演示版本仅支持 WAV 自动播放";
                    SetStatus("播放失败");
                    SetResult(formatMessage);
                    _log.Error("playback.unsupported_format", "TTS 输出格式不受支持，已跳过播放",
                        new() { ["tts_audio_path"] = ttsPath });
                    MessageBox.Show(
                        $"{formatMessage}\n请在设置中将 TTS 输出格式调整为 wav 后重试。",
                        "晚晚", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
                else
                {
                    SetStatus("播放中...");
                    _player.Volume = ReadVoiceVolumeFromSettings();
                    var played = await _player.PlayAsync(ttsPath);

                    if (played)
                    {
                        SetStatus("完成");
                    }
                    else
                    {
                        // 播放结束/失败都要回到可再次录音的状态（_isRunning 由 finally 复位）
                        SetStatus("播放失败");
                        _log.Error("playback.ui_failed", "播放失败");
                        MessageBox.Show($"播放失败\nstep=playback\nerror_type=playback_error\nerror_message=无法播放 TTS 音频",
                            "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                    }
                }
            }
            else
            {
                SetStatus("完成");
                _log.Warn("voice_chain.no_tts", "语音链路未返回 TTS 路径");
            }

            var summary = "";
            if (!string.IsNullOrEmpty(sttText))
                summary += $"识别: {TruncateText(sttText, 25)}";
            if (!string.IsNullOrEmpty(replyText))
                summary += (summary.Length > 0 ? " | " : "") + $"回复: {TruncateText(replyText, 25)}";
            if (summary.Length == 0)
                summary = "完成";
            SetResult(summary);

            if (!string.IsNullOrEmpty(sttText) || !string.IsNullOrEmpty(replyText))
            {
                var tooltipText = "";
                if (!string.IsNullOrEmpty(sttText))
                    tooltipText += $"识别文本：\n{sttText}";
                if (!string.IsNullOrEmpty(replyText))
                    tooltipText += (tooltipText.Length > 0 ? "\n\n" : "") + $"回复文本：\n{replyText}";

                ResultLabel.ToolTip = new TextBlock
                {
                    Text = tooltipText,
                    TextWrapping = TextWrapping.Wrap,
                    MaxWidth = 320,
                    FontSize = 13,
                };
            }
        }
        catch (Exception ex)
        {
            SetStatus("失败");
            _log.Error("voice_chain.error", "语音链路异常", new() { ["error"] = ex.Message });
            MessageBox.Show($"语音链路异常\nstep=voice_chain\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            _isRunning = false;
        }
    }

    private static string BuildVoiceChainFailureMessage(VoiceChainResult? result)
    {
        if (result == null)
            return "Python 后端失败：未返回可解析结果";

        var failedStage = result.Final?.FailedStage;
        var step = NormalizeStep(failedStage?.Step);
        var error = failedStage?.Error;

        if (string.IsNullOrEmpty(step) || error == null)
        {
            foreach (var stage in result.Stages ?? Enumerable.Empty<VoiceChainStage>())
            {
                if (!string.Equals(stage.Status, "failed", StringComparison.OrdinalIgnoreCase))
                    continue;

                step = NormalizeStep(stage.Step);
                error = stage.Error;
                break;
            }
        }

        if (string.IsNullOrEmpty(step))
            step = NormalizeStep(result.Step);

        var title = BuildFailureTitle(step, error);
        var detail = FirstNonEmpty(error?.Message, error?.Code, "请查看日志");
        return $"{title}：{detail}";
    }

    private static string? ResolveFailedStep(VoiceChainResult? result)
    {
        if (result == null)
            return null;

        var failedStageStep = NormalizeStep(result.Final?.FailedStage?.Step);
        if (!string.IsNullOrEmpty(failedStageStep))
            return failedStageStep;

        foreach (var stage in result.Stages ?? Enumerable.Empty<VoiceChainStage>())
        {
            if (string.Equals(stage.Status, "failed", StringComparison.OrdinalIgnoreCase))
                return NormalizeStep(stage.Step);
        }

        return NormalizeStep(result.Step);
    }

    /// <summary>
    /// 与失败阶段定位相同的查找顺序：final.failed_stage → stages 中第一个 failed。
    /// </summary>
    private static string ResolveErrorCode(VoiceChainResult? result)
    {
        if (result == null)
            return "";

        var directCode = result.Final?.FailedStage?.Error?.Code;
        if (!string.IsNullOrWhiteSpace(directCode))
            return directCode;

        foreach (var stage in result.Stages ?? Enumerable.Empty<VoiceChainStage>())
        {
            if (!string.Equals(stage.Status, "failed", StringComparison.OrdinalIgnoreCase))
                continue;
            if (!string.IsNullOrWhiteSpace(stage.Error?.Code))
                return stage.Error.Code;
        }

        return "";
    }

    private static string BuildFailureTitle(string? step, VoiceChainError? error)
    {
        if (IsConfigError(error))
            return "配置失败";

        return NormalizeStep(step) switch
        {
            "stt" => "STT 失败",
            "llm" => "LLM 失败",
            "tts" => "TTS 失败",
            "playback" => "播放失败",
            "record_upload" or "voice_chain" or "recorder" => "音频输入失败",
            "config" or "settings" => "配置失败",
            _ => "Python 后端失败",
        };
    }

    private static string GetStepDisplayName(string? step)
    {
        return NormalizeStep(step) switch
        {
            "stt" => "STT 语音识别",
            "llm" => "LLM 回复生成",
            "tts" => "TTS 语音合成",
            "playback" => "音频播放",
            "record_upload" or "voice_chain" or "recorder" => "音频输入",
            "config" or "settings" => "配置读取",
            _ => "未知阶段",
        };
    }

    /// <summary>
    /// 结构化阶段失败时桌宠上显示的短状态，与详细错误（ResultLabel）区分。
    /// </summary>
    private static string BuildFailureStatus(string? step)
    {
        return NormalizeStep(step) switch
        {
            "stt" => "识别失败",
            "llm" => "回复失败",
            "tts" => "合成失败",
            "playback" => "播放失败",
            "config" or "settings" => "配置失败",
            "record_upload" or "voice_chain" or "recorder" => "输入失败",
            _ => "链路失败",
        };
    }

    private static bool IsConfigError(VoiceChainError? error)
    {
        var code = error?.Code ?? "";
        var type = error?.Type ?? "";
        var message = error?.Message ?? "";

        return ContainsAny(code, "CONFIG", "SETTINGS")
            || ContainsAny(type, "config")
            || ContainsAny(
                message,
                "config",
                "settings",
                "provider not found",
                "configured provider not found",
                "model not found",
                "configured model not found",
                "missing api key",
                "api_key",
                "api key",
                "api_host",
                "api_path");
    }

    private static bool ContainsAny(string value, params string[] candidates)
    {
        foreach (var candidate in candidates)
        {
            if (value.Contains(candidate, StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }

    private static string NormalizeStep(string? step)
    {
        return (step ?? "").Trim().ToLowerInvariant();
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
                return value.Trim();
        }

        return "";
    }

    // ======================== Settings ========================

    private void OpenSettings_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            _log.Info("settings.open", "打开设置页");

            if (_settingsWindow != null)
            {
                try { _settingsWindow.Activate(); }
                catch { _settingsWindow = null; }
                if (_settingsWindow != null) return;
            }

            _settingsWindow = new SettingsWindow(_python, _player);
            _settingsWindow.Closed += (_, _) =>
            {
                _settingsWindow = null;
                _log.Info("settings.close", "设置页关闭");
            };
            _settingsWindow.Show();
        }
        catch (Exception ex)
        {
            _settingsWindow = null;
            var fullError = ex.ToString();
            _log.Error("settings.error", "打开设置页失败", new() { ["error"] = fullError });
            MessageBox.Show($"打开设置页失败\nstep=settings\nerror_type={ex.GetType().Name}\n\n{fullError}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    // ======================== Log ========================

    private void OpenLogWindow_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            _log.Info("log_window.open", "打开日志窗口");

            if (_logWindow != null)
            {
                try { _logWindow.Activate(); }
                catch { _logWindow = null; }
                if (_logWindow != null) return;
            }

            _logWindow = new LogWindow();
            _logWindow.Closed += (_, _) =>
            {
                _logWindow = null;
                _log.Info("log_window.close", "日志窗口关闭");
            };
            _logWindow.Show();
        }
        catch (Exception ex)
        {
            _log.Error("log_window.error", "打开日志窗口失败", new() { ["error"] = ex.Message });
            MessageBox.Show($"打开日志窗口失败\nstep=log_window\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OpenLogFolder_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Process.Start("explorer.exe", _log.GetLogDir());
        }
        catch (Exception ex)
        {
            MessageBox.Show($"打开日志文件夹失败\nstep=log_folder\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    // ======================== Exit ========================

    private void Exit_Click(object sender, RoutedEventArgs e)
    {
        SafeShutdown();
    }

    protected override void OnClosed(EventArgs e)
    {
        SafeShutdown();
        base.OnClosed(e);
    }

    private void SafeShutdown()
    {
        if (_isShuttingDown) return;
        _isShuttingDown = true;

        _log.Info("app.exit", "开始安全退出");

        try
        {
            if (_recorder.IsRecording)
                _recorder.CancelRecording();
        }
        catch { }

        try
        {
            _player.Stop();
        }
        catch { }

        try
        {
            _settingsWindow?.Close();
        }
        catch { }

        try
        {
            _logWindow?.Close();
        }
        catch { }

        try
        {
            Application.Current.Shutdown();
        }
        catch { }
    }

    private float ReadVoiceVolumeFromSettings()
    {
        try
        {
            // 复用 PythonBackendService 已有的项目根目录查找
            var settingsPath = Path.Combine(_python.GetProjectRoot(), "data", "config", "app_settings.json");
            if (!File.Exists(settingsPath)) return 1.0f;

            var json = File.ReadAllText(settingsPath);
            var settings = JsonSerializer.Deserialize<AppSettings>(json,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (settings == null) return 1.0f;

            // 按 active_profile_id 定位 profile，而非硬编码 profiles[0]
            var profile = settings.Profiles.FirstOrDefault(p => p.ProfileId == settings.ActiveProfileId);
            if (profile == null) return 1.0f;

            var savedVolume = profile.Desktop?.ResolveVoiceVolume();
            return savedVolume is >= 0.1 and <= 2.0 ? (float)savedVolume.Value : 1.0f;
        }
        catch
        {
            return 1.0f;
        }
    }
}
