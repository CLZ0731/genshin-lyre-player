@echo off
chcp 65001 >nul
echo 正在啟動原神風物之詩琴助手...

REM 強制將新安裝的 Python 加入環境變數
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

REM 執行主程式
python main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [錯誤] 程式發生異常結束，錯誤碼: %ERRORLEVEL%
    pause
)
