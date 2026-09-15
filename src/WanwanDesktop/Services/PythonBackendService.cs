using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using WanwanDesktop.Infrastructure;
using WanwanDesktop.Models;

namespace WanwanDesktop.Services;

public class TtsTestResult
{
    public string? AudioPath { get; set; }
    public string? ErrorMessage { get; set; }
    public string? ErrorCode { get; set; }
    public string? StdoutPreview { get; set; }
    public string? StderrPreview { get; set; }

    public bool IsSuccess => AudioPath != null && ErrorMessage == null;
}

/// <summary>
/// 语音链子进程调用结果。
/// Result 非空表示 Python 返回了可解析的结构化结果（其中可能是 success 或阶段失败）；
/// Result 为空表示传输层失败，FailureCode 区分超时 / 无输出 / JSON 非法 / 进程异常。
/// </summary>
public sealed class VoiceChainInvokeResult
{
    public VoiceChainResult? Result { get; init; }
    public string? FailureCode { get; init; }
    public string? FailureMessage { get; init; }

    public bool IsSuccess => Result is { Status: "success" };

    public static VoiceChainInvokeResult Ok(VoiceChainResult result) => new() { Result = result };

    public static VoiceChainInvokeResult TransportFailure(string code, string message) =>
        new() { FailureCode = code, FailureMessage = message };
}

public class PythonBackendService
{
    // 语音链路包含 STT + LLM + TTS 三段网络调用，deepseek-reasoner 偶发较慢，超时给到 180 秒
    private const int VoiceChainTimeoutSeconds = 180;

    private readonly DesktopLogService _log;
    private readonly string _projectRoot;
    private readonly string _pythonPath;

    public PythonBackendService(DesktopLogService log)
    {
        _log = log;

        // 项目根目录统一由 ProjectPaths 定位，不再在本服务内重复向上查找
        _projectRoot = ProjectPaths.ProjectRoot;

        _pythonPath = Path.Combine(_projectRoot, ".venv", "Scripts", "python.exe");
        if (!File.Exists(_pythonPath))
        {
            _pythonPath = "python";
        }
    }

