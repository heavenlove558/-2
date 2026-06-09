@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === 第1步: 检查Python ===
python --version
if %ERRORLEVEL% NEQ 0 (
    echo [失败] 没有找到Python! 请先安装Python
    pause
    exit /b 1
)
echo [通过] Python已安装

echo.
echo === 第2步: 检查tkinter ===
python -c "import tkinter; print('[通过] tkinter可用')" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [失败] tkinter不可用
    pause
    exit /b 1
)

echo.
echo === 第3步: 检查matplotlib ===
python -c "import matplotlib; matplotlib.use('TkAgg'); print('[通过] matplotlib可用')" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [失败] matplotlib不可用
    pause
    exit /b 1
)

echo.
echo === 第4步: 检查项目模块 ===
python -c "import parameters; print('[通过] 项目模块可导入')" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [失败] 项目模块导入失败
    pause
    exit /b 1
)

echo.
echo === 全部通过! 启动GUI... ===
python gui_app.py 2>&1
pause
