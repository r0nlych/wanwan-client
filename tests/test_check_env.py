"""check_env.py 环境自检的离线测试。

全部使用临时目录搭建「假仓库结构」，不访问网络，不接触真实仓库文件，
临时目录在用例结束时自动清理。
"""

import builtins
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_env

# 塞进假配置文件的哨兵值，用来验证自检不会读取、也不会输出配置内容
SENTINEL_SETTINGS_VALUE = "sentinel-settings-value-0001"

DESKTOP_PROJECT = "src/WanwanDesktop/WanwanDesktop.csproj"
PYTHON_ENTRY = "src/wanwan_client/main.py"
APP_SETTINGS = "data/config/app_settings.json"
APP_SETTINGS_EXAMPLE = "data/config/app_settings.example.json"


def _write_file(root: Path, relative: str, text: str = "") -> Path:
    """在假仓库里写一个文件，父目录自动创建。"""
    target = Path(root) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _make_fake_project(
    root: Path,
    *,
    agents: bool = True,
    desktop_project: bool = True,
    python_entry: bool = True,
    requirements: bool = True,
    app_settings: bool = True,
    app_settings_example: bool = True,
    venv_python: bool = True,
) -> Path:
    """按开关搭建假仓库，默认是「结构完整」的目录树。"""
    root = Path(root)
    if agents:
        _write_file(root, "AGENTS.md", "# fake agents\n")
    if desktop_project:
        _write_file(root, DESKTOP_PROJECT, "<Project />\n")
    if python_entry:
        # 入口存在时同时补上包标记，让导入探针能真正找到模块
        _write_file(root, PYTHON_ENTRY, "")
        _write_file(root, "src/__init__.py", "")
        _write_file(root, "src/wanwan_client/__init__.py", "")
    if requirements:
        _write_file(root, "requirements.txt", "requests\n")
    if app_settings:
        _write_file(root, APP_SETTINGS, '{"schema_version": "settings.v0.2"}\n')
    if app_settings_example:
        _write_file(root, APP_SETTINGS_EXAMPLE, "{}\n")
    if venv_python:
        _write_file(root, ".venv/Scripts/python.exe", "")
    return root


def _result_by_id(report: check_env.PreflightReport, check_id: str) -> check_env.CheckResult:
    """按检查项 id 取结果，缺失直接失败，避免断言落空。"""
    for item in report.results:
        if item.check_id == check_id:
            return item
    raise AssertionError(f"自检报告缺少检查项: {check_id}")


class _FileAccessRecorder:
    """记录检查过程中被打开或读取的文件路径。

    用来证明 check_env 只做存在性判断，没有读取配置文件内容。
    """

    def __init__(self) -> None:
        self.accessed: list[str] = []
        self._saved: dict[str, object] = {}

    def __enter__(self) -> "_FileAccessRecorder":
        self._saved = {
            "builtins_open": builtins.open,
            "path_open": Path.open,
            "path_read_text": Path.read_text,
            "path_read_bytes": Path.read_bytes,
        }
        recorder = self

        def spy_builtin_open(file, *args, **kwargs):
            recorder.accessed.append(str(file))
            return self._saved["builtins_open"](file, *args, **kwargs)

        def spy_path_open(path_self, *args, **kwargs):
            recorder.accessed.append(str(path_self))
            return self._saved["path_open"](path_self, *args, **kwargs)

        def spy_read_text(path_self, *args, **kwargs):
            recorder.accessed.append(str(path_self))
            return self._saved["path_read_text"](path_self, *args, **kwargs)

        def spy_read_bytes(path_self, *args, **kwargs):
            recorder.accessed.append(str(path_self))
            return self._saved["path_read_bytes"](path_self, *args, **kwargs)

        builtins.open = spy_builtin_open
        Path.open = spy_path_open
        Path.read_text = spy_read_text
        Path.read_bytes = spy_read_bytes
        return self

    def __exit__(self, *exc_info) -> bool:
        builtins.open = self._saved["builtins_open"]
        Path.open = self._saved["path_open"]
        Path.read_text = self._saved["path_read_text"]
        Path.read_bytes = self._saved["path_read_bytes"]
        return False


class CheckEnvTestBase(unittest.TestCase):
    """统一的临时目录与报告调用封装。"""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="wanwan_check_env_")
        self.root = Path(self._temp_dir.name)
        self.addCleanup(self._temp_dir.cleanup)

    def run_report(self, root: Path | None = None) -> check_env.PreflightReport:
        target = self.root if root is None else root
        return check_env.run_checks(target, start=target)


class CompleteStructureTest(CheckEnvTestBase):
    """1. 完整目录结构 → 通过。"""

    def test_full_structure_passes_without_errors(self) -> None:
        _make_fake_project(self.root)

        report = self.run_report()

        self.assertTrue(
            report.can_start,
            msg="完整结构不应阻断启动：\n" + "\n".join(check_env.format_report(report)),
        )
        self.assertEqual([], report.errors)
        self.assertEqual(check_env.LEVEL_OK, _result_by_id(report, "project_root").level)
        self.assertEqual(check_env.LEVEL_OK, _result_by_id(report, "import_entry").level)

    def test_runtime_dirs_are_created_by_check(self) -> None:
        _make_fake_project(self.root)

        self.run_report()

        for relative in check_env.RUNTIME_DIR_RELATIVES:
            self.assertTrue((self.root / relative).is_dir(), msg=f"未创建运行目录: {relative}")


