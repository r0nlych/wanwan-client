using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Microsoft.Win32;
using WanwanDesktop.Models;
using WanwanDesktop.Services;
using WanwanDesktop.Windows;

namespace WanwanDesktop;

public partial class MainWindow : Window
{
    // 收起 / 展开的目标窗口尺寸。XAML 里的初始 Width/Height 必须与收起值一致，
    // 改这里要同步改 MainWindow.xaml 的 Width/Height。
    private const double CollapsedWindowWidth = 260;
    private const double CollapsedWindowHeight = 300;
    private const double ExpandedWindowWidth = 420;
    private const double ExpandedWindowHeight = 520;

    // 主操作按钮的两种图标：麦克风（可开始录音）/ 停止（停止录音、停止播放）
    private const string MicGlyphCode = "\uE720";
    private const string StopGlyphCode = "\uE71A";

    // 成功后停留多久再自动回到空闲，避免“完成”一闪而过
    private static readonly TimeSpan SuccessDwell = TimeSpan.FromMilliseconds(1600);

    private readonly DesktopLogService _log;
    private readonly PythonBackendService _python;
    private readonly AudioRecorderService _recorder;
    private readonly AudioPlayerService _player;
    private readonly ConversationHistoryService _history;
    private LogWindow? _logWindow;
    private SettingsWindow? _settingsWindow;
    private bool _isRunning;
    private bool _isShuttingDown;
    private bool _isInputPanelExpanded;
    private WanwanCharacterState _currentUiState = WanwanCharacterState.Idle;
    private string _currentSessionId = BuildDesktopSessionId();
    private bool _continuousContextEnabled;

    // AudioPlayerService.PlayAsync() 只能告诉你“播放结束了”，无法区分是被 Stop() 打断还是自然播完。
    // 因此在这里加一个最小标记：点停止播放前置位，播放返回后据此决定走“空闲”还是“完成”。
    // 不为这一个判断去改播放器服务。
    private bool _stopPlaybackRequested;

    // 界面状态版本号。每次 ApplyUiState 都会自增，
    // 让此前排队的“延迟回到空闲”旧任务自动失效，避免旧任务覆盖新一轮交互状态。
    private int _uiStateVersion;

    // 气泡错误操作区当前挂着的恢复动作，以及它出现时的状态版本号。
    // 版本号用于丢弃过期点击：新一轮操作清空操作区后，旧按钮即使被点到也不再执行。
    private RecoverableAction _errorAction = RecoverableAction.None;
    private int _errorActionVersion;

    // “重试文本”只重试最后一次提交失败的原文，不读取输入框当前内容。
    private string? _lastFailedText;

    // “重试播放”只重放最后一次已通过校验的本地 WAV，重试不会再调用 LLM / TTS。
    private string? _lastPlayableWavPath;

    public MainWindow()
    {
        InitializeComponent();

        // 复用进程级共享日志服务，保证 App 全局兜底与主窗口写入同一份日志
        _log = DesktopLogService.Shared;
        _python = new PythonBackendService(_log);
        _recorder = new AudioRecorderService(_log);
        _player = new AudioPlayerService(_log);
        _history = new ConversationHistoryService(_python.GetProjectRoot(), _log);

        InitializeInputPanel();

        _log.Info("app.start", "WPF 桌宠启动",
            new() { ["session_id"] = _currentSessionId, ["continuous_context"] = false });
    }

