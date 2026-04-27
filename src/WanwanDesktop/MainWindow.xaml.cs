using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
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

        _log = new DesktopLogService();
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
        Dispatcher.Invoke(() => ResultLabel.Text = text);
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
        if (_isRunning)
        {
            SetStatus("运行中...");
            return;
        }

        try
        {
            _log.Info("choose_audio.start", "打开文件选择框");

            var dialog = new OpenFileDialog
            {
                Title = "选择本地音频文件",
                Filter = "音频文件 (*.webm;*.wav)|*.webm;*.wav|All Files (*.*)|*.*",
                InitialDirectory = Path.GetFullPath(Path.Combine(_python.GetProjectRoot(), "data", "temp")),
            };

            if (dialog.ShowDialog() != true)
            {
                SetStatus("已取消");
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
            var result = await _python.RunVoiceChainAsync(audioPath);

            if (result == null || result.Status != "success")
            {
                SetStatus("失败");
                SetResult("Python 链路失败，请查看日志");
                _isRunning = false;
                return;
            }

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
                SetStatus("播放中...");
                var played = await _player.PlayAsync(ttsPath);

                if (played)
                {
                    SetStatus("完成");
                }
                else
                {
                    SetStatus("播放失败");
                    _log.Error("playback.ui_failed", "播放失败");
                    MessageBox.Show($"播放失败\nstep=playback\nerror_type=playback_error\nerror_message=无法播放 TTS 音频",
                        "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
            else
            {
                SetStatus("完成");
                _log.Warn("voice_chain.no_tts", "语音链路未返回 TTS 路径");
            }

            var display = "";
            if (!string.IsNullOrEmpty(sttText))
                display += $"识别: {sttText}";
            if (!string.IsNullOrEmpty(replyText))
                display += (display.Length > 0 ? " | " : "") + $"回复: {replyText}";
            if (display.Length == 0)
                display = "完成";
            SetResult(display);
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

            _settingsWindow = new SettingsWindow();
            _settingsWindow.Closed += (_, _) =>
            {
                _settingsWindow = null;
                _log.Info("settings.close", "设置页关闭");
            };
            _settingsWindow.Show();
        }
        catch (Exception ex)
        {
            _log.Error("settings.error", "打开设置页失败", new() { ["error"] = ex.Message });
            MessageBox.Show($"打开设置页失败\nstep=settings\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}",
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
}
