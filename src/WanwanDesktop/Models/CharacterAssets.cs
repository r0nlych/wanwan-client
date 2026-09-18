namespace WanwanDesktop.Models;

/// <summary>
/// 桌宠角色状态。命名对应任务约定的 6 个状态，
/// 后续接入录音/链路时只需要改调用点，不需要再动资源路径。
/// </summary>
public enum WanwanCharacterState
{
    Idle,
    Listening,
    Processing,
    Speaking,
    Success,
    Error,
}

/// <summary>
/// 角色素材的集中映射表。
///
/// 为什么要单独一个文件：
/// - 页面代码里不允许出现零散的图片路径字符串，否则以后换素材要全仓库搜索
/// - 图片已通过 csproj 的 Resource 打包进程序集，这里必须用 pack URI 加载，
///   不能用 F:\KB\... 这样的本机绝对路径
/// </summary>
public static class CharacterAssets
{
    // 打包资源根路径：三个逗号是 WPF pack URI 的固定写法，指向本程序集内的资源
    private const string AssetRoot = "pack://application:,,,/Assets/Characters/Wanwan/";

    /// <summary>
    /// 说话闭口帧。本阶段不参与状态切换，只作为后续口型动画的预留资源，
    /// 放在这里是为了保证 7 张素材都有明确归属、不出现"复制了但没人用"的悬空文件。
    /// </summary>
    public static string SpeakingClosed { get; } = AssetRoot + "wanwan_speaking_closed.png";

    /// <summary>
    /// 状态 → 素材路径。这是本阶段唯一的角色状态切换入口所依赖的映射。
    /// </summary>
    public static string Resolve(WanwanCharacterState state) => state switch
    {
        WanwanCharacterState.Listening => AssetRoot + "wanwan_listening.png",
        WanwanCharacterState.Processing => AssetRoot + "wanwan_thinking.png",
        WanwanCharacterState.Speaking => AssetRoot + "wanwan_speaking_open.png",
        WanwanCharacterState.Success => AssetRoot + "wanwan_success.png",
        WanwanCharacterState.Error => AssetRoot + "wanwan_error.png",
        _ => AssetRoot + "wanwan_idle.png",
    };
}