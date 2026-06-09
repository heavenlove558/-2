@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动抽油杆三维力学模型分析系统...
python gui_app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo 启动失败！错误详情见 gui_error.log
    echo ========================================
    if exist gui_error.log type gui_error.log
    pause
)
