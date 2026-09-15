using System;
using System.IO;
using System.Threading;
using NAudio.Wave;
using WanwanDesktop.Infrastructure;
using WanwanDesktop.Models;

namespace WanwanDesktop.Services;

public class AudioRecorderService
{
    // 等待底层录音线程回调 RecordingStopped 的最长时间。
    // 正常在毫秒级触发；给足上限是为了异常设备下也不卡死 UI。
    private static readonly TimeSpan StopWaitTimeout = TimeSpan.FromSeconds(3);

    private readonly DesktopLogService _log;
    private WaveInEvent? _waveIn;
    private WaveFileWriter? _writer;
    private string? _outputPath;
    private ManualResetEventSlim? _stoppedSignal;
    private bool _isRecording;

    public bool IsRecording => _isRecording;

    public AudioRecorderService(DesktopLogService log)
    {
        _log = log;
    }

    public string StartRecording()
    {
        if (_isRecording)
            throw new InvalidOperationException("已经在录音中");

        try
        {
            // 录音临时目录基于统一的项目根目录拼接
            var projectRoot = ProjectPaths.ProjectRoot;
            var tempDir = Path.Combine(projectRoot, "data", "temp");
            Directory.CreateDirectory(tempDir);

            var timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            _outputPath = Path.Combine(tempDir, $"trace_desktop_{timestamp}.wav");

            // 每轮录音一个全新的完成信号，避免上一轮残留状态
            _stoppedSignal = new ManualResetEventSlim(false);

            _waveIn = new WaveInEvent
            {
                WaveFormat = new WaveFormat(16000, 16, 1),
                BufferMilliseconds = 50,
            };

            _writer = new WaveFileWriter(_outputPath, _waveIn.WaveFormat);
            _waveIn.DataAvailable += OnDataAvailable;
            _waveIn.RecordingStopped += OnRecordingStopped;

            _waveIn.StartRecording();
            _isRecording = true;

            _log.Info("record.start", "录音开始",
                new() { ["output_path"] = _outputPath, ["format"] = "16000Hz/mono/16bit" });

            return _outputPath;
        }
        catch (Exception ex)
        {
            _isRecording = false;
            CleanupSession();
            _log.Error("record.start_failed", "录音启动失败",
                new() { ["error"] = ex.Message });
            throw;
        }
    }

    public string StopRecording()
    {
        if (!_isRecording || _waveIn == null)
            throw new InvalidOperationException("未在录音中");

        var path = _outputPath;
        _isRecording = false;

        // 通知底层停止采集；RecordingStopped 回调稍后在录音线程上触发，
        // 那里会 Dispose WaveFileWriter（回写 RIFF/data 长度），
        // 必须等回调完成后再返回，否则 Python/其他解析器会读到长度为 0 的 WAV 头。
        try
        {
            _waveIn.StopRecording();
        }
        catch (Exception ex)
        {
            _log.Error("record.stop_failed", "停止录音异常", new() { ["error"] = ex.Message });
            throw;
        }

        WaitForRecordingStopped();
        CleanupSession();

        if (string.IsNullOrEmpty(path) || !File.Exists(path) || new FileInfo(path).Length == 0)
        {
            _log.Warn("record.empty", "录音为空");
            throw new InvalidOperationException("录音为空");
        }

        _log.Info("record.stop", "录音停止",
            new() { ["output_path"] = path, ["size"] = new FileInfo(path).Length });

        return path;
    }

    public void CancelRecording()
    {
        if (!_isRecording || _waveIn == null)
            throw new InvalidOperationException("未在录音中");

        _isRecording = false;

        try
        {
            _waveIn.StopRecording();
        }
        catch { }

        // 与正常停止相同：等 WAV 写完后再删文件，避免删除一个仍被写入句柄占用的文件
        WaitForRecordingStopped();
        CleanupSession(deleteFile: true);

        _log.Info("record.cancel", "录音已取消");
    }

    /// <summary>
    /// 阻塞等待录音线程的 RecordingStopped 回调完成。
    /// 注意：不能在录音线程自身调用（本应用的调用方都是 UI 线程）。
    /// </summary>
    private void WaitForRecordingStopped()
    {
        var signal = _stoppedSignal;
        try
        {
            signal?.Wait(StopWaitTimeout);
        }
        catch (Exception ex)
        {
            _log.Warn("record.stop_wait", "等待录音停止回调异常", new() { ["error"] = ex.Message });
        }

        if (signal is { IsSet: false })
        {
            _log.Warn("record.stop_timeout", "等待录音停止回调超时，仍继续释放资源");
        }
    }

    private void OnDataAvailable(object? sender, WaveInEventArgs e)
    {
        try
        {
            _writer?.Write(e.Buffer, 0, e.BytesRecorded);
        }
        catch (Exception ex)
        {
            _log.Warn("record.write_failed", "写入录音数据失败", new() { ["error"] = ex.Message });
        }
    }

    private void OnRecordingStopped(object? sender, StoppedEventArgs e)
    {
        // NAudio 保证该回调在最后一块数据写完之后触发，因此在此 Dispose
        // 既不会丢末尾音频，又能让 WaveFileWriter 回写正确的 RIFF/data 长度。
        try
        {
            _writer?.Dispose();
        }
        catch (Exception ex)
        {
            _log.Warn("record.writer_dispose", "关闭录音文件失败", new() { ["error"] = ex.Message });
        }
        finally
        {
            _writer = null;
        }

        try
        {
            _waveIn?.Dispose();
        }
        catch { }

        _stoppedSignal?.Set();
    }

    /// <summary>
    /// 统一释放本轮会话的托管资源。文件删除仅用于“取消录音”。
    /// </summary>
    private void CleanupSession(bool deleteFile = false)
    {
        if (deleteFile && !string.IsNullOrEmpty(_outputPath))
        {
            try
            {
                if (File.Exists(_outputPath))
                    File.Delete(_outputPath);
            }
            catch (Exception ex)
            {
                _log.Warn("record.delete_failed", "删除取消录音文件失败", new() { ["error"] = ex.Message });
            }
        }

        // 启动失败等路径下 writer/waveIn 可能仍存在；正常停止时这里已经是 null。
        // NAudio 的 Dispose 可重入，重复调用不会产生副作用。
        try { _writer?.Dispose(); } catch { }
        try { _waveIn?.Dispose(); } catch { }

        _waveIn = null;
        _writer = null;
        _outputPath = null;

        _stoppedSignal?.Dispose();
        _stoppedSignal = null;
    }
}
