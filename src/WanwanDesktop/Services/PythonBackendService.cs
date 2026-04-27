using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using WanwanDesktop.Models;

namespace WanwanDesktop.Services;

public class PythonBackendService
{
    private readonly DesktopLogService _log;
    private readonly string _projectRoot;
    private readonly string _pythonPath;

    public PythonBackendService(DesktopLogService log)
    {
        _log = log;

        _projectRoot = AppDomain.CurrentDomain.BaseDirectory;
        while (!string.IsNullOrEmpty(_projectRoot) && !File.Exists(Path.Combine(_projectRoot, "AGENTS.md")))
        {
            var parent = Directory.GetParent(_projectRoot);
            if (parent == null) break;
            _projectRoot = parent.FullName;
        }

        _pythonPath = Path.Combine(_projectRoot, ".venv", "Scripts", "python.exe");
        if (!File.Exists(_pythonPath))
        {
            _pythonPath = "python";
        }
    }

    public async Task<VoiceChainResult?> RunVoiceChainAsync(string audioPath)
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
            await process.WaitForExitAsync();

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
                return null;
            }

            VoiceChainResult? result;
            try
            {
                result = JsonSerializer.Deserialize<VoiceChainResult>(stdout);
                if (result == null)
                {
                    _log.Error("python.result", "JSON 解析结果为 null",
                        new() { ["stdout_length"] = stdout.Length });
                    return null;
                }
            }
            catch (JsonException ex)
            {
                _log.Error("python.result", "JSON 解析失败",
                    new() { ["error"] = ex.Message, ["stdout_preview"] = stdout.Length > 1000 ? stdout[..1000] : stdout });
                return null;
            }

            _log.Info("python.result", "Python 后端返回成功",
                new()
                {
                    ["status"] = result.Status,
                    ["trace_id"] = result.TraceId,
                    ["stt_text"] = result.Final?.SttText ?? result.Final?.LlmReplyText,
                    ["conversation_saved"] = result.ConversationSave?.Saved,
                });

            return result;
        }
        catch (Exception ex)
        {
            _log.Error("python.exception", "调用 Python 异常",
                new() { ["error"] = ex.Message, ["stack_trace"] = ex.StackTrace });
            return null;
        }
    }

    public string GetProjectRoot() => _projectRoot;
}