    private void Window_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton == MouseButton.Left)
            DragMove();
    }

    // ======================== UI 状态 ========================

    /// <summary>
    /// 界面状态的唯一入口。角色图片、Chip 文案与圆点颜色、主操作按钮的图标/颜色/可用性、
    /// 取消按钮可见性、发送与历史按钮的禁用状态，全部在这里集中决定。
    ///
    /// 事件处理方法只负责“发生了什么事”，不再各自散落图片路径和颜色。
    /// statusText 传 null 时使用该状态的默认文案，传具体文案时用于保留明确的错误原因。
    /// </summary>
    private void ApplyUiState(WanwanCharacterState state, string? statusText = null)
    {
        // 非 UI 线程调用时切回 UI 线程，避免调用方到处写 Dispatcher
        if (!Dispatcher.CheckAccess())
        {
            Dispatcher.Invoke(() => ApplyUiState(state, statusText));
            return;
        }

        // 任何一次状态切换都让此前排队的“延迟回到空闲”任务失效
        _uiStateVersion++;
        _currentUiState = state;

        // 角色图片：路径仍集中在 CharacterAssets，页面里不出现素材路径
        SetCharacterState(state);

        // 状态 Chip：文案 + 圆点颜色
        StatusLabel.Text = statusText ?? GetDefaultStatusText(state);
        StatusDot.Fill = GetStatusDotBrush(state);

        // 主操作按钮：图标、底色、是否可点
        switch (state)
        {
            case WanwanCharacterState.Listening:
                // 录音中：红色停止按钮，可点（再次点击 = 停止录音并发送）
                SetMicButton(StopGlyphCode, "ErrorBrush", enabled: true, tooltip: "点击停止录音并发送");
                break;

            case WanwanCharacterState.Speaking:
                // 播放中：蓝色停止按钮，可点（点击 = 停止播放）
                SetMicButton(StopGlyphCode, "PrimaryBrush", enabled: true, tooltip: "点击停止播放");
                break;

            case WanwanCharacterState.Processing:
                // 处理中：禁用，防止重复录音/重复提交
                SetMicButton(MicGlyphCode, "DisabledBackgroundBrush", enabled: false, tooltip: "处理中，请稍候");
                break;

            case WanwanCharacterState.Success:
                // 完成停留期间同样禁用，避免和即将到来的空闲态抢点击
                SetMicButton(MicGlyphCode, "DisabledBackgroundBrush", enabled: false, tooltip: "完成");
                break;

            case WanwanCharacterState.Error:
                // 出错后立即可重试，下一次点击录音时状态自然回到正常
                SetMicButton(MicGlyphCode, "PrimaryBrush", enabled: true, tooltip: "点击开始录音");
                break;

            default:
                SetMicButton(MicGlyphCode, "PrimaryBrush", enabled: true, tooltip: "点击开始录音");
                break;
        }

        // 取消录音入口只在录音中出现，其他状态一律收起
        CancelRecordButton.Visibility = state == WanwanCharacterState.Listening
            ? Visibility.Visible
            : Visibility.Collapsed;

        // 文本发送与历史按钮都按当前运行状态统一刷新。
        RefreshTextInputAvailability();
    }

    /// <summary>
    /// 主操作按钮的图标 / 底色 / 可用性统一设置处。
    /// 颜色从 XAML 资源里按 key 取，不在代码里写死十六进制色值。
    /// </summary>
    private void SetMicButton(string glyph, string brushKey, bool enabled, string tooltip)
    {
        MicGlyph.Text = glyph;
        MicButton.Background = (Brush)FindResource(brushKey);
        MicButton.Foreground = enabled
            ? Brushes.White
            : (Brush)FindResource("DisabledForegroundBrush");
        MicButton.IsEnabled = enabled;
        MicButton.ToolTip = tooltip;
    }

    /// <summary>
    /// 文本输入区的可用性只由当前状态、运行标记和输入内容决定。
    /// 这样录音、文本链路和播放共用同一个忙碌门禁，不会出现按钮看似可点却重复提交。
    /// </summary>
    private void RefreshTextInputAvailability()
    {
        var inputAllowed = _currentUiState is WanwanCharacterState.Idle
            or WanwanCharacterState.Listening
            or WanwanCharacterState.Error;
        MessageInput.IsEnabled = inputAllowed;

        // 历史窗口只在空闲/可恢复错误状态打开，避免遮断正在进行的录音或播放操作。
        HistoryButton.IsEnabled = (_currentUiState is WanwanCharacterState.Idle or WanwanCharacterState.Error)
            && !_isRunning
            && !_recorder.IsRecording
            && !_player.IsPlaying;

        var sendStateAllowed = _currentUiState is WanwanCharacterState.Idle
            or WanwanCharacterState.Error;
        SendButton.IsEnabled = sendStateAllowed
            && !_isRunning
            && !_recorder.IsRecording
            && !_player.IsPlaying
            && !string.IsNullOrWhiteSpace(MessageInput.Text);
    }

    private static string GetDefaultStatusText(WanwanCharacterState state) => state switch
    {
        WanwanCharacterState.Listening => "正在听…",
        WanwanCharacterState.Processing => "处理中…",
        WanwanCharacterState.Speaking => "播放中…",
        WanwanCharacterState.Success => "完成",
        WanwanCharacterState.Error => "失败",
        _ => "空闲中",
    };

    /// <summary>
    /// Chip 圆点颜色：空闲/完成绿、录音警示橙、处理与播放进行中蓝、出错红。
    /// </summary>
    private Brush GetStatusDotBrush(WanwanCharacterState state) => state switch
    {
        WanwanCharacterState.Listening => (Brush)FindResource("WarningBrush"),
        WanwanCharacterState.Processing => (Brush)FindResource("PrimaryBrush"),
        WanwanCharacterState.Speaking => (Brush)FindResource("PrimaryBrush"),
        WanwanCharacterState.Error => (Brush)FindResource("ErrorBrush"),
        _ => (Brush)FindResource("SuccessBrush"),
    };

    /// <summary>
    /// 成功后停留一小段时间再回到空闲。
    /// 用版本号做守卫：只要期间发生过任何一次状态切换（例如用户已经开始下一轮录音），
    /// 本次延迟就放弃，不会把新状态覆盖成空闲。
    /// </summary>
    private async void ScheduleReturnToIdle()
    {
        var version = _uiStateVersion;

        await Task.Delay(SuccessDwell);

        if (version != _uiStateVersion)
            return;

        // 期间用户可能已经通过右键菜单开始录音或播放，此时不要抢占
        if (_isRunning || _recorder.IsRecording || _player.IsPlaying)
            return;

        ApplyUiState(WanwanCharacterState.Idle);
    }

    private void SetResult(string text)
    {
        Dispatcher.Invoke(() =>
        {
            ResultLabel.Text = text;
            ResultLabel.ToolTip = null;
            // 空文本时把气泡整体（含尾巴）收起，避免窗口顶部留一个空白卡片
            var visible = !string.IsNullOrEmpty(text);
            BubbleArea.Visibility = visible ? Visibility.Visible : Visibility.Collapsed;
            // 气泡都没了，错误操作区不能单独留在窗口上
            if (!visible)
                ClearErrorActionsCore();
        });
    }

    // ======================== Recoverable Error ========================

    /// <summary>
    /// 气泡内可恢复错误的操作类型。只描述“用户点下去能做什么”，
    /// 不引入命令框架、依赖注入或新的状态管理库。
    /// </summary>
    private enum RecoverableAction
    {
        None,
        Dismiss,
        RetryText,
        RetryPlayback,
        OpenSettings,
    }

    /// <summary>
    /// 可恢复错误的统一入口。集中决定：错误角色图、Chip 文案、气泡正文、操作按钮文字与可见性、
    /// 当前可执行的恢复动作。各处 catch 只调用它，不再各自修改多个控件。
    /// bubbleText 只放“用户能看懂的一句话”；完整技术细节写日志，或放进 detail 作为气泡悬停提示。
    /// </summary>
    private void ShowRecoverableError(
        string statusText,
        string bubbleText,
        RecoverableAction action,
        string? detail = null,
        string? retryLabel = null)
    {
        if (!Dispatcher.CheckAccess())
        {
            Dispatcher.Invoke(() => ShowRecoverableError(statusText, bubbleText, action, detail, retryLabel));
            return;
        }

        // 角色图 / Chip 文案 / 圆点颜色 / 主按钮语义仍然走同一个状态入口
        ApplyUiState(WanwanCharacterState.Error, statusText);

        ResultLabel.Text = bubbleText;
        ResultLabel.ToolTip = string.IsNullOrWhiteSpace(detail)
            ? null
            : new TextBlock
            {
                Text = detail,
                TextWrapping = TextWrapping.Wrap,
                MaxWidth = 320,
                FontSize = 12,
            };
        BubbleArea.Visibility = Visibility.Visible;

        // 按错误类型分别决定显示哪些按钮，不给所有错误都挂上全部按钮
        ErrorDismissButton.Visibility = action == RecoverableAction.None
            ? Visibility.Collapsed
            : Visibility.Visible;
        ErrorRetryButton.Content = retryLabel ?? "重试";
        ErrorRetryButton.Visibility = action is RecoverableAction.RetryText or RecoverableAction.RetryPlayback
            ? Visibility.Visible
            : Visibility.Collapsed;
        ErrorSettingsButton.Visibility = action == RecoverableAction.OpenSettings
            ? Visibility.Visible
            : Visibility.Collapsed;
        ErrorActionArea.Visibility = Visibility.Visible;

        _errorAction = action;
        _errorActionVersion = _uiStateVersion;
    }

    /// <summary>
    /// 清空错误操作区。开始新一轮录音、文本或音频链路时调用，
    /// 避免上一轮的“重试 / 打开设置”在新一轮操作里继续生效。
    /// </summary>
    private void ClearErrorActions()
    {
        if (!Dispatcher.CheckAccess())
        {
            Dispatcher.Invoke(ClearErrorActions);
            return;
        }

        ClearErrorActionsCore();
    }

    private void ClearErrorActionsCore()
    {
        _errorAction = RecoverableAction.None;
        ErrorActionArea.Visibility = Visibility.Collapsed;
        ErrorDismissButton.Visibility = Visibility.Collapsed;
        ErrorRetryButton.Visibility = Visibility.Collapsed;
        ErrorSettingsButton.Visibility = Visibility.Collapsed;
    }

    /// <summary>
    /// 判断错误操作区里的按钮是否仍然有效。
    /// “我知道了”是兜底动作，只要操作区还挂着任意有效动作就应该可用；
    /// 其余按钮必须与当前动作类型一致（避免“重试文本”被旧的重试播放误触发）。
    /// 中途发生过任何一次状态切换（版本号变化）时，本次点击作废并收起操作区，
    /// 防止旧按钮在新状态下触发过期动作。
    /// </summary>
    private bool IsErrorActionCurrent(RecoverableAction expected)
    {
        var actionMatches = expected == RecoverableAction.Dismiss
            ? _errorAction != RecoverableAction.None
            : _errorAction == expected;

        if (!actionMatches)
            return false;

        if (_errorActionVersion != _uiStateVersion)
        {
            ClearErrorActions();
            return false;
        }

        return true;
    }

    /// <summary>
    /// 把后端错误码翻译成气泡里“用户能看懂的一句话”。
    /// 原始 message 只写日志和悬停提示，不直接铺在气泡上。
    /// </summary>
    private static string BuildFriendlyFailureText(string? errorCode, bool isText)
    {
        var code = errorCode ?? "";

        if (ContainsAny(code, "TIMEOUT"))
            return "后端响应超时，请稍后重试";
        if (ContainsAny(code, "NETWORK"))
            return "连接不上服务，请检查网络后再试一次";
        if (ContainsAny(code, "AUTH", "API_KEY", "KEY_"))
            return "鉴权失败，请在设置中检查 API Key";
        if (IsConfigurationError(code))
            return "服务配置有误，请在设置中检查 Provider 与模型";
        if (ContainsAny(code, "NO_SPEECH"))
            return "没有听清，靠近麦克风再说一次";

        return isText ? "文本处理失败，可展开提示查看原因后重试" : "语音处理失败，请稍后再试一次";
    }

    /// <summary>
    /// 失败时 Chip 上的短状态。网络/超时统一显示“处理失败 / 处理超时”，
    /// 配置类问题显示“配置失败”，其余沿用按阶段的中文名。
    /// </summary>
    private static string BuildFriendlyFailureStatus(string? errorCode, string? step)
    {
        var code = errorCode ?? "";

        if (ContainsAny(code, "TIMEOUT"))
            return "处理超时";
        if (ContainsAny(code, "NETWORK"))
            return "处理失败";
        if (IsConfigurationError(code))
            return "配置失败";

        return BuildFailureStatus(step);
    }

    /// <summary>
    /// 只有存在、非空、且是 .wav 的本地文件才允许挂“重试播放”。
    /// </summary>
    private static bool IsPlayableWav(string? path)
    {
        if (string.IsNullOrWhiteSpace(path) || !path.EndsWith(".wav", StringComparison.OrdinalIgnoreCase))
            return false;

        var info = new FileInfo(path);
        return info.Exists && info.Length > 0;
    }

    /// <summary>
    /// 配置缺失 / 鉴权失败 / 服务地址或输出格式不对 —— 这些只有改设置才有意义，
    /// 因此给“打开设置”而不是反复重试。
    /// </summary>
    private static bool IsConfigurationError(string? errorCode) =>
        ContainsAny(errorCode ?? "",
            "VALIDATION_ERROR", "AUTH", "API_KEY", "KEY_", "CONFIG",
            "UNSUPPORTED", "REQUIRED", "NO_PROVIDER");

    private void ErrorDismiss_Click(object sender, RoutedEventArgs e)
    {
        if (!IsErrorActionCurrent(RecoverableAction.Dismiss))
            return;

        // “我知道了”只收起提示并回到空闲，绝不自动重新调用后端
        ClearErrorActions();
        // 错误提示本身也要一起关掉：回到空闲后气泡里不该再挂着上一轮的错误文案
        SetResult("");
        ApplyUiState(WanwanCharacterState.Idle);
        _log.Info("error.dismiss", "用户关闭可恢复错误提示");
    }

    private async void ErrorRetry_Click(object sender, RoutedEventArgs e)
    {
        var action = _errorAction;
        if (action is not (RecoverableAction.RetryText or RecoverableAction.RetryPlayback))
            return;

        if (!IsErrorActionCurrent(action))
            return;

        // 先收起操作区，再复用原有链路：防重复仍然由各链路自己的 _isRunning 保护
        ClearErrorActions();

        if (action == RecoverableAction.RetryText)
        {
            var pendingText = _lastFailedText;
            if (string.IsNullOrWhiteSpace(pendingText))
            {
                ApplyUiState(WanwanCharacterState.Idle);
                return;
            }

            // 把失败原文放回输入框，用户能看到这次重试发的是什么
            MessageInput.Text = pendingText;
            MessageInput.CaretIndex = MessageInput.Text.Length;
            _log.Info("error.retry_text", "用户手动重试上一次失败的文本");
            await SendTextAsync();
            return;
        }

        var audioPath = _lastPlayableWavPath;
        if (!IsPlayableWav(audioPath))
        {
            // 音频已经不在了：不显示不可用的重试，也不退回“失败”
            ApplyUiState(WanwanCharacterState.Idle);
            return;
        }

        _log.Info("error.retry_playback", "用户手动重试播放", new() { ["audio_path"] = audioPath! });
        // 只重放已有 WAV，不再调用 LLM / TTS
        await PlayResponseAudioAsync(audioPath!);
    }

    private void ErrorSettings_Click(object sender, RoutedEventArgs e)
    {
        if (!IsErrorActionCurrent(RecoverableAction.OpenSettings))
            return;

        ClearErrorActions();
        _log.Info("error.open_settings", "用户从错误提示打开设置");
        OpenSettingsWindow();
    }

    private static string TruncateText(string? text, int maxLength)
    {
        if (string.IsNullOrEmpty(text))
            return "";
        return text.Length <= maxLength ? text : text[..maxLength] + "...";
    }

    // ======================== Character ========================

    /// <summary>
    /// 角色素材切换。只负责换图，不碰 Chip 和按钮 —— 那些由 ApplyUiState 统一处理，
    /// 这样页面内不会散落图片路径（路径集中在 CharacterAssets 里）。
    /// </summary>
    private void SetCharacterState(WanwanCharacterState state)
    {
        try
        {
            // CacheOption.OnLoad：一次性读完并释放文件流，
            // 避免后续拖动窗口或切换状态时反复解码，也避免残留文件句柄
            var image = new BitmapImage();
            image.BeginInit();
            image.UriSource = new Uri(CharacterAssets.Resolve(state), UriKind.Absolute);
            image.CacheOption = BitmapCacheOption.OnLoad;
            image.EndInit();

            CharacterImage.Source = image;
        }
        catch (Exception ex)
        {
            // 素材缺失不能让桌宠直接崩掉：记录日志并保留当前画面
            _log.Warn("character.asset_failed", "角色素材加载失败",
                new() { ["state"] = state.ToString(), ["error"] = ex.Message });
        }
    }

    // ======================== Input Panel ========================

    /// <summary>
    /// 输入面板初始状态：收起、字数归零、角色回到待机。
    /// 窗口启动尺寸也必须等于收起尺寸，否则首屏会是大窗口空面板。
    /// </summary>
    private void InitializeInputPanel()
    {
        _isInputPanelExpanded = false;
        CharCountLabel.Text = $"0/{MessageInput.MaxLength}";
        // 初始为空，占位提示可见（占位文字只在这里和 TextChanged 里切可见性，从不写进 TextBox.Text）
        PlaceholderLabel.Visibility = Visibility.Visible;
        // 首屏统一走状态入口，保证图片、Chip、麦克风按钮三者初始一致
        ApplyUiState(WanwanCharacterState.Idle);
    }

    private void ExpandInput_Click(object sender, RoutedEventArgs e) => SetInputPanelExpanded(true);

    private void CollapseInput_Click(object sender, RoutedEventArgs e) => SetInputPanelExpanded(false);

    /// <summary>
    /// 展开 / 收起输入面板，并同步调整窗口尺寸。
    /// 只改可见性和尺寸，不触发任何后端调用。
    /// </summary>
    private void SetInputPanelExpanded(bool expanded)
    {
        if (_isInputPanelExpanded == expanded)
            return;

        _isInputPanelExpanded = expanded;

        InputPanel.Visibility = expanded ? Visibility.Visible : Visibility.Collapsed;
        ExpandInputButton.Visibility = expanded ? Visibility.Collapsed : Visibility.Visible;

        var targetWidth = expanded ? ExpandedWindowWidth : CollapsedWindowWidth;
        var targetHeight = expanded ? ExpandedWindowHeight : CollapsedWindowHeight;

        // 展开是向右下扩大，桌宠贴着屏幕边缘时会超出工作区，
        // 因此先按目标尺寸收敛左上角坐标，再改尺寸
        var workArea = SystemParameters.WorkArea;
        var maxLeft = Math.Max(workArea.Left, workArea.Right - targetWidth);
        var maxTop = Math.Max(workArea.Top, workArea.Bottom - targetHeight);
        Left = Math.Clamp(Left, workArea.Left, maxLeft);
        Top = Math.Clamp(Top, workArea.Top, maxTop);

        Width = targetWidth;
        Height = targetHeight;

        if (expanded)
        {
            // 展开后直接把焦点交给输入框，少一次点击
            MessageInput.Focus();
        }
    }

    /// <summary>
    /// 字数显示 + 占位提示切换。
    /// 本阶段只做计数，不做语义校验（长度硬上限由 MaxLength=2000 控制）。
    /// </summary>
    private void MessageInput_TextChanged(object sender, TextChangedEventArgs e)
    {
        CharCountLabel.Text = $"{MessageInput.Text.Length}/{MessageInput.MaxLength}";

        // 有内容就藏起占位提示，清空后重新显示；占位文字不参与真实输入
        PlaceholderLabel.Visibility = MessageInput.Text.Length == 0
            ? Visibility.Visible
            : Visibility.Collapsed;

        RefreshTextInputAvailability();
    }

    /// <summary>
    /// Enter 发送，Shift+Enter 保留 TextBox 原生换行。
    /// 输入法处理键不是普通 Enter，不在这里拦截，避免中文候选确认被误当成发送。
    /// </summary>
    private async void MessageInput_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.ImeProcessed || e.Key != Key.Enter)
            return;

        if ((Keyboard.Modifiers & ModifierKeys.Shift) == ModifierKeys.Shift)
            return;

        // Ctrl/Alt/Windows 等组合键交给输入框或系统处理，只有纯 Enter 才发送。
        if (Keyboard.Modifiers != ModifierKeys.None)
            return;

        e.Handled = true;
        await SendTextAsync();
    }

    private async void SendText_Click(object sender, RoutedEventArgs e) => await SendTextAsync();

    /// <summary>
    /// 打开最近 50 条本地会话记录。历史窗口只读，不会修改或删除 JSONL。
    /// </summary>
    private void HistoryButton_Click(object sender, RoutedEventArgs e)
    {
        if (!HistoryButton.IsEnabled)
            return;

        try
        {
            var items = _history.LoadRecent(50);
            var historyWindow = new HistoryWindow(items)
            {
                Owner = this,
            };
            historyWindow.ShowDialog();
        }
        catch (Exception ex)
        {
            _log.Error("history.open_failed", "打开会话历史失败",
                new() { ["error"] = ex.Message, ["stack_trace"] = ex.StackTrace });
            MessageBox.Show($"打开会话历史失败：{ex.Message}",
                "晚晚", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    /// <summary>
    /// 文本发送统一入口：按钮和 Enter 都走这里。
    /// 它只负责编排现有 TextAudioPipeline、展示回复并把生成的 WAV 交给 WPF 播放。
    /// </summary>
    private async Task SendTextAsync()
    {
        var submittedText = MessageInput.Text.Trim();
        if (string.IsNullOrWhiteSpace(submittedText)
            || _isRunning
            || _recorder.IsRecording
            || _player.IsPlaying
            || _currentUiState is not (WanwanCharacterState.Idle or WanwanCharacterState.Error))
        {
            RefreshTextInputAvailability();
            return;
        }

        // 新一轮文本发送开始，先撤掉上一轮残留的错误按钮，避免旧动作被误点
        ClearErrorActions();

        _isRunning = true;
        ApplyUiState(WanwanCharacterState.Processing);
        SetResult("");

        try
        {
            // 本轮固定使用提交瞬间的 session，防止异步执行期间会话被意外切换。
            var submittedSessionId = _currentSessionId;
            var outcome = await _python.RunTextAudioAsync(
                submittedText,
                submittedSessionId,
                _continuousContextEnabled);
            if (!outcome.IsSuccess)
            {
                // 失败时保留输入内容，用户可以修改后直接重试；这里同时记住原文供“重试”按钮使用
                _lastFailedText = submittedText;

                if (outcome.Result == null)
                {
                    _log.Error("text_audio.ui_transport_failed", "文本链路传输层失败",
                        new()
                        {
                            ["failure_code"] = outcome.FailureCode,
                            ["failure_message"] = outcome.FailureMessage,
                        });

                    // 传输层失败（超时 / 无输出 / 进程异常）：原文本仍在，允许手动重试一次
                    ShowRecoverableError(
                        outcome.FailureCode == "TIMEOUT" ? "处理超时" : "处理失败",
                        outcome.FailureCode == "TIMEOUT"
                            ? "后端响应超时，可以重试或检查网络与设置"
                            : "后端暂时没有返回结果，可以重试一次",
                        RecoverableAction.RetryText,
                        detail: $"{outcome.FailureMessage}\nfailure_code={outcome.FailureCode}",
                        retryLabel: "重试");
                }
                else
                {
                    var failedStage = outcome.Result.Stages?
                        .FirstOrDefault(stage => stage.Status == "failed");
                    var failedStep = NormalizeStep(failedStage?.Step);
                    var errorCode = failedStage?.Error?.Code;
                    var errorMessage = failedStage?.Error?.Message;

                    _log.Error("text_audio.ui_failed", "文本音频链路阶段失败",
                        new()
                        {
                            ["trace_id"] = outcome.Result.TraceId,
                            ["step"] = failedStep,
                            ["error_code"] = errorCode,
                            ["error_message"] = errorMessage,
                        });

                    // 配置 / 鉴权类问题重试没有意义，直接引导到设置页；其余允许重试
                    var code = errorCode ?? "";
                    ShowRecoverableError(
                        BuildFriendlyFailureStatus(code, failedStep),
                        BuildFriendlyFailureText(code, isText: true),
                        IsConfigurationError(code) ? RecoverableAction.OpenSettings : RecoverableAction.RetryText,
                        detail: $"step={failedStep}\nerror_code={errorCode}\n{errorMessage}",
                        retryLabel: "重试");
                }

                return;
            }

            var result = outcome.Result;
            if (!string.Equals(result?.SessionId, submittedSessionId, StringComparison.Ordinal))
            {
                _log.Error("text_audio.session_mismatch", "文本链路 session_id 不匹配",
                    new()
                    {
                        ["expected_session_id"] = submittedSessionId,
                        ["actual_session_id"] = result?.SessionId,
                    });

                // 会话标识不一致属于状态不可信，不给重试，避免把结果记到错误的会话上
                ShowRecoverableError("会话校验失败",
                    "后端返回了不匹配的会话标识，本轮结果已停止处理",
                    RecoverableAction.Dismiss);
                return;
            }

            var replyText = result?.Final?.ReplyText?.Trim() ?? "";
            if (string.IsNullOrEmpty(replyText))
            {
                _lastFailedText = submittedText;
                _log.Error("text_audio.empty_reply", "文本链路 success 但回复为空",
                    new() { ["trace_id"] = result?.TraceId });

                ShowRecoverableError("回复为空", "LLM 没有返回可显示的回复，可以重试一次",
                    RecoverableAction.RetryText, retryLabel: "重试");
                return;
            }

            // 收到有效回复后才清空用户输入；气泡正文显示完整回复，超长内容由现有 UI 省略并通过提示查看。
            SetResult(replyText);
            ResultLabel.ToolTip = replyText;
            MessageInput.Clear();
            // 本轮已经成功，上一轮的失败原文不再作为重试来源
            _lastFailedText = null;

            var audioRef = result?.Final?.AudioRef;
            if (audioRef == null || string.IsNullOrWhiteSpace(audioRef.Value))
            {
                ApplyUiState(WanwanCharacterState.Success);
                ScheduleReturnToIdle();
                _log.Warn("text_audio.no_audio", "文本链路成功但未返回音频引用",
                    new() { ["trace_id"] = result?.TraceId });
                return;
            }

            if (!string.Equals(audioRef.Type, "local_path", StringComparison.OrdinalIgnoreCase))
            {
                _log.Error("text_audio.unsupported_audio_ref", "WPF 当前只支持本地音频引用",
                    new() { ["audio_ref_type"] = audioRef.Type, ["audio_ref_value"] = audioRef.Value });

                ShowRecoverableError("音频引用不支持",
                    "回复已生成，但当前版本只支持本地 WAV 自动播放",
                    RecoverableAction.Dismiss,
                    detail: $"audio_ref_type={audioRef.Type}\n回复：{TruncateText(replyText, 120)}");
                return;
            }

            var audioPath = ResolveProjectAudioPath(audioRef.Value);
            if (!audioPath.EndsWith(".wav", StringComparison.OrdinalIgnoreCase)
                || (!string.IsNullOrWhiteSpace(audioRef.MimeType)
                    && !string.Equals(audioRef.MimeType, "audio/wav", StringComparison.OrdinalIgnoreCase)
                    && !string.Equals(audioRef.MimeType, "audio/x-wav", StringComparison.OrdinalIgnoreCase)))
            {
                _log.Error("text_audio.unsupported_format", "文本链路返回的音频不是 WAV",
                    new() { ["audio_path"] = audioPath, ["mime_type"] = audioRef.MimeType });

                ShowRecoverableError("播放失败",
                    "TTS 输出不是 WAV，当前版本仅支持 WAV 自动播放",
                    RecoverableAction.OpenSettings,
                    detail: $"audio_path={audioPath}\nmime_type={audioRef.MimeType}");
                return;
            }

            if (!File.Exists(audioPath) || new FileInfo(audioPath).Length == 0)
            {
                _log.Error("text_audio.audio_missing", "文本链路音频文件不存在或为空",
                    new() { ["audio_path"] = audioPath });

                ShowRecoverableError("音频文件无效",
                    "回复已生成，但音频文件不存在或为空",
                    RecoverableAction.Dismiss,
                    detail: $"audio_path={audioPath}\n回复：{TruncateText(replyText, 120)}");
                return;
            }

            await PlayResponseAudioAsync(audioPath);
        }
        catch (Exception ex)
        {
            _lastFailedText = submittedText;
            _log.Error("text_audio.ui_exception", "文本发送异常",
                new() { ["error"] = ex.Message, ["stack_trace"] = ex.StackTrace });

            ShowRecoverableError("处理失败", "文本处理出现异常，可以重试一次",
                RecoverableAction.RetryText,
                detail: $"{ex.GetType().Name}: {ex.Message}",
                retryLabel: "重试");
        }
        finally
        {
            _isRunning = false;
            RefreshTextInputAvailability();
        }
    }

    /// <summary>
    /// Python 返回相对路径时，以项目根目录解析；绝对路径保持不变。
    /// </summary>
    private string ResolveProjectAudioPath(string audioPath)
    {
        return Path.IsPathRooted(audioPath)
            ? Path.GetFullPath(audioPath)
            : Path.GetFullPath(Path.Combine(_python.GetProjectRoot(), audioPath));
    }

    // ======================== 录音 / 播放共享入口 ========================
    // 主界面按钮与右键菜单都调用下面这三个方法，保证只有一套语音链路，
    // 不出现“界面按钮一套、右键菜单另一套”的重复实现。

    /// <summary>
    /// 开始录音。已有录音或链路运行中时直接忽略，不重复启动。
    /// </summary>
    private void StartRecordingShared()
    {
        if (_isRunning || _recorder.IsRecording || _player.IsPlaying)
        {
            // 状态机已经在处理中/录音中/播放中，重复点击不再叠加动作，也不重复弹窗。
            // 播放中也必须拦住：主按钮会先停止播放，但右键菜单“开始录音”不能绕过这一层。
            _log.Info("record.ignored", "当前状态不允许开始录音",
                new()
                {
                    ["is_running"] = _isRunning,
                    ["is_recording"] = _recorder.IsRecording,
                    ["is_playing"] = _player.IsPlaying,
                });
            return;
        }

        try
        {
            // 开始新一轮录音前先撤掉旧错误按钮，避免“重试”挂在已经不相关的错误上
            ClearErrorActions();

            _recorder.StartRecording();
            _log.Info("record.start", "开始录音");
            ApplyUiState(WanwanCharacterState.Listening);
        }
        catch (Exception ex)
        {
            _log.Error("record.ui_failed", "开始录音失败", new() { ["error"] = ex.Message });

            // 麦克风类问题属于可恢复的输入问题，不弹阻塞式 MessageBox
            ShowRecoverableError("录音失败", "无法开始录音，请检查麦克风后再试一次",
                RecoverableAction.Dismiss,
                detail: $"step=recorder\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}");
        }
    }

    /// <summary>
    /// 停止录音并送入语音链路。停止成功后立即进入处理中，避免出现状态空档。
    /// </summary>
    private async Task StopRecordingAndRunChainAsync()
    {
        if (!_recorder.IsRecording)
            return;

        string? audioPath;
        try
        {
            audioPath = _recorder.StopRecording();
        }
        catch (Exception ex)
        {
            // 空录音属于可重试的输入问题，不进入链路
            _log.Warn("record.ui_empty", "停止录音失败", new() { ["error"] = ex.Message });

            ShowRecoverableError("录音为空", "这次没有录到有效声音，请重新录一次",
                RecoverableAction.Dismiss,
                detail: $"step=recorder\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}");
            return;
        }

        await RunVoiceChainAsync(audioPath);
    }

    /// <summary>
    /// 取消录音：删除本次录音文件，不调用后端、不发送音频，直接回到空闲。
    /// </summary>
    private void CancelRecordingShared()
    {
        if (!_recorder.IsRecording)
            return;

        try
        {
            _recorder.CancelRecording();
            _log.Info("record.cancel", "用户取消录音");
            ApplyUiState(WanwanCharacterState.Idle);
        }
        catch (Exception ex)
        {
            _log.Warn("record.ui_cancel", "取消录音失败", new() { ["error"] = ex.Message });
            // 底层若仍在录音，就保留停止/取消入口，不能伪装成已经空闲。
            if (_recorder.IsRecording)
                ApplyUiState(WanwanCharacterState.Listening, "取消失败，请重试");
            else
                ApplyUiState(WanwanCharacterState.Error, "取消失败");
        }
    }

    // ======================== Recording ========================

    /// <summary>
    /// 主操作按钮。按当前状态决定语义：播放中 = 停止播放，录音中 = 停止录音并发送，其余 = 开始录音。
    /// </summary>
    private async void MicButton_Click(object sender, RoutedEventArgs e)
    {
        if (_player.IsPlaying)
        {
            // 主动停止播放：先置标记再 Stop，播放返回后据此走空闲而不是“完成”
            _stopPlaybackRequested = true;
            _player.Stop();
            _log.Info("playback.ui_stop", "用户主动停止播放");
            return;
        }

        if (_recorder.IsRecording)
        {
            await StopRecordingAndRunChainAsync();
            return;
        }

        StartRecordingShared();
    }

    private void StartRecord_Click(object sender, RoutedEventArgs e) => StartRecordingShared();

    private async void StopRecord_Click(object sender, RoutedEventArgs e) => await StopRecordingAndRunChainAsync();

    private void CancelRecord_Click(object sender, RoutedEventArgs e) => CancelRecordingShared();

    /// <summary>
    /// 语音输入与文本输入共用的 WPF 播放入口。
    /// 它统一处理 Speaking、用户主动停止、自然完成和播放失败，避免两条链路状态漂移。
    /// </summary>
    private async Task PlayResponseAudioAsync(string audioPath)
    {
        // 记下最后一个通过校验的 WAV：播放失败时“重试播放”只重放它，不会再走 LLM / TTS
        _lastPlayableWavPath = audioPath;

        _stopPlaybackRequested = false;
        _player.Volume = ReadVoiceVolumeFromSettings();
        ApplyUiState(WanwanCharacterState.Speaking);

        var played = await _player.PlayAsync(audioPath);
        if (!played)
        {
            _log.Error("playback.ui_failed", "播放失败", new() { ["audio_path"] = audioPath });

            // 音频文件还在就允许重试播放；文件已不可用就只给“我知道了”
            var canRetry = IsPlayableWav(audioPath);
            ShowRecoverableError(
                "播放失败",
                canRetry ? "音频播放失败，可以重试播放" : "音频播放失败，请重新发起一次",
                canRetry ? RecoverableAction.RetryPlayback : RecoverableAction.Dismiss,
                detail: $"step=playback\naudio_path={audioPath}",
                retryLabel: "重试播放");
            return;
        }

        if (_stopPlaybackRequested)
        {
            _log.Info("playback.ui_stopped_by_user", "播放被用户主动停止，回到空闲");
            ApplyUiState(WanwanCharacterState.Idle);
            return;
        }

        ApplyUiState(WanwanCharacterState.Success);
        ScheduleReturnToIdle();
    }

    // ======================== Choose Audio ========================

    private async void ChooseAudio_Click(object sender, RoutedEventArgs e)
    {
        // 处理中、录音中、播放中都不允许再提交一段音频，防止重复进入链路或与播放并发
        if (_isRunning || _recorder.IsRecording || _player.IsPlaying)
        {
            _log.Info("choose_audio.ignored", "当前状态不允许提交音频",
                new()
                {
                    ["is_running"] = _isRunning,
                    ["is_recording"] = _recorder.IsRecording,
                    ["is_playing"] = _player.IsPlaying,
                });
            return;
        }

        try
        {
            _log.Info("choose_audio.start", "打开文件选择框");

            var dialog = new OpenFileDialog
            {
                // 当前演示版本录音与 NAudio 播放链路仅可靠支持 WAV，明确限制可选格式
                Title = "选择本地 WAV 音频文件",
                Filter = "WAV 音频文件 (*.wav)|*.wav|所有文件 (*.*)|*.*",
                InitialDirectory = Path.GetFullPath(Path.Combine(_python.GetProjectRoot(), "data", "temp")),
            };

            if (dialog.ShowDialog() != true)
            {
                // 用户放弃选择：不改变链路，回到空闲
                ApplyUiState(WanwanCharacterState.Idle);
                return;
            }

            // 即使用户通过“所有文件”选了其他格式，也在提交前拦截并提示
            if (!dialog.FileName.EndsWith(".wav", StringComparison.OrdinalIgnoreCase))
            {
                _log.Warn("choose_audio.unsupported_format", "选择了非 WAV 文件，已拒绝提交",
                    new() { ["audio_path"] = dialog.FileName });

                ShowRecoverableError("仅支持 WAV",
                    "当前演示版本仅可靠支持 WAV 音频，请重新选择 .wav 文件",
                    RecoverableAction.Dismiss,
                    detail: $"audio_path={dialog.FileName}");
                return;
            }

            _log.Info("choose_audio.selected", "用户选择了音频",
                new() { ["audio_path"] = dialog.FileName });

            await RunVoiceChainAsync(dialog.FileName);
        }
        catch (Exception ex)
        {
            _log.Error("choose_audio.error", "选择音频异常", new() { ["error"] = ex.Message });

            ShowRecoverableError("选择音频失败", "无法读取所选音频，请重新选择一次",
                RecoverableAction.Dismiss,
                detail: $"step=choose_audio\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}");
        }
    }

    // ======================== Voice Chain ========================

    private async Task RunVoiceChainAsync(string audioPath)
    {
        // 进入链路即切处理中：麦克风禁用，取消按钮收起，不允许再开一轮录音
        ApplyUiState(WanwanCharacterState.Processing);
        SetResult("");
        _isRunning = true;

        try
        {
            // 发送前本地静音检测：纯静音不调用 STT，省一次 API 请求并给出更快反馈
            var silence = AudioSilenceDetector.Analyze(audioPath);
            if (!string.IsNullOrEmpty(silence.Error))
            {
                // 检测自身失败时放行，只记录警告，不阻塞正常链路
                _log.Warn("silence_check.error", "静音检测失败，放行继续发送",
                    new() { ["error"] = silence.Error, ["audio_path"] = audioPath });
            }
            else if (silence.IsSilent)
            {
                _log.Info("voice_chain.silence_blocked", "检测到静音，未发送 STT 请求",
                    new()
                    {
                        ["audio_path"] = audioPath,
                        ["duration_seconds"] = Math.Round(silence.DurationSeconds, 1),
                        ["peak"] = silence.Peak,
                        ["max_window_rms"] = silence.MaxWindowRms,
                    });

                // “没有听到声音”是最典型的可恢复输入问题：气泡内提示，不弹阻塞式对话框
                ShowRecoverableError("没有听到声音", "靠近麦克风后再试一次",
                    RecoverableAction.Dismiss,
                    detail: $"peak={silence.Peak}\nduration_seconds={Math.Round(silence.DurationSeconds, 1)}");
                return;
            }

            // 当前 IPC 只有一次最终结果，无法确认 STT/LLM/TTS 实时阶段，
            // 等待期间统一显示“处理中”，不伪造 TRANSCRIBING/THINKING/SPEAKING
            var outcome = await _python.RunVoiceChainAsync(audioPath);

            if (!outcome.IsSuccess)
            {
                if (outcome.Result == null)
                {
                    // 传输层失败：超时 / 无输出 / JSON 非法 / 进程异常
                    _log.Error("voice_chain.transport_failed", "语音链路传输层失败",
                        new()
                        {
                            ["failure_code"] = outcome.FailureCode,
                            ["failure_message"] = outcome.FailureMessage,
                        });

                    // 语音输入不能安全重放（音频已不在输入框里），因此只给“我知道了”
                    ShowRecoverableError(
                        outcome.FailureCode == "TIMEOUT" ? "处理超时" : "处理失败",
                        BuildFriendlyFailureText(outcome.FailureCode, isText: false),
                        RecoverableAction.Dismiss,
                        detail: $"failure_code={outcome.FailureCode}\n{outcome.FailureMessage}");
                }
                else
                {
                    // 结构化阶段失败：Python 正常返回，但 STT/LLM/TTS 等某阶段失败
                    var failedResult = outcome.Result;
                    var failedStep = ResolveFailedStep(failedResult);
                    var errorCode = ResolveErrorCode(failedResult);

                    // “没听清”是可恢复的输入问题，与系统故障区分开
                    if (ContainsAny(errorCode, "NO_SPEECH"))
                    {
                        _log.Warn("voice_chain.no_speech", "STT 未识别到语音内容",
                            new() { ["trace_id"] = failedResult.TraceId, ["step"] = failedStep });

                        ShowRecoverableError("没有听到声音", "没有听清，靠近麦克风再说一次",
                            RecoverableAction.Dismiss,
                            detail: $"trace_id={failedResult.TraceId}\nstep={failedStep}");
                        return;
                    }

                    var failureMessage = BuildVoiceChainFailureMessage(failedResult);
                    var errorDetail = failedResult.Final?.FailedStage?.Error;
                    var configProblem = IsConfigError(errorDetail) || IsConfigurationError(errorCode);

                    _log.Error("voice_chain.failed", "语音链路失败",
                        new()
                        {
                            ["failure"] = failureMessage,
                            ["trace_id"] = failedResult.TraceId,
                            ["step"] = failedStep,
                            ["error_code"] = errorCode,
                            ["step_display"] = GetStepDisplayName(failedStep),
                        });

                    // 配置 / 鉴权类问题只有改设置才有意义，其余只给“我知道了”
                    ShowRecoverableError(
                        BuildFriendlyFailureStatus(errorCode, failedStep),
                        BuildFriendlyFailureText(errorCode, isText: false),
                        configProblem ? RecoverableAction.OpenSettings : RecoverableAction.Dismiss,
                        detail: $"step={failedStep}\nerror_code={errorCode}\n{failureMessage}");
                }

                // 失败后状态已可继续下一轮录音（_isRunning 由 finally 统一复位）
                return;
            }

            var result = outcome.Result;
            // 理论不可达：IsSuccess 已保证 Result 非空，守卫仅用于让空引用流分析明确
            if (result == null) return;

            var sttText = result.Final?.SttText ?? "";
            var replyText = result.Final?.ReplyText ?? result.Final?.LlmReplyText ?? "";
            var ttsPath = result.Final?.TtsAudioPath ?? "";

            var convSaved = result.ConversationSave?.Saved ?? false;
            _log.Info("voice_chain.result", "语音链路完成",
                new()
                {
                    ["trace_id"] = result.TraceId,
                    ["stt_text"] = sttText,
                    ["tts_audio_path"] = ttsPath,
                    ["conversation_saved"] = convSaved,
                });

            if (!string.IsNullOrEmpty(ttsPath))
            {
                // 当前演示版本 NAudio 播放链路仅可靠支持 WAV；
                // TTS 若配置成其他格式，明确提示，而不是静默“播放失败”
                if (!ttsPath.EndsWith(".wav", StringComparison.OrdinalIgnoreCase))
                {
                    _log.Error("playback.unsupported_format", "TTS 输出格式不受支持，已跳过播放",
                        new() { ["tts_audio_path"] = ttsPath });

                    // 输出格式由 TTS 配置决定，只有改设置才有意义，因此给“打开设置”
                    ShowRecoverableError("播放失败",
                        "TTS 输出不是 WAV，当前版本仅支持 WAV 自动播放，请在设置中调整输出格式",
                        RecoverableAction.OpenSettings,
                        detail: $"tts_audio_path={ttsPath}\n回复：{TruncateText(replyText, 120)}");
                    return;
                }

                await PlayResponseAudioAsync(ttsPath);
            }
            else
            {
                // 链路成功但没有 TTS 音频：同样算完成
                ApplyUiState(WanwanCharacterState.Success);
                ScheduleReturnToIdle();
                _log.Warn("voice_chain.no_tts", "语音链路未返回 TTS 路径");
            }

            var summary = "";
            if (!string.IsNullOrEmpty(sttText))
                summary += $"识别: {TruncateText(sttText, 25)}";
            if (!string.IsNullOrEmpty(replyText))
                summary += (summary.Length > 0 ? " | " : "") + $"回复: {TruncateText(replyText, 25)}";
            if (summary.Length == 0)
                summary = "完成";
            SetResult(summary);

            if (!string.IsNullOrEmpty(sttText) || !string.IsNullOrEmpty(replyText))
            {
                var tooltipText = "";
                if (!string.IsNullOrEmpty(sttText))
                    tooltipText += $"识别文本：\n{sttText}";
                if (!string.IsNullOrEmpty(replyText))
                    tooltipText += (tooltipText.Length > 0 ? "\n\n" : "") + $"回复文本：\n{replyText}";

                ResultLabel.ToolTip = new TextBlock
                {
                    Text = tooltipText,
                    TextWrapping = TextWrapping.Wrap,
                    MaxWidth = 320,
                    FontSize = 13,
                };
            }
        }
        catch (Exception ex)
        {
            _log.Error("voice_chain.error", "语音链路异常", new() { ["error"] = ex.Message });

            ShowRecoverableError("处理失败", "语音链路出现异常，请稍后再试一次",
                RecoverableAction.Dismiss,
                detail: $"step=voice_chain\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}");
        }
        finally
        {
            _isRunning = false;
            RefreshTextInputAvailability();
        }
    }

    private static string BuildVoiceChainFailureMessage(VoiceChainResult? result)
    {
        if (result == null)
            return "Python 后端失败：未返回可解析结果";

        var failedStage = result.Final?.FailedStage;
        var step = NormalizeStep(failedStage?.Step);
        var error = failedStage?.Error;

        if (string.IsNullOrEmpty(step) || error == null)
        {
            foreach (var stage in result.Stages ?? Enumerable.Empty<VoiceChainStage>())
            {
                if (!string.Equals(stage.Status, "failed", StringComparison.OrdinalIgnoreCase))
                    continue;

                step = NormalizeStep(stage.Step);
                error = stage.Error;
                break;
            }
        }

        if (string.IsNullOrEmpty(step))
            step = NormalizeStep(result.Step);

        var title = BuildFailureTitle(step, error);
        var detail = FirstNonEmpty(error?.Message, error?.Code, "请查看日志");
        return $"{title}：{detail}";
    }

    private static string? ResolveFailedStep(VoiceChainResult? result)
    {
        if (result == null)
            return null;

        var failedStageStep = NormalizeStep(result.Final?.FailedStage?.Step);
        if (!string.IsNullOrEmpty(failedStageStep))
            return failedStageStep;

        foreach (var stage in result.Stages ?? Enumerable.Empty<VoiceChainStage>())
        {
            if (string.Equals(stage.Status, "failed", StringComparison.OrdinalIgnoreCase))
                return NormalizeStep(stage.Step);
        }

        return NormalizeStep(result.Step);
    }

    /// <summary>
    /// 与失败阶段定位相同的查找顺序：final.failed_stage → stages 中第一个 failed。
    /// </summary>
    private static string ResolveErrorCode(VoiceChainResult? result)
    {
        if (result == null)
            return "";

        var directCode = result.Final?.FailedStage?.Error?.Code;
        if (!string.IsNullOrWhiteSpace(directCode))
            return directCode;

        foreach (var stage in result.Stages ?? Enumerable.Empty<VoiceChainStage>())
        {
            if (!string.Equals(stage.Status, "failed", StringComparison.OrdinalIgnoreCase))
                continue;
            if (!string.IsNullOrWhiteSpace(stage.Error?.Code))
                return stage.Error.Code;
        }

        return "";
    }

    private static string BuildFailureTitle(string? step, VoiceChainError? error)
    {
        if (IsConfigError(error))
            return "配置失败";

        return NormalizeStep(step) switch
        {
            "stt" => "STT 失败",
            "llm" => "LLM 失败",
            "tts" => "TTS 失败",
            "playback" => "播放失败",
            "record_upload" or "voice_chain" or "recorder" => "音频输入失败",
            "config" or "settings" => "配置失败",
            _ => "Python 后端失败",
        };
    }

    private static string GetStepDisplayName(string? step)
    {
        return NormalizeStep(step) switch
        {
            "stt" => "STT 语音识别",
            "llm" => "LLM 回复生成",
            "tts" => "TTS 语音合成",
            "playback" => "音频播放",
            "record_upload" or "voice_chain" or "recorder" => "音频输入",
            "config" or "settings" => "配置读取",
            _ => "未知阶段",
        };
    }

    /// <summary>
    /// 结构化阶段失败时桌宠上显示的短状态，与详细错误（ResultLabel）区分。
    /// </summary>
    private static string BuildFailureStatus(string? step)
    {
        return NormalizeStep(step) switch
        {
            "stt" => "识别失败",
            "llm" => "回复失败",
            "tts" => "合成失败",
            "playback" => "播放失败",
            "config" or "settings" => "配置失败",
            "record_upload" or "voice_chain" or "recorder" => "输入失败",
            _ => "链路失败",
        };
    }

    private static bool IsConfigError(VoiceChainError? error)
    {
        var code = error?.Code ?? "";
        var type = error?.Type ?? "";
        var message = error?.Message ?? "";

        return ContainsAny(code, "CONFIG", "SETTINGS")
            || ContainsAny(type, "config")
            || ContainsAny(
                message,
                "config",
                "settings",
                "provider not found",
                "configured provider not found",
                "model not found",
                "configured model not found",
                "missing api key",
                "api_key",
                "api key",
                "api_host",
                "api_path");
    }

    private static bool ContainsAny(string value, params string[] candidates)
    {
        foreach (var candidate in candidates)
        {
            if (value.Contains(candidate, StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }

    private static string NormalizeStep(string? step)
    {
        return (step ?? "").Trim().ToLowerInvariant();
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
                return value.Trim();
        }

        return "";
    }

    // ======================== Text Session ========================

    /// <summary>
    /// 创建仅属于当前桌面进程的文本会话标识。重启应用或主动新建会话都会更换，
    /// 避免不同聊天主题意外共享上下文。
    /// </summary>
    private static string BuildDesktopSessionId() =>
        $"session_desktop_{Guid.NewGuid():N}";

    private void NewTextSession_Click(object sender, RoutedEventArgs e)
    {
        if (_isRunning || _recorder.IsRecording || _player.IsPlaying)
        {
            MessageBox.Show(this, "当前任务结束后再新建会话。",
                "晚晚", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        _currentSessionId = BuildDesktopSessionId();
        MessageInput.Clear();
        ResultLabel.ToolTip = null;
        SetResult("");
        ApplyUiState(WanwanCharacterState.Idle, "新会话");
        _log.Info("text_session.created", "已创建新的文本会话",
            new()
            {
                ["session_id"] = _currentSessionId,
                ["continuous_context"] = _continuousContextEnabled,
            });
    }

    /// <summary>
    /// 连续上下文默认关闭。只有用户确认历史内容会发给当前 LLM 后才置为启用，
    /// 取消勾选或设置窗口关闭后立即撤销授权。
    /// </summary>
    private void ContinuousContextMenuItem_Click(object sender, RoutedEventArgs e)
    {
        if (_isRunning || _recorder.IsRecording || _player.IsPlaying)
        {
            ContinuousContextMenuItem.IsChecked = _continuousContextEnabled;
            MessageBox.Show(this, "当前任务结束后再切换连续对话。",
                "晚晚", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (!ContinuousContextMenuItem.IsChecked)
        {
            _continuousContextEnabled = false;
            _log.Info("text_context.disabled", "用户关闭连续对话");
            return;
        }

        var confirmation = MessageBox.Show(
            this,
            "启用后，每次发送文本时，会把当前会话最近最多 6 轮（最多 12000 字符）发送给当前配置的 LLM。\n\n不会读取其他会话；语音记录不会加入文本上下文。是否继续？",
            "启用连续对话",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (confirmation != MessageBoxResult.Yes)
        {
            ContinuousContextMenuItem.IsChecked = false;
            _continuousContextEnabled = false;
            return;
        }

        _continuousContextEnabled = true;
        _log.Info("text_context.enabled", "用户确认启用连续对话",
            new() { ["session_id"] = _currentSessionId, ["max_turns"] = 6, ["max_characters"] = 12000 });
    }

    // ======================== Settings ========================

    private void OpenSettings_Click(object sender, RoutedEventArgs e) => OpenSettingsWindow();

    /// <summary>
    /// 设置窗口的唯一入口。右键菜单和气泡“打开设置”按钮都走这里，
    /// 不出现第二套设置实现，也保证 Provider 变更后撤销连续对话授权的逻辑只写一次。
    /// </summary>
    private void OpenSettingsWindow()
    {
        try
        {
            _log.Info("settings.open", "打开设置页");

            if (_settingsWindow != null)
            {
                try { _settingsWindow.Activate(); }
                catch { _settingsWindow = null; }
                if (_settingsWindow != null) return;
            }

            _settingsWindow = new SettingsWindow(_python, _player);
            _settingsWindow.Closed += (_, _) =>
            {
                _settingsWindow = null;
                // Provider 配置可能已经变化，旧授权不自动沿用到新的外部服务。
                if (_continuousContextEnabled)
                {
                    _continuousContextEnabled = false;
                    ContinuousContextMenuItem.IsChecked = false;
                    _log.Info("text_context.disabled", "设置关闭后已撤销连续对话授权");
                }
                _log.Info("settings.close", "设置页关闭");
            };
            _settingsWindow.Show();
        }
        catch (Exception ex)
        {
            _settingsWindow = null;
            var fullError = ex.ToString();
            _log.Error("settings.error", "打开设置页失败", new() { ["error"] = fullError });
            MessageBox.Show($"打开设置页失败\nstep=settings\nerror_type={ex.GetType().Name}\n\n{fullError}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    // ======================== Log ========================

    private void OpenLogWindow_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            _log.Info("log_window.open", "打开日志窗口");

            if (_logWindow != null)
            {
                try { _logWindow.Activate(); }
                catch { _logWindow = null; }
                if (_logWindow != null) return;
            }

            _logWindow = new LogWindow();
            _logWindow.Closed += (_, _) =>
            {
                _logWindow = null;
                _log.Info("log_window.close", "日志窗口关闭");
            };
            _logWindow.Show();
        }
        catch (Exception ex)
        {
            _log.Error("log_window.error", "打开日志窗口失败", new() { ["error"] = ex.Message });
            MessageBox.Show($"打开日志窗口失败\nstep=log_window\nerror_type={ex.GetType().Name}\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OpenLogFolder_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Process.Start("explorer.exe", _log.GetLogDir());
        }
        catch (Exception ex)
        {
            MessageBox.Show($"打开日志文件夹失败\nstep=log_folder\nerror_message={ex.Message}",
                "错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    // ======================== Exit ========================

    private void Exit_Click(object sender, RoutedEventArgs e)
    {
        SafeShutdown();
    }

    protected override void OnClosed(EventArgs e)
    {
        SafeShutdown();
        base.OnClosed(e);
    }

    private void SafeShutdown()
    {
        if (_isShuttingDown) return;
        _isShuttingDown = true;

        _log.Info("app.exit", "开始安全退出");

        try
        {
            if (_recorder.IsRecording)
                _recorder.CancelRecording();
        }
        catch { }

        try
        {
            _player.Stop();
        }
        catch { }

        try
        {
            _settingsWindow?.Close();
        }
        catch { }

        try
        {
            _logWindow?.Close();
        }
        catch { }

        try
        {
            Application.Current.Shutdown();
        }
        catch { }
    }

    private float ReadVoiceVolumeFromSettings()
    {
        try
        {
            // 复用 PythonBackendService 已有的项目根目录查找
            var settingsPath = Path.Combine(_python.GetProjectRoot(), "data", "config", "app_settings.json");
            if (!File.Exists(settingsPath)) return 1.0f;

            var json = File.ReadAllText(settingsPath);
            var settings = JsonSerializer.Deserialize<AppSettings>(json,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (settings == null) return 1.0f;

            // 按 active_profile_id 定位 profile，而非硬编码 profiles[0]
            var profile = settings.Profiles.FirstOrDefault(p => p.ProfileId == settings.ActiveProfileId);
            if (profile == null) return 1.0f;

            var savedVolume = profile.Desktop?.ResolveVoiceVolume();
            return savedVolume is >= 0.1 and <= 2.0 ? (float)savedVolume.Value : 1.0f;
        }
        catch
        {
            return 1.0f;
        }
    }
}
