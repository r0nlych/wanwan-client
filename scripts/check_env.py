"""wanwan-client 环境自检脚本（Windows MVP 一键启动前置检查）。

怎么用：
- 双击 scripts/dev_start.bat 时，会先自动调用本脚本。
- 也可以手动运行：.venv\\Scripts\\python.exe scripts\\check_env.py

它做什么：
- 只检查「项目结构是否完整」「当前 Python 是否可用」「运行目录能否写入」。
- 输出简单中文提示，告诉你哪里有问题、怎么处理。

它刻意不做什么（安全边界）：
- 不访问网络，不调用任何真实 Provider。
- 不读取、不打印 data/config/app_settings.json 的内容。
- 不打印 API Key、Token、Authorization 等任何配置值。
- 不自动安装依赖，不自动创建或覆盖配置文件，不删除用户文件。
- 只在 logs、data/temp、data/tts 下写一个临时文件做写入探测，退出时立即删除。

退出码：
- 0：环境可用，可以启动 WPF 桌宠。
- 1：存在阻断启动的问题，请先按提示处理。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------
# 常量：需要检查的路径集中在这里，以后调整检查项只改这一段
# ---------------------------------------------------------------

# 与桌面端 ProjectPaths.cs 保持一致：AGENTS.md 就是「已到达项目根」的标志
ROOT_MARKER_FILE = "AGENTS.md"

DESKTOP_PROJECT_RELATIVE = Path("src/WanwanDesktop/WanwanDesktop.csproj")
PYTHON_ENTRY_RELATIVE = Path("src/wanwan_client/main.py")
REQUIREMENTS_RELATIVE = Path("requirements.txt")
APP_SETTINGS_RELATIVE = Path("data/config/app_settings.json")
APP_SETTINGS_EXAMPLE_RELATIVE = Path("data/config/app_settings.example.json")
VENV_PYTHON_RELATIVE = Path(".venv/Scripts/python.exe")

# 运行期需要写入的目录：日志、临时音频、TTS 产物
RUNTIME_DIR_RELATIVES = (Path("logs"), Path("data/temp"), Path("data/tts"))

# 用 importlib.util.find_spec 只判断模块能否被找到，不执行 main()，也不读配置
PYTHON_ENTRY_MODULE = "src.wanwan_client.main"

# 三个等级：通过 / 警告（不阻断启动）/ 错误（阻断启动）
LEVEL_OK = "ok"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"

LEVEL_LABELS = {
    LEVEL_OK: "[通过]",
    LEVEL_WARNING: "[警告]",
    LEVEL_ERROR: "[错误]",
}

# 给初学者的可复制命令（纯提示，脚本不会自动执行）
COPY_SETTINGS_COMMAND = (
    "Copy-Item data\\config\\app_settings.example.json data\\config\\app_settings.json"
)
CREATE_VENV_COMMAND = "python -m venv .venv"
INSTALL_DEPS_COMMAND = ".venv\\Scripts\\python.exe -m pip install -r requirements.txt"


@dataclass(frozen=True)
class CheckResult:
    """单项检查结果。

    level 决定它是否阻断启动：只有 LEVEL_ERROR 会阻断。
    hints 是给用户看的处理建议，按行输出。
    """

    check_id: str
    level: str
    title: str
    hints: tuple[str, ...] = ()


@dataclass
class PreflightReport:
    """整次自检的结果集合。"""

    root: Path | None
    results: list[CheckResult] = field(default_factory=list)

    @property
    def errors(self) -> list[CheckResult]:
        return [item for item in self.results if item.level == LEVEL_ERROR]

    @property
    def warnings(self) -> list[CheckResult]:
        return [item for item in self.results if item.level == LEVEL_WARNING]

    @property
    def can_start(self) -> bool:
        """没有 ERROR 就认为可以启动。"""
        return not self.errors

    def lines(self) -> list[str]:
        """把结果渲染成可直接 print 的文本行。"""
        lines: list[str] = []
        for item in self.results:
            lines.append(f"{LEVEL_LABELS[item.level]} {item.title}")
            lines.extend(f"       {hint}" for hint in item.hints)
        return lines


# ---------------------------------------------------------------
# 定位项目根目录
# ---------------------------------------------------------------


def find_project_root(start: Path) -> Path | None:
    """从 start 开始逐级向上查找含 AGENTS.md 的目录。

    找不到返回 None，交由调用方按「阻断启动」处理。
    """
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ROOT_MARKER_FILE).is_file():
            return candidate
    return None


def check_project_root(root: Path | None, start: Path) -> CheckResult:
    """检查 1：能否定位项目根目录。"""
    if root is None:
        return CheckResult(
            check_id="project_root",
            level=LEVEL_ERROR,
            title=f"未能定位项目根目录（从 {start} 向上都没有找到 {ROOT_MARKER_FILE}）",
            hints=(
                "请确认 scripts\\check_env.py 位于 wanwan-client 仓库内，或重新克隆项目。",
            ),
        )
    return CheckResult(
        check_id="project_root",
        level=LEVEL_OK,
        title=f"项目根目录：{root}",
    )


# ---------------------------------------------------------------
# 文件存在性检查
# ---------------------------------------------------------------


def check_file(
    root: Path,
    relative: Path,
    check_id: str,
    description: str,
    level_if_missing: str,
    missing_hint: str,
) -> CheckResult:
    """通用文件检查：存在算通过，缺失按指定等级报告。

    只做 is_file() 判断，不读取文件内容。
    """
    target = root / relative
    if target.is_file():
        return CheckResult(
            check_id=check_id,
            level=LEVEL_OK,
            title=f"{description}存在：{relative.as_posix()}",
        )
    return CheckResult(
        check_id=check_id,
        level=level_if_missing,
        title=f"缺少{description}：{relative.as_posix()}",
        hints=(missing_hint,),
    )


def check_app_settings(root: Path) -> CheckResult:
    """检查 6：本地配置是否存在。

    配置缺失会阻断启动（Python 链路读不到 Provider 配置），但脚本不会自动复制，
    也不会输出配置内容。
    """
    target = root / APP_SETTINGS_RELATIVE
    if target.is_file():
        return CheckResult(
            check_id="app_settings",
            level=LEVEL_OK,
            title=f"本地配置文件存在：{APP_SETTINGS_RELATIVE.as_posix()}",
        )

    if (root / APP_SETTINGS_EXAMPLE_RELATIVE).is_file():
        copy_hint = f"请手动复制一份配置（脚本不会自动复制）：{COPY_SETTINGS_COMMAND}"
    else:
        copy_hint = "配置模板也不存在，请重新克隆仓库后再复制模板生成配置。"

    return CheckResult(
        check_id="app_settings",
        level=LEVEL_ERROR,
        title=f"缺少本地配置文件：{APP_SETTINGS_RELATIVE.as_posix()}",
        hints=(
            "本地配置只影响本机运行，脚本不会读取或打印它的内容。",
            copy_hint,
        ),
    )


def check_venv_python(root: Path) -> CheckResult:
    """检查 8：虚拟环境里的 Python 是否存在。"""
    target = root / VENV_PYTHON_RELATIVE
    if target.is_file():
        return CheckResult(
            check_id="venv_python",
            level=LEVEL_OK,
            title=f"虚拟环境 Python 存在：{VENV_PYTHON_RELATIVE.as_posix()}",
        )
    return CheckResult(
        check_id="venv_python",
        level=LEVEL_ERROR,
        title=f"缺少虚拟环境 Python：{VENV_PYTHON_RELATIVE.as_posix()}",
        hints=(
            "本项目不会自动安装依赖，请手动执行下面两条命令：",
            f"  1) {CREATE_VENV_COMMAND}",
            f"  2) {INSTALL_DEPS_COMMAND}",
        ),
    )


# ---------------------------------------------------------------
# Python 可用性检查
# ---------------------------------------------------------------


def build_import_probe_command() -> list[str]:
    """构造最小导入探针命令：只查模块能否被找到，不执行模块、不读配置、不联网。"""
    code = (
        "import importlib.util, sys;"
        f"sys.exit(0 if importlib.util.find_spec({PYTHON_ENTRY_MODULE!r}) else 1)"
    )
    return ["-c", code]


def check_python_import(root: Path, python_exe: str) -> CheckResult:
    """检查 9：当前 Python 能否找到项目入口模块。"""
    try:
        completed = subprocess.run(  # noqa: S603 - 命令由本脚本固定构造，无外部输入
            [python_exe, *build_import_probe_command()],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CheckResult(
            check_id="import_entry",
            level=LEVEL_ERROR,
            title=f"无法用当前 Python 执行检查：{exc}",
            hints=(
                f"请确认解释器可用：{python_exe}",
                "必要时重新创建虚拟环境后重试。",
            ),
        )

    if completed.returncode == 0:
        return CheckResult(
            check_id="import_entry",
            level=LEVEL_OK,
            title=f"当前 Python 可以找到项目入口：{PYTHON_ENTRY_MODULE}",
        )

    return CheckResult(
        check_id="import_entry",
        level=LEVEL_ERROR,
        title=(
            f"当前 Python 无法导入项目入口：{PYTHON_ENTRY_MODULE}"
            f"（退出码 {completed.returncode}）"
        ),
        hints=(
            "请在项目根目录确认依赖已安装：",
            f"  {INSTALL_DEPS_COMMAND}",
        ),
    )


# ---------------------------------------------------------------
# 运行目录可写性检查
# ---------------------------------------------------------------


def check_runtime_dirs(root: Path) -> CheckResult:
    """检查 10：logs、data/temp、data/tts 能否创建并写入。

    写入探测用的临时文件在 with 块结束时自动删除，不在仓库留下残留。
    """
    for relative in RUNTIME_DIR_RELATIVES:
        target = root / relative
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return CheckResult(
                check_id="runtime_dirs",
                level=LEVEL_ERROR,
                title=f"运行目录无法创建：{relative.as_posix()}（{exc}）",
                hints=("请检查目录权限、磁盘空间或安全软件拦截。",),
            )

        try:
            with tempfile.NamedTemporaryFile(
                dir=str(target), prefix=".wanwan_preflight_", suffix=".tmp"
            ):
                pass
        except OSError as exc:
            return CheckResult(
                check_id="runtime_dirs",
                level=LEVEL_ERROR,
                title=f"运行目录无法写入：{relative.as_posix()}（{exc}）",
                hints=("请检查目录权限、磁盘空间或安全软件拦截。",),
            )

    dirs_text = "、".join(path.as_posix() for path in RUNTIME_DIR_RELATIVES)
    return CheckResult(
        check_id="runtime_dirs",
        level=LEVEL_OK,
        title=f"运行目录可创建并可写入：{dirs_text}",
    )


# ---------------------------------------------------------------
# 汇总执行与输出
# ---------------------------------------------------------------


def run_checks(
    root: Path | None,
    start: Path | None = None,
    python_exe: str | None = None,
) -> PreflightReport:
    """按固定顺序跑完全部检查项，返回报告对象。

    root 为 None（没定位到项目根）时只报告这一条，不再继续检查文件，
    避免刷一堆无意义的失败项。
    """
    start_dir = Path(start) if start is not None else Path(__file__).resolve().parent
    interpreter = python_exe or sys.executable

    report = PreflightReport(root=root)
    report.results.append(check_project_root(root, start_dir))
    if root is None:
        return report

    # 1. AGENTS.md：项目根标志文件
    report.results.append(
        check_file(
            root,
            Path(ROOT_MARKER_FILE),
            "agents_md",
            f"{ROOT_MARKER_FILE} 项目说明文件",
            LEVEL_ERROR,
            "该文件是项目根目录标志，请不要删除；如已丢失，请重新克隆仓库。",
        )
    )
    # 2. WPF 桌面工程
    report.results.append(
        check_file(
            root,
            DESKTOP_PROJECT_RELATIVE,
            "desktop_project",
            "WPF 桌面工程",
            LEVEL_ERROR,
            "缺少桌面工程就无法启动桌宠，请重新克隆仓库或恢复该文件。",
        )
    )
    # 3. Python 入口
    report.results.append(
        check_file(
            root,
            PYTHON_ENTRY_RELATIVE,
            "python_entry",
            "Python 入口",
            LEVEL_ERROR,
            "请确认 src\\wanwan_client 目录没有被删除；如已丢失，请重新克隆仓库。",
        )
    )
    # 4. 依赖清单
    report.results.append(
        check_file(
            root,
            REQUIREMENTS_RELATIVE,
            "requirements",
            "Python 依赖清单",
            LEVEL_ERROR,
            f"依赖清单缺失，请重新克隆仓库后再执行：{INSTALL_DEPS_COMMAND}",
        )
    )
    # 5. 本地配置（缺失阻断启动）
    report.results.append(check_app_settings(root))
    # 6. 配置模板（只影响「怎么生成配置」，不阻断启动，所以是警告）
    report.results.append(
        check_file(
            root,
            APP_SETTINGS_EXAMPLE_RELATIVE,
            "app_settings_example",
            "配置模板",
            LEVEL_WARNING,
            "模板缺失时无法用「复制模板」的方式生成本地配置，请重新克隆仓库。",
        )
    )
    # 7. 虚拟环境 Python
    report.results.append(check_venv_python(root))
    # 8. 当前 Python 能否找到项目入口
    report.results.append(check_python_import(root, interpreter))
    # 9. 运行目录可写
    report.results.append(check_runtime_dirs(root))

    return report


def format_report(report: PreflightReport) -> list[str]:
    """把报告渲染成完整的中文输出（不含任何配置内容）。"""
    lines = [
        "=" * 46,
        " wanwan-client 环境自检",
        "=" * 46,
    ]
    lines.extend(report.lines())
    lines.append("-" * 46)

    error_count = len(report.errors)
    warning_count = len(report.warnings)
    if report.can_start:
        if warning_count:
            lines.append(f"自检结果：通过（{warning_count} 项警告，不影响启动）")
        else:
            lines.append("自检结果：通过，可以启动 WPF 桌宠")
    else:
        lines.append(f"自检结果：不通过（{error_count} 项错误，{warning_count} 项警告）")
        lines.append(
            "请先按上面「错误」项的提示处理，然后重新双击 scripts\\dev_start.bat"
        )
    return lines


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check_env.py",
        description="wanwan-client 环境自检：检查当前环境能否启动 WPF 桌宠。",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="手动指定项目根目录（默认从本脚本所在位置向上查找 AGENTS.md）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """脚本入口：返回退出码（0 可启动 / 1 有阻断问题）。"""
    args = _parse_args(argv)
    start_dir = Path(__file__).resolve().parent

    if args.root:
        candidate = Path(args.root).expanduser()
        root = candidate.resolve() if candidate.is_dir() else None
        if root is None:
            print(f"[错误] --root 指定的目录不存在：{candidate}")
            print("请检查路径后重试。")
            return 1
    else:
        root = find_project_root(start_dir)

    report = run_checks(root, start=start_dir)
    for line in format_report(report):
        print(line)

    return 0 if report.can_start else 1


if __name__ == "__main__":
    sys.exit(main())