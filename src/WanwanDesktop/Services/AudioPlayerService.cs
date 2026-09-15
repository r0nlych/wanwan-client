using System;
using System.IO;
using System.Threading.Tasks;
using NAudio.Wave;
using WanwanDesktop.Infrastructure;

namespace WanwanDesktop.Services;

public class AudioPlayerService
{
    private readonly DesktopLogService _log;
    private IWavePlayer? _player;
    private AudioFileReader? _reader;
    private bool _isPlaying;

    public bool IsPlaying => _isPlaying;

    public float Volume { get; set; } = 1.0f;

    public AudioPlayerService(DesktopLogService log)
    {
        _log = log;
    }

    public async Task<bool> PlayAsync(string ttsAudioPath)
    {
        if (_isPlaying)
            throw new InvalidOperationException("已经在播放中");

        // 项目根目录统一由 ProjectPaths 提供，用于把相对音频路径解析为绝对路径
        var projectRoot = ProjectPaths.ProjectRoot;

        // Resolve relative path
        var resolvedPath = ttsAudioPath;
        if (!Path.IsPathRooted(ttsAudioPath))
        {
            resolvedPath = Path.GetFullPath(Path.Combine(projectRoot, ttsAudioPath));
        }

        _log.Info("playback.start", "播放开始",
            new() { ["original_path"] = ttsAudioPath, ["resolved_path"] = resolvedPath });

        if (string.IsNullOrEmpty(resolvedPath))
        {
            _log.Error("playback.failed", "播放失败：路径为空");
            return false;
        }

        if (!File.Exists(resolvedPath))
        {
            _log.Error("playback.failed", "播放失败：文件不存在",
                new() { ["resolved_path"] = resolvedPath });
            return false;
        }

        var fileInfo = new FileInfo(resolvedPath);
        if (fileInfo.Length == 0)
        {
            _log.Error("playback.failed", "播放失败：文件大小为 0");
            return false;
        }

        if (!resolvedPath.EndsWith(".wav", StringComparison.OrdinalIgnoreCase))
        {
            _log.Error("playback.failed", "播放失败：不是 .wav 文件",
                new() { ["resolved_path"] = resolvedPath });
            return false;
        }

        try
        {
            _isPlaying = true;
            _reader = new AudioFileReader(resolvedPath);
            _reader.Volume = Volume;
            _player = new WaveOutEvent();
            _player.Init(_reader);

            var tcs = new TaskCompletionSource<bool>();
            _player.PlaybackStopped += (_, _) =>
            {
                _isPlaying = false;
                _reader?.Dispose();
                _reader = null;
                _player?.Dispose();
                _player = null;
                tcs.TrySetResult(true);
            };

            _player.Play();

            _log.Info("playback.playing", "正在播放",
                new() { ["file_size"] = fileInfo.Length });

            await tcs.Task;

            _log.Info("playback.complete", "播放完成");
            return true;
        }
        catch (Exception ex)
        {
            _isPlaying = false;
            _reader?.Dispose();
            _reader = null;
            _player?.Dispose();
            _player = null;
            _log.Error("playback.failed", "播放异常", new() { ["error"] = ex.Message });
            return false;
        }
    }

    public void Stop()
    {
        try
        {
            _player?.Stop();
        }
        catch { }
        _isPlaying = false;
    }
}
