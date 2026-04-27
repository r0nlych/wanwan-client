using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows;
using WanwanDesktop.Services;

namespace WanwanDesktop.Windows;

public partial class LogWindow : Window
{
    private const int MaxLines = 300;
    private readonly string _debugLogPath;
    private readonly string _desktopLogPath;
    private readonly string _logDir;
    private string _currentLogPath;

    public LogWindow()
    {
        InitializeComponent();

        string projectRoot = AppDomain.CurrentDomain.BaseDirectory;
        while (!string.IsNullOrEmpty(projectRoot) && !File.Exists(Path.Combine(projectRoot, "AGENTS.md")))
        {
            var parent = Directory.GetParent(projectRoot);
            if (parent == null) break;
            projectRoot = parent.FullName;
        }

        _logDir = Path.Combine(projectRoot, "logs");
        Directory.CreateDirectory(_logDir);

        _debugLogPath = Path.Combine(_logDir, "wanwan_debug.log");
        _desktopLogPath = Path.Combine(_logDir, "wanwan_desktop.log");
        _currentLogPath = _debugLogPath;

        DebugLogRadio.IsChecked = true;

        Loaded += (_, _) => RefreshLog();
    }

    private void LogRadio_Checked(object sender, RoutedEventArgs e)
    {
        _currentLogPath = DebugLogRadio.IsChecked == true ? _debugLogPath : _desktopLogPath;
        if (IsLoaded)
            RefreshLog();
    }

    private void Refresh_Click(object sender, RoutedEventArgs e) => RefreshLog();

    private void ClearLog_Click(object sender, RoutedEventArgs e)
    {
        var isDebug = DebugLogRadio.IsChecked == true;
        var logName = isDebug ? "Python 调试日志" : "桌面端日志";
        var targetPath = isDebug ? _debugLogPath : _desktopLogPath;

        var confirm = MessageBox.Show(
            $"确认清空 {logName}？",
            "确认清空",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (confirm != MessageBoxResult.Yes)
            return;

        try
        {
            if (File.Exists(targetPath))
            {
                File.WriteAllText(targetPath, "");
            }

            if (_currentLogPath == targetPath)
                RefreshLog();
        }
        catch (Exception ex)
        {
            MessageBox.Show($"清空日志失败: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OpenFolder_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (Directory.Exists(_logDir))
                Process.Start("explorer.exe", _logDir);
            else
                MessageBox.Show($"日志目录不存在: {_logDir}", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"打开文件夹失败: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void Close_Click(object sender, RoutedEventArgs e) => Close();

    private void RefreshLog()
    {
        if (LogTextBox == null) return;

        try
        {
            if (string.IsNullOrEmpty(_currentLogPath) || !File.Exists(_currentLogPath))
            {
                LogTextBox.Text = "暂无日志";
                return;
            }

            var allLines = File.ReadAllLines(_currentLogPath);
            var tailLines = allLines.Skip(Math.Max(0, allLines.Length - MaxLines)).ToArray();

            LogTextBox.Text = tailLines.Length > 0
                ? string.Join(Environment.NewLine, tailLines)
                : "暂无日志";

            LogTextBox.ScrollToEnd();
        }
        catch (Exception ex)
        {
            LogTextBox.Text = $"读取日志失败: {ex.Message}";
        }
    }
}
