@echo off
chcp 65001 > nul
echo.
echo ===================================
echo   安裝必要套件
echo ===================================
echo.

pip install "rembg[cpu]" pillow
echo.
echo 安裝完成！
echo 現在可以把圖片拖曳到 run.bat 上使用。
echo.
pause
