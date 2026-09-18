using System.IO;
using System.Text.Json;
using WanwanDesktop.Models;

namespace WanwanDesktop.Services;

/// <summary>
/// 只读访问 Python ConversationStore 生成的 JSONL。
/// 本阶段不提供删除或修改，避免桌面 UI 成为第二套写入实现。
/// </summary>
public sealed class ConversationHistoryService
{
    private readonly string _conversationsDirectory;
    private readonly DesktopLogService _log;

    public ConversationHistoryService(string projectRoot, DesktopLogService log)
    {
        _conversationsDirectory = Path.Combine(projectRoot, "data", "conversations");
        _log = log;
    }

    /// <summary>
    /// 从最新日期文件开始、从每个文件最后一行向前读取，返回最近的记录。
    /// 单行损坏只跳过该行，不影响其余历史显示。
    /// </summary>
    public IReadOnlyList<ConversationHistoryItem> LoadRecent(int limit = 50)
    {
        var items = new List<ConversationHistoryItem>();
        if (limit <= 0 || !Directory.Exists(_conversationsDirectory))
            return items;

        var files = Directory.EnumerateFiles(_conversationsDirectory, "*.jsonl")
            .OrderByDescending(Path.GetFileName)
            .ToList();

        foreach (var file in files)
        {
            string[] lines;
            try
            {
                lines = File.ReadAllLines(file);
            }
            catch (Exception ex)
            {
                _log.Warn("history.file_read_failed", "读取会话历史文件失败",
                    new() { ["file"] = file, ["error"] = ex.Message });
                continue;
            }

            for (var index = lines.Length - 1; index >= 0 && items.Count < limit; index--)
            {
                if (string.IsNullOrWhiteSpace(lines[index]))
                    continue;

                try
                {
                    var item = JsonSerializer.Deserialize<ConversationHistoryItem>(lines[index]);
                    if (item != null)
                        items.Add(item);
                }
                catch (JsonException ex)
                {
                    _log.Warn("history.line_parse_failed", "跳过无法解析的会话历史记录",
                        new() { ["file"] = file, ["line_number"] = index + 1, ["error"] = ex.Message });
                }
            }

            if (items.Count >= limit)
                break;
        }

        _log.Info("history.loaded", "会话历史加载完成", new() { ["count"] = items.Count });
        return items;
    }
}