    public async Task<VoiceChainInvokeResult> RunVoiceChainAsync(string audioPath)
    {
        _log.Info("python.start", "开始调用 Python 后端",
            new() { ["audio_path"] = audioPath, ["python_path"] = _pythonPath });

        var args = $"-m src.wanwan_client.main run-voice-chain \"{audioPath}\" --json-only --no-play";
        var startInfo = new ProcessStartInfo
        {
            FileName = _pythonPath,
            Arguments = args,
            WorkingDirectory = _projectRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        using var process = new Process { StartInfo = startInfo };

        var stdoutBuilder = new StringBuilder();
        var stderrBuilder = new StringBuilder();

        process.OutputDataReceived += (_, e) =>
        {
            if (e.Data != null) stdoutBuilder.AppendLine(e.Data);
        };

        process.ErrorDataReceived += (_, e) =>
        {
            if (e.Data != null) stderrBuilder.AppendLine(e.Data);
        };

        try
        {
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();

            // 超时保护：Python 端挂起时不能让 UI 永久等待，超时后杀掉整个进程树
            using var timeoutCts = new CancellationTokenSource(
                TimeSpan.FromSeconds(VoiceChainTimeoutSeconds));
            try
            {
                await process.WaitForExitAsync(timeoutCts.Token);
            }
            catch (OperationCanceledException)
            {
                try { process.Kill(entireProcessTree: true); } catch { }
                _log.Error("python.timeout", $"语音链路超时（{VoiceChainTimeoutSeconds} 秒），已终止 Python 进程",
                    new() { ["timeout_seconds"] = VoiceChainTimeoutSeconds });
                return VoiceChainInvokeResult.TransportFailure(
                    "TIMEOUT",
                    $"Python 语音链路处理超时（{VoiceChainTimeoutSeconds} 秒），已终止，请重试或检查网络");
            }

            var stdout = stdoutBuilder.ToString().Trim();
            var stderr = stderrBuilder.ToString().Trim();

            _log.Info("python.stdout", $"stdout 长度: {stdout.Length}",
                new() { ["stdout_preview"] = stdout.Length > 500 ? stdout[..500] : stdout });

            if (!string.IsNullOrEmpty(stderr))
            {
                _log.Warn("python.stderr", $"stderr 内容",
                    new() { ["stderr"] = stderr, ["exit_code"] = process.ExitCode });
            }

            if (process.ExitCode != 0)
            {
                _log.Error("python.result", $"Python 退出码非 0",
                    new() { ["exit_code"] = process.ExitCode, ["stderr"] = stderr });
            }

            var result = TryParseVoiceChainResult(stdout);
            if (result == null)
            {
                // 传输层失败：区分“无输出”和“输出无法解析”，便于界面给出准确提示
                var code = string.IsNullOrWhiteSpace(stdout) ? "NO_OUTPUT" : "INVALID_JSON";
                var message = code == "NO_OUTPUT"
                    ? "Python 后端没有返回内容，请检查 Python 环境与依赖"
                    : "Python 后端返回内容无法解析，请查看日志";
                return VoiceChainInvokeResult.TransportFailure(code, message);
            }

            _log.Info("python.result", process.ExitCode == 0 ? "Python 后端返回成功" : "Python 后端返回结构化失败",
                new()
                {
                    ["status"] = result.Status,
                    ["trace_id"] = result.TraceId,
                    ["stt_text"] = result.Final?.SttText ?? result.Final?.LlmReplyText,
                    ["conversation_saved"] = result.ConversationSave?.Saved,
                });

            return VoiceChainInvokeResult.Ok(result);
        }
        catch (Exception ex)
        {
            _log.Error("python.exception", "调用 Python 异常",
                new() { ["error"] = ex.Message, ["stack_trace"] = ex.StackTrace });
            return VoiceChainInvokeResult.TransportFailure(
                "PROCESS_EXCEPTION",
                $"调用 Python 后端时发生异常：{ex.Message}");
        }
    }

    public string GetProjectRoot() => _projectRoot;

    public async Task<TtsTestResult> RunTtsTestAsync(string testText)
    {
        _log.Info("tts_test.start", "开始 TTS 配置测试",
            new() { ["test_text"] = testText });

        var args = $"-m src.wanwan_client.main run-tts-text \"{testText}\" --no-play";
        var startInfo = new ProcessStartInfo
        {
            FileName = _pythonPath,
            Arguments = args,
            WorkingDirectory = _projectRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };

        using var process = new Process { StartInfo = startInfo };

        var stdoutBuilder = new StringBuilder();
        var stderrBuilder = new StringBuilder();

        process.OutputDataReceived += (_, e) =>
        {
            if (e.Data != null) stdoutBuilder.AppendLine(e.Data);
        };

        process.ErrorDataReceived += (_, e) =>
        {
            if (e.Data != null) stderrBuilder.AppendLine(e.Data);
        };

        try
        {
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();

            var completed = process.WaitForExit(60000);
            if (!completed)
            {
                try { process.Kill(); } catch { }
                var partialStdout = stdoutBuilder.ToString().Trim();
                var partialStderr = stderrBuilder.ToString().Trim();
                _log.Error("tts_test.timeout", "TTS 测试超时（60 秒）");
                return new TtsTestResult
                {
                    ErrorCode = "TIMEOUT",
                    ErrorMessage = "TTS 请求超时（60 秒），请检查网络或 API 地址",
                    StdoutPreview = TruncateForLog(partialStdout, 300),
                    StderrPreview = TruncateForLog(partialStderr, 300),
                };
            }

            var stdout = stdoutBuilder.ToString().Trim();
            var stderr = stderrBuilder.ToString().Trim();
            var stdoutPreview = TruncateForLog(stdout, 500);
            var stderrPreview = TruncateForLog(stderr, 500);

            if (!string.IsNullOrEmpty(stderr))
            {
                _log.Warn("tts_test.stderr", "TTS 测试 stderr",
                    new() { ["stderr"] = stderr, ["exit_code"] = process.ExitCode });
            }

            if (process.ExitCode != 0)
            {
                var detailError = ExtractErrorFromStdout(stdout);
                _log.Error("tts_test.failed", "TTS 测试失败：退出码非 0",
                    new() { ["exit_code"] = process.ExitCode, ["stderr_preview"] = stderrPreview,
                        ["parsed_error"] = detailError });
                return new TtsTestResult
                {
                    ErrorCode = "PROCESS_FAILED",
                    ErrorMessage = detailError
                        ?? (string.IsNullOrEmpty(stderr)
                            ? $"Python 进程异常退出（退出码 {process.ExitCode}）"
                            : $"Python 进程异常退出：{TruncateForDisplay(stderr, 200)}"),
                    StdoutPreview = stdoutPreview,
                    StderrPreview = stderrPreview,
                };
            }

            if (string.IsNullOrWhiteSpace(stdout))
            {
                _log.Error("tts_test.empty_stdout", "TTS 测试 stdout 为空");
                return new TtsTestResult
                {
                    ErrorCode = "EMPTY_OUTPUT",
                    ErrorMessage = "Python 后端无输出，请检查 Python 环境和依赖",
                    StderrPreview = stderrPreview,
                };
            }

            using var doc = JsonDocument.Parse(stdout);
            var root = doc.RootElement;

            var ttsSection = root.TryGetProperty("tts", out var ttsProp) ? ttsProp : default;
            if (ttsSection.ValueKind == JsonValueKind.Undefined)
            {
                _log.Error("tts_test.parse_failed", "TTS 测试返回中缺少 tts 字段",
                    new() { ["stdout_preview"] = stdoutPreview });
                return new TtsTestResult
                {
                    ErrorCode = "INVALID_JSON",
                    ErrorMessage = "Python 返回了数据但 JSON 结构不符合预期（缺少 tts 字段）",
                    StdoutPreview = stdoutPreview,
                };
            }

            var status = ttsSection.TryGetProperty("status", out var statusProp)
                ? statusProp.GetString() : null;

            var errorInfo = ttsSection.TryGetProperty("error", out var errProp) && errProp.ValueKind == JsonValueKind.Object
                ? (JsonElement?)errProp : null;
            var errorCode = errorInfo?.TryGetProperty("code", out var codeProp) == true
                ? codeProp.GetString() : null;
            var errorMessage = errorInfo?.TryGetProperty("message", out var msgProp) == true
                ? msgProp.GetString() : null;

            if (status != "success")
            {
                var reason = !string.IsNullOrEmpty(errorMessage)
                    ? errorMessage
                    : (!string.IsNullOrEmpty(errorCode) ? $"错误码: {errorCode}" : "未知原因");
                _log.Error("tts_test.failed", "TTS 测试失败：status 非 success",
                    new() { ["status"] = status, ["error_code"] = errorCode, ["error_message"] = errorMessage });
                return new TtsTestResult
                {
                    ErrorCode = errorCode ?? "TTS_FAILED",
                    ErrorMessage = $"TTS 合成失败：{reason}",
                    StdoutPreview = stdoutPreview,
                    StderrPreview = stderrPreview,
                };
            }

            if (errorInfo != null)
            {
                var detail = !string.IsNullOrEmpty(errorMessage) ? errorMessage : "error 字段存在但无详细信息";
                _log.Warn("tts_test.error_present", "TTS status=success 但 error 字段非空",
                    new() { ["error_code"] = errorCode, ["error_message"] = errorMessage });
                return new TtsTestResult
                {
                    ErrorCode = errorCode ?? "TTS_PARTIAL_ERROR",
                    ErrorMessage = $"TTS 返回成功但有异常信息：{detail}",
                    StdoutPreview = stdoutPreview,
                    StderrPreview = stderrPreview,
                };
            }

            var audioRefValue = ttsSection
                .TryGetProperty("payload", out var payloadProp) ? payloadProp : default;
            if (audioRefValue.ValueKind == JsonValueKind.Object)
                audioRefValue = audioRefValue.TryGetProperty("output", out var outputProp) ? outputProp : default;
            if (audioRefValue.ValueKind == JsonValueKind.Object)
                audioRefValue = audioRefValue.TryGetProperty("audio_ref", out var refProp) ? refProp : default;
            if (audioRefValue.ValueKind == JsonValueKind.Object)
                audioRefValue = audioRefValue.TryGetProperty("value", out var valueProp) ? valueProp : default;

            var audioPath = audioRefValue.ValueKind == JsonValueKind.String
                ? audioRefValue.GetString() : null;

            if (string.IsNullOrEmpty(audioPath))
            {
                _log.Error("tts_test.no_audio_path", "TTS 返回 success 但缺少音频路径",
                    new() { ["stdout_preview"] = stdoutPreview });
                return new TtsTestResult
                {
                    ErrorCode = "NO_AUDIO_PATH",
                    ErrorMessage = "TTS 合成成功但未返回音频文件路径",
                    StdoutPreview = stdoutPreview,
                    StderrPreview = stderrPreview,
                };
            }

            _log.Info("tts_test.success", "TTS 测试成功",
                new() { ["tts_audio_path"] = audioPath });
            return new TtsTestResult
            {
                AudioPath = audioPath,
                StdoutPreview = stdoutPreview,
            };
        }
        catch (JsonException ex)
        {
            var partialStdout = stdoutBuilder.ToString().Trim();
            _log.Error("tts_test.parse_failed", "TTS 测试 JSON 解析失败",
                new() { ["error"] = ex.Message });
            return new TtsTestResult
            {
                ErrorCode = "JSON_PARSE_ERROR",
                ErrorMessage = "Python 输出无法解析为 JSON，请查看日志",
                StdoutPreview = TruncateForLog(partialStdout, 300),
            };
        }
        catch (Exception ex)
        {
            var partialStdout = stdoutBuilder.ToString().Trim();
            var partialStderr = stderrBuilder.ToString().Trim();
            _log.Error("tts_test.exception", "TTS 测试异常",
                new() { ["error"] = ex.Message, ["stack_trace"] = ex.StackTrace });
            return new TtsTestResult
            {
                ErrorCode = "EXCEPTION",
                ErrorMessage = $"TTS 测试异常：{ex.Message}",
                StdoutPreview = TruncateForLog(partialStdout, 300),
                StderrPreview = TruncateForLog(partialStderr, 300),
            };
        }
    }

    private static string TruncateForLog(string text, int maxLength)
    {
        return text.Length <= maxLength ? text : text[..maxLength];
    }

    private static string TruncateForDisplay(string text, int maxLength)
    {
        return text.Length <= maxLength ? text : text[..maxLength] + "...";
    }

    private static string? ExtractErrorFromStdout(string stdout)
    {
        if (string.IsNullOrWhiteSpace(stdout)) return null;
        try
        {
            using var doc = JsonDocument.Parse(stdout);
            var tts = doc.RootElement.TryGetProperty("tts", out var t) ? t : default;
            if (tts.ValueKind != JsonValueKind.Object) return null;

            var errorObj = tts.TryGetProperty("error", out var e) && e.ValueKind == JsonValueKind.Object ? e : default;
            if (errorObj.ValueKind == JsonValueKind.Object)
            {
                var msg = errorObj.TryGetProperty("message", out var m) ? m.GetString() : null;
                if (!string.IsNullOrEmpty(msg)) return msg;

                var code = errorObj.TryGetProperty("code", out var c) ? c.GetString() : null;
                if (!string.IsNullOrEmpty(code)) return $"Provider 错误码: {code}";
            }

            var status = tts.TryGetProperty("status", out var s) ? s.GetString() : null;
            if (status == "failed") return "TTS 合成失败（查看日志获取详情）";

            return null;
        }
        catch { return null; }
    }

    private VoiceChainResult? TryParseVoiceChainResult(string stdout)
    {
        if (string.IsNullOrWhiteSpace(stdout))
        {
            _log.Error("python.result", "stdout 为空，无法解析 Python 返回结果");
            return null;
        }

        try
        {
            var result = JsonSerializer.Deserialize<VoiceChainResult>(stdout);
            if (result == null)
            {
                _log.Error("python.result", "JSON 解析结果为 null",
                    new() { ["stdout_length"] = stdout.Length });
                return null;
            }

            return result;
        }
        catch (JsonException ex)
        {
            _log.Error("python.result", "JSON 解析失败",
                new() { ["error"] = ex.Message, ["stdout_preview"] = stdout.Length > 1000 ? stdout[..1000] : stdout });
            return null;
        }
    }
}
