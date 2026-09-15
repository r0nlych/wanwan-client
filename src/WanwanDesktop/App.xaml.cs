using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;
using WanwanDesktop.Services;

namespace WanwanDesktop;

public partial class App : Application
{
    // 产品界面正式名称，所有异常弹窗标题统一使用
    private const string ProductName = "晚晚";

    // 全局兜底复用进程级共享日志服务，不引入第二套日志体系
    private readonly DesktopLogService _globalLog = DesktopLogService.Shared;

    // 防止退出过程中连续异常导致重复弹窗/重复 Shutdown
    private bool _isShuttingDown;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // 注册三层未处理异常：UI 线程、非 UI 线程、未被观察的 Task 异常
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnAppDomainUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;

        try
        {
            var mainWindow = new MainWindow();
            mainWindow.Show();
        }
        catch (Exception ex)
        {
            // 主窗口构造失败属于启动致命错误：记录、提示后安全退出
            WriteGlobalError("app.startup_failed", "主窗口启动失败", ex);
            ShowBlockingMessage($"晚晚启动失败：{ex.Message}");
            Shutdown(1);
        }
    }

    private void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        // 先标记 Handled，阻止 WPF 默认的未处理异常崩溃对话框，
        // 让应用走“可恢复继续”或“受控退出”两条明确路径，而不是直接崩掉
        e.Handled = true;

        WriteGlobalError("app.ui_unhandled", "UI 线程发生未处理异常", e.Exception);

        if (!_isShuttingDown && IsRecoverable(e.Exception))
        {
            // 仅白名单内、明确不会破坏内存状态的异常允许继续运行
            ShowBlockingMessage(
                $"晚晚遇到一个可恢复的问题：\n\n{e.Exception.Message}\n\n可以继续使用；若重复出现，请查看日志。");
            return;
        }

        // 未知异常不保证进程状态仍一致：提示后受控退出，避免在损坏状态下继续
        BeginSafeShutdown(e.Exception);
    }

    private void OnAppDomainUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        // 非 UI 线程异常：终止路径上只做尽力日志落盘，
        // 不弹模态窗口——弹窗可能阻塞进程正常退出
        if (e.ExceptionObject is Exception ex)
        {
            WriteGlobalError(
                "app.domain_unhandled",
                $"AppDomain 未处理异常（IsTerminating={e.IsTerminating}）",
                ex);
            return;
        }

        WriteGlobalError(
            "app.domain_unhandled",
            $"AppDomain 抛出非 Exception 对象：{e.ExceptionObject}",
            null);
    }

    private void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        // 后台 Task 的未观察异常：记录后标记已观察，避免升级为进程崩溃；
        // 不弹窗打扰，主界面状态由各自调用链的 finally 负责恢复
        WriteGlobalError("app.task_unobserved", "后台任务发生未观察异常", e.Exception);
        e.SetObserved();
    }

    /// <summary>
    /// 明确可恢复的异常白名单：仅限临时性 IO/超时类故障，
    /// 这类异常发生后本应用的内存状态（录音标志、链路标志）不依赖出错资源。
    /// 其余异常一律按不可恢复处理。
    /// </summary>
    private static bool IsRecoverable(Exception ex)
    {
        return ex is IOException or TimeoutException;
    }

    private void BeginSafeShutdown(Exception ex)
    {
        if (_isShuttingDown) return;
        _isShuttingDown = true;

        try
        {
            ShowBlockingMessage(
                $"晚晚遇到内部错误，为避免在异常状态下继续运行，将安全退出。\n\n" +
                $"错误类型：{ex.GetType().Name}\n详细信息已写入日志。");
        }
        finally
        {
            Shutdown(1);
        }
    }

    private void WriteGlobalError(string eventName, string message, Exception? ex)
    {
        // 异常处理器自身绝不能再抛异常，否则会触发二次崩溃
        try
        {
            _globalLog.Error(
                eventName,
                message,
                ex == null
                    ? null
                    : new Dictionary<string, object?>
                    {
                        ["error"] = ex.Message,
                        ["exception_type"] = ex.GetType().FullName,
                        ["stack_trace"] = ex.StackTrace,
                    });
        }
        catch
        {
            // 日志写入失败时直接放弃，保证兜底链路自身不抛出
        }
    }

    private void ShowBlockingMessage(string text)
    {
        try
        {
            MessageBox.Show(
                text,
                ProductName,
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
        }
        catch
        {
            // 会话正在结束等极端场景下弹窗也可能失败，忽略以保证处理器不抛异常
        }
    }
}