class MissingItemTest(CheckEnvTestBase):
    """2~7. 关键文件缺失时的结果等级与提示。"""

    def test_missing_agents_md_is_error(self) -> None:
        _make_fake_project(self.root, agents=False)

        report = self.run_report()

        self.assertFalse(report.can_start)
        self.assertEqual(check_env.LEVEL_ERROR, _result_by_id(report, "agents_md").level)

    def test_missing_desktop_project_is_error(self) -> None:
        _make_fake_project(self.root, desktop_project=False)

        report = self.run_report()

        self.assertFalse(report.can_start)
        self.assertEqual(
            check_env.LEVEL_ERROR, _result_by_id(report, "desktop_project").level
        )

    def test_missing_python_entry_is_error(self) -> None:
        _make_fake_project(self.root, python_entry=False)

        report = self.run_report()

        self.assertFalse(report.can_start)
        self.assertEqual(check_env.LEVEL_ERROR, _result_by_id(report, "python_entry").level)
        # 入口缺失时导入探针也必须失败，不能假装通过
        self.assertEqual(check_env.LEVEL_ERROR, _result_by_id(report, "import_entry").level)

    def test_missing_app_settings_is_error_with_copy_hint(self) -> None:
        _make_fake_project(self.root, app_settings=False)

        report = self.run_report()
        result = _result_by_id(report, "app_settings")

        self.assertFalse(report.can_start)
        self.assertEqual(check_env.LEVEL_ERROR, result.level)
        hints = "\n".join(result.hints)
        self.assertIn("Copy-Item", hints)
        self.assertIn("app_settings.example.json", hints)

    def test_missing_example_settings_is_warning_only(self) -> None:
        _make_fake_project(self.root, app_settings_example=False)

        report = self.run_report()
        result = _result_by_id(report, "app_settings_example")

        self.assertEqual(check_env.LEVEL_WARNING, result.level)
        self.assertEqual([], report.errors)
        self.assertTrue(report.can_start)

    def test_missing_venv_python_is_error_with_setup_commands(self) -> None:
        _make_fake_project(self.root, venv_python=False)

        report = self.run_report()
        result = _result_by_id(report, "venv_python")

        self.assertFalse(report.can_start)
        self.assertEqual(check_env.LEVEL_ERROR, result.level)
        hints = "\n".join(result.hints)
        self.assertIn(check_env.CREATE_VENV_COMMAND, hints)
        self.assertIn(check_env.INSTALL_DEPS_COMMAND, hints)


class ConfigContentSafetyTest(CheckEnvTestBase):
    """8. 检查过程不会读取或输出配置内容。"""

    def test_report_does_not_read_or_print_settings_content(self) -> None:
        _make_fake_project(self.root)
        _write_file(
            self.root,
            APP_SETTINGS,
            '{"api_key": "' + SENTINEL_SETTINGS_VALUE + '", "note": "' + SENTINEL_SETTINGS_VALUE + '"}\n',
        )

        with _FileAccessRecorder() as recorder:
            report = self.run_report()
            output = "\n".join(check_env.format_report(report))

        self.assertNotIn(SENTINEL_SETTINGS_VALUE, output)
        self.assertTrue(report.can_start)
        accessed_settings = [
            path for path in recorder.accessed if Path(path).name == "app_settings.json"
        ]
        self.assertEqual([], accessed_settings, msg="自检不应打开本地配置文件")


class PathHandlingTest(CheckEnvTestBase):
    """9. 路径含空格与中文时仍能正确检查。"""

    def test_project_root_with_spaces_and_chinese(self) -> None:
        weird_root = self.root / "wan wan 测试 目录"
        _make_fake_project(weird_root)
        nested = weird_root / "scripts"
        nested.mkdir(parents=True, exist_ok=True)

        found = check_env.find_project_root(nested)
        report = check_env.run_checks(weird_root, start=nested)
        output = "\n".join(check_env.format_report(report))

        self.assertEqual(weird_root, found)
        self.assertTrue(report.can_start, msg=output)
        self.assertIn(str(weird_root), output)


class ResidueTest(CheckEnvTestBase):
    """10. 临时目录测试结束后无残留。"""

    def test_runtime_dir_probe_leaves_no_files(self) -> None:
        _make_fake_project(self.root)

        self.run_report()
        first_snapshot = {
            relative: sorted(path.name for path in (self.root / relative).iterdir())
            for relative in check_env.RUNTIME_DIR_RELATIVES
        }
        self.run_report()
        second_snapshot = {
            relative: sorted(path.name for path in (self.root / relative).iterdir())
            for relative in check_env.RUNTIME_DIR_RELATIVES
        }

        for relative, names in second_snapshot.items():
            self.assertEqual([], names, msg=f"写入探测留下了残留文件: {relative}")
        self.assertEqual(first_snapshot, second_snapshot)


class ExitCodeTest(CheckEnvTestBase):
    """退出码语义：0 可启动，非 0 存在阻断问题。"""

    def _run_main(self, argv: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = check_env.main(argv)
        return exit_code, buffer.getvalue()

    def test_main_returns_zero_for_complete_structure(self) -> None:
        _make_fake_project(self.root)

        exit_code, output = self._run_main(["--root", str(self.root)])

        self.assertEqual(0, exit_code)
        self.assertIn("自检结果：通过", output)

    def test_main_returns_nonzero_when_blocking_error(self) -> None:
        _make_fake_project(self.root, app_settings=False)

        exit_code, output = self._run_main(["--root", str(self.root)])

        self.assertEqual(1, exit_code)
        self.assertIn("自检结果：不通过", output)

    def test_main_returns_nonzero_for_unknown_root_argument(self) -> None:
        exit_code, output = self._run_main(["--root", str(self.root / "not_exists")])

        self.assertEqual(1, exit_code)
        self.assertIn("--root", output)


if __name__ == "__main__":
    sys.exit(unittest.main())