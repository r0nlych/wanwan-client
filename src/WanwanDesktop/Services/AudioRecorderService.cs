using System;
using System.IO;
using NAudio.Wave;
using WanwanDesktop.Infrastructure;
using WanwanDesktop.Models;

namespace WanwanDesktop.Services;

public class AudioRecorderService
{
    private readonly DesktopLogService _log;
    private WaveInEvent? _waveIn;
    private WaveFileWriter? _writer;
    private string? _outputPath;
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
            _waveIn?.Dispose();
            _waveIn = null;
            _writer?.Dispose();
            _writer = null;
            _log.Error("record.start_failed", "录音启动失败",
                new() { ["error"] = ex.Message });
            throw;
        }
    }

    public string StopRecording()
    {
        if (!_isRecording || _waveIn == null)
            throw new InvalidOperationException("未在录音中");

        try
        {
            _waveIn.StopRecording();
        }
        catch (Exception ex)
        {
            _log.Error("record.stop_failed", "停止录音异常", new() { ["error"] = ex.Message });
            throw;
        }

        var path = _outputPath;
        _isRecording = false;
        _waveIn = null;
        _writer = null;

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

        try
        {
            _waveIn.StopRecording();
        }
        catch { }

        try
        {
            if (_outputPath != null && File.Exists(_outputPath))
                File.Delete(_outputPath);
        }
        catch { }

        _isRecording = false;
        _waveIn = null;
        _writer = null;
        _outputPath = null;

        _log.Info("record.cancel", "录音已取消");
    }

    private void OnDataAvailable(object? sender, WaveInEventArgs e)
    {
        try
        {
            _writer?.Write(e.Buffer, 0, e.BytesRecorded);
        }
        catch { }
    }

    private void OnRecordingStopped(object? sender, StoppedEventArgs e)
    {
        try
        {
            _writer?.Dispose();
            _writer = null;
        }
        catch { }

        try
        {
            _waveIn?.Dispose();
        }
        catch { }
    }
}
