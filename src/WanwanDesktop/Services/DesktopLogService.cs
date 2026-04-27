using System;
using System.IO;
using System.Text.Json;

namespace WanwanDesktop.Services;

public class DesktopLogService
{
    private readonly string _logDir;
    private readonly string _logPath;
    private readonly object _lock = new();

    public DesktopLogService()
    {
        string projectRoot = AppDomain.CurrentDomain.BaseDirectory;
        while (!string.IsNullOrEmpty(projectRoot) && !File.Exists(Path.Combine(projectRoot, "AGENTS.md")))
        {
            var parent = Directory.GetParent(projectRoot);
            if (parent == null) break;
            projectRoot = parent.FullName;
        }

        _logDir = Path.Combine(projectRoot, "logs");
        _logPath = Path.Combine(_logDir, "wanwan_desktop.log");
        Directory.CreateDirectory(_logDir);
    }

    public void Info(string eventName, string message, Dictionary<string, object?>? extra = null)
    {
        Write("info", eventName, message, extra);
    }

    public void Error(string eventName, string message, Dictionary<string, object?>? extra = null)
    {
        Write("error", eventName, message, extra);
    }

    public void Warn(string eventName, string message, Dictionary<string, object?>? extra = null)
    {
        Write("warn", eventName, message, extra);
    }

    private void Write(string level, string eventName, string message, Dictionary<string, object?>? extra)
    {
        var entry = new Dictionary<string, object?>
        {
            ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:sszzz"),
            ["level"] = level,
            ["event"] = eventName,
            ["message"] = message,
        };

        if (extra != null)
        {
            foreach (var kv in extra)
            {
                if (kv.Key != "api_key" && kv.Key != "secret")
                    entry[kv.Key] = kv.Value;
            }
        }

        string line;
        try
        {
            line = JsonSerializer.Serialize(entry);
        }
        catch
        {
            line = $"{{\"timestamp\":\"{DateTime.Now:O}\",\"level\":\"error\",\"event\":\"log_serialize_failed\",\"message\":\"{message}\"}}";
        }

        lock (_lock)
        {
            File.AppendAllText(_logPath, line + Environment.NewLine);
        }
    }

    public string GetLogDir() => _logDir;
}
