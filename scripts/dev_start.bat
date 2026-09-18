@echo off
rem ===================================================================
rem wanwan-client Windows MVP 一键启动
rem 双击本文件：先做环境自检，自检通过后再启动 WPF 桌宠。
rem 本脚本不安装依赖、不修改配置、不启动旧的 Python CLI 主程序。
rem ===================================================================

rem 中文提示依赖 UTF-8 控制台；本文件保存为 UTF-8（无 BOM）+ CRLF 行尾
chcp 65001 >nul
setlocal

rem 用脚本自身位置定位仓库根目录，不写死任何本机绝对路径
pushd "%~dp0.."
set "ROOT=%CD%"
popd

set "CHECK_SCRIPT=%ROOT%\scripts\check_env.py"
set "DESKTOP_PROJECT=%ROOT%\src\WanwanDesktop\WanwanDesktop.csproj"
set "VENV_PYTHON=%ROOT%\.venv\Scripts\python.exe"

echo ==============================================
echo  wanwan-client 一键启动
echo ==============================================
echo 项目根目录: "%ROOT%"
echo.

rem ---------------------------------------------------------------
rem 步骤 0：选择执行自检的 Python 解释器
rem 优先用 .venv（本项目约定的运行环境）；.venv 缺失时不静默换用错误环境，
rem 而是临时用 PATH 上的 python 跑自检，由自检明确报出 .venv 缺失。
rem ---------------------------------------------------------------
set "PYTHON_EXE="
if exist "%VENV_PYTHON%" (
    set "PYTHON_EXE=%VENV_PYTHON%"
) else (
    echo [警告] 未找到虚拟环境 Python: "%VENV_PYTHON%"
    echo        将先用 PATH 上的 python 执行自检，不会用它启动后端。
    echo.
    for %%P in (python.exe) do set "PYTHON_EXE=%%~$PATH:P"
)

if not defined PYTHON_EXE (
    echo [错误] 找不到可用的 Python：.venv 不存在，PATH 上也没有 python。
    echo        请手动执行下面两条命令（脚本不会自动安装）：
    echo          python -m venv .venv
    echo          .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo        完成后重新双击 scripts\dev_start.bat
    echo.
    pause
    exit /b 1
)

rem ---------------------------------------------------------------
rem 步骤 1：环境自检（scripts\check_env.py）
rem ---------------------------------------------------------------
echo [1/3] 环境自检...
"%PYTHON_EXE%" "%CHECK_SCRIPT%" --root "%ROOT%"
set "CHECK_EXIT=%ERRORLEVEL%"

if not "%CHECK_EXIT%"=="0" (
    echo.
    echo [错误] 环境自检未通过，已停止启动 WPF 桌宠。
    echo        请按上面「错误」项给出的办法处理后，重新双击本文件。
    echo.
    pause
    exit /b %CHECK_EXIT%
)

rem ---------------------------------------------------------------
rem 步骤 2：检查 dotnet 是否可用（WPF 需要 .NET SDK）
rem ---------------------------------------------------------------
echo.
echo [2/3] 检查 dotnet...
set "DOTNET_EXE="
for %%D in (dotnet.exe) do set "DOTNET_EXE=%%~$PATH:D"

if not defined DOTNET_EXE (
    echo [错误] 没有找到 dotnet 命令，无法启动 WPF 桌宠。
    echo        请先安装 .NET 10 SDK: https://dotnet.microsoft.com/download
    echo        安装完成后打开新窗口执行 dotnet --version 验证。
    echo.
    pause
    exit /b 1
)

"%DOTNET_EXE%" --version
if errorlevel 1 (
    echo [错误] dotnet 命令无法正常执行，请修复 .NET SDK 安装后重试。
    echo.
    pause
    exit /b 1
)

rem ---------------------------------------------------------------
rem 步骤 3：启动 WPF 桌宠（首次运行需要编译，耗时稍长）
rem ---------------------------------------------------------------
cd /d "%ROOT%"
echo.
echo [3/3] 启动 WPF 桌宠...
"%DOTNET_EXE%" run --project "%DESKTOP_PROJECT%"
set "RUN_EXIT=%ERRORLEVEL%"

echo.
echo WPF 桌宠已退出，退出码: %RUN_EXIT%
if not "%RUN_EXIT%"=="0" (
    echo [提示] 非 0 退出码通常表示启动或运行出错，可查看日志: logs\wanwan_desktop.log
)
echo.
pause
exit /b %RUN_EXIT%