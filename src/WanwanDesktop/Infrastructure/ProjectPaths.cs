using System;
using System.IO;

namespace WanwanDesktop.Infrastructure;

/// <summary>
/// 桌面端统一的项目路径定位工具。
/// 之前各服务各自向上查找 AGENTS.md，逻辑重复了 6 处；
/// 这里收口为唯一实现，并缓存查找结果，避免重复扫目录。
/// </summary>
public static class ProjectPaths
{
    // AGENTS.md 固定放在仓库根目录，作为"已到达项目根"的判定标志
    private const string ROOT_MARKER_FILE = "AGENTS.md";

    // 查找结果全局只算一次：进程生命周期内项目根不会变化
    private static readonly Lazy<string> _projectRoot = new(FindProjectRoot);

    /// <summary>
    /// 仓库根目录（包含 AGENTS.md 的目录）。
    /// data、logs、.venv 等运行时路径都基于它拼接。
    /// </summary>
    public static string ProjectRoot => _projectRoot.Value;

    /// <summary>
    /// 从程序运行目录逐级向上查找，直到发现 AGENTS.md。
    /// 找不到时停在基目录（与旧实现行为保持一致，不抛异常）。
    /// </summary>
    private static string FindProjectRoot()
    {
        var current = AppDomain.CurrentDomain.BaseDirectory;

        while (!string.IsNullOrEmpty(current)
               && !File.Exists(Path.Combine(current, ROOT_MARKER_FILE)))
        {
            var parent = Directory.GetParent(current);
            if (parent == null) break;
            current = parent.FullName;
        }

        return current;
    }
}
