using System;
using NAudio.Wave;

namespace WanwanDesktop.Services;

/// <summary>
/// 发送 STT 前的本地静音检测结果。
/// </summary>
public sealed class SilenceCheckResult
{
    /// <summary>是否判定为静音（静音时不应发送 STT 请求）。</summary>
    public bool IsSilent { get; init; }

    /// <summary>音频时长（秒）。</summary>
    public double DurationSeconds { get; init; }

    /// <summary>全段峰值（归一化 0~1）。</summary>
    public float Peak { get; init; }

    /// <summary>逐 1 秒窗口的最大 RMS（归一化 0~1），用于区分“偶发咔哒声”。</summary>
    public float MaxWindowRms { get; init; }

    /// <summary>检测自身失败时的错误信息；此时一律放行，不能因检测故障挡住正常请求。</summary>
    public string? Error { get; init; }
}

/// <summary>
/// 发送语音链路前的本地静音检测：
/// 用 NAudio 读 WAV，按“峰值 + 每秒窗口 RMS”双条件判断，
/// 阈值根据真实录音样本标定（见 data/temp 下三次实测录音）。
/// </summary>
public static class AudioSilenceDetector
{
    // 归一化幅度阈值（AudioFileReader 输出 float，范围 -1~1）。
    // 实测静音样本峰值约 0.007，轻说话样本峰值约 0.04，取中间偏保守值。
    private const float PeakThreshold = 0.02f;

    // 1 秒窗口 RMS 阈值。实测静音最大窗口约 0.0007，轻说话约 0.0032。
    // 用窗口能量而不是只看峰值，避免一声咔哒被误判成说话。
    private const float WindowRmsThreshold = 0.0015f;

    public static SilenceCheckResult Analyze(string wavPath)
    {
        try
        {
            using var reader = new AudioFileReader(wavPath);
            var sampleRate = reader.WaveFormat.SampleRate;
            var channels = Math.Max(1, reader.WaveFormat.Channels);

            // 每次读 1 秒（含多声道交错样本）
            var buffer = new float[sampleRate * channels];

            float peak = 0f;
            float maxWindowRms = 0f;
            long totalSamples = 0;

            int read;
            while ((read = reader.Read(buffer, 0, buffer.Length)) > 0)
            {
                double squareSum = 0d;
                for (var i = 0; i < read; i++)
                {
                    var sample = buffer[i];
                    var absolute = MathF.Abs(sample);
                    if (absolute > peak)
                        peak = absolute;
                    squareSum += sample * sample;
                }

                var windowRms = (float)Math.Sqrt(squareSum / read);
                if (windowRms > maxWindowRms)
                    maxWindowRms = windowRms;

                totalSamples += read;
            }

            var durationSeconds = sampleRate > 0
                ? (double)totalSamples / channels / sampleRate
                : 0d;

            // 两个条件都达标才认为“有语音”；任一不达标按静音处理，不发 STT。
            var isSilent = peak < PeakThreshold || maxWindowRms < WindowRmsThreshold;

            return new SilenceCheckResult
            {
                IsSilent = isSilent,
                DurationSeconds = durationSeconds,
                Peak = peak,
                MaxWindowRms = maxWindowRms,
            };
        }
        catch (Exception ex)
        {
            // 分析失败不阻塞主流程：放行交给 STT，由调用方记录一条警告日志
            return new SilenceCheckResult
            {
                IsSilent = false,
                Error = ex.Message,
            };
        }
    }
}
