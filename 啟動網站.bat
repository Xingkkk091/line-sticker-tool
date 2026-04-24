@echo off
chcp 65001 > nul
echo.
echo ===================================
echo   LINE 貼圖工具 - 啟動中...
echo ===================================
echo.
echo 瀏覽器會自動開啟，請稍候...
echo 關閉此視窗即可停止服務。
echo.
streamlit run "%~dp0app.py"
pause
