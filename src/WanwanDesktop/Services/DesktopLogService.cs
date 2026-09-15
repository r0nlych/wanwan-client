using System;
using System.IO;
using System.Text.Json;
using WanwanDesktop.Infrastructure;

namespace WanwanDesktop.Services;

public class DesktopLogService
{
    // 进程级共享实例：App、MainWindow 及其下游服务统一使用它，
    // 保证全进程只有一个日志门面，不再各建实例写同一个文件
    private static readonly Lazy<DesktopLogService> _shared = new(() => new DesktopLogService());

    public static DesktopLogService Shared => _shared.Value;

    // 进程级文件写锁：即使历史代码里再出现第二个实例，
    // 对同一个日志文件的写入也不会交错损坏
    private static readonly object _fileWriteLock = new();

    // 敏感字段脱敏名单（小写包含匹配），禁止把 Key / Token / 口令原文写入日志
    private static readonly string[] _sensitiveFragments =
    {
        "api_key", "apikey", "api-key",
        "secret",
        "authorization",
        "access_token", "refresh_token",
        "password", "passwd",
    };

    private const string RedactedValue = "***redacted***";

    private readonly string _logDir;
    private readonly string _logPath;

    public DesktopLogService()
    {
        // 日志目录基于统一的项目根目录，不再各自向上查找 AGENTS.md
        var projectRoot = ProjectPaths.ProjectRoot;

        _logDir = Path.Combine(projectRoot, "logs");
        _logPath = Path.Combine(_logDir, "wanwan_desktop.log");

        // 目录创建失败不能让构造函数抛异常（异常处理器还要依赖日志服务）
        try
        {
            Directory.CreateDirectory(_logDir);
        }
        catch
        {
            // 路径不可用时保留 _logPath，写入时还会再做一次安全兜底
        }
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
        // 日志写入整体兜底：任何失败都吞掉，绝不能反过来触发全局异常处理
        try
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
                    entry[kv.Key] = IsSensitive(kv.Key) ? RedactedValue : kv.Value;
                }
            }

            var line = JsonSerializer.Serialize(entry);

            lock (_fileWriteLock)
            {
                File.AppendAllText(_logPath, line + Environment.NewLine);
            }
        }
        catch
        {
            // 序列化失败、文件被占用、磁盘不可写等情况均静默放弃本条日志
        }
    }

    private static bool IsSensitive(string key)
    {
        if (string.IsNullOrEmpty(key)) return false;

        var lowered = key.ToLowerInvariant();
        foreach (var fragment in _sensitiveFragments)
        {
            if (lowered.Contains(fragment, StringComparison.Ordinal))
                return true;
        }

        return false;
    }

    public string GetLogDir() => _logDir;
}
