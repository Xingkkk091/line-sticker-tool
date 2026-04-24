@echo off
chcp 65001 > nul
echo.
echo ===================================
echo   LINE 貼圖自動化工具
echo ===================================
echo.

if "%~1"=="" (
    echo 請把圖片拖曳到這個 bat 檔案上，或：
    echo.
    echo 用法：直接把 Gemini 生成的排版圖拖曳到此 bat 上
    echo.
    pause
    exit /b
)

python "%~dp0sticker_tool.py" "%~1"
echo.
pause
