@echo off
rem Wanwan desktop launcher: kill old instance, then start the built exe (no rebuild, fast).
rem After code changes, run: dotnet build src\WanwanDesktop\WanwanDesktop.csproj

taskkill /IM WanwanDesktop.exe /F >nul 2>&1
start "" "%~dp0src\WanwanDesktop\bin\Debug\net10.0-windows\WanwanDesktop.exe"
