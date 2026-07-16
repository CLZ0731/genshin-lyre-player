import os
import sys
import shutil
import subprocess

def main():
    print("[Build] Starting Genshin Lyre Player packaging process...")
    
    # 1. 確保基本檔案結構
    if not os.path.exists("main.py"):
        print("[Build] Error: main.py not found in current directory.")
        sys.exit(1)
        
    # 2. 動態載入 basic_pitch，取得其權重檔案路徑
    try:
        import basic_pitch
        basic_pitch_dir = os.path.dirname(basic_pitch.__file__)
        saved_models_src = os.path.join(basic_pitch_dir, "saved_models")
        if not os.path.exists(saved_models_src):
            raise ImportError("basic_pitch saved_models directory not found.")
    except ImportError as e:
        print(f"[Build] Error: basic_pitch package is not installed correctly: {e}")
        sys.exit(1)
        
    # 3. 定義 PyInstaller 的 --add-data 參數
    # Windows 的路徑分隔符為分號 ';'
    add_data_option = f"{saved_models_src}{os.pathsep}basic_pitch{os.sep}saved_models"
    print(f"[Build] Found basic_pitch directory: {basic_pitch_dir}")
    print(f"[Build] Bundling saved_models data: {add_data_option}")
    
    # 4. 執行 PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=GenshinLyrePlayer",
        "--onefile",              # 打包為單一執行檔
        "--noconsole",            # 隱藏後台控制台視窗 (GUI 專用)
        f"--add-data={add_data_option}",
        "main.py"
    ]
    
    print(f"[Build] Executing Command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("[Build] Executable built successfully inside 'dist/' folder!")
        
        # 5. 複製 midi_files 預設庫
        dist_dir = os.path.join(os.getcwd(), "dist")
        midi_dest = os.path.join(dist_dir, "midi_files")
        
        if os.path.exists("midi_files"):
            if os.path.exists(midi_dest):
                shutil.rmtree(midi_dest)
            shutil.copytree("midi_files", midi_dest)
            print("[Build] Copied 'midi_files' library folder to 'dist/'")
        else:
            os.makedirs(midi_dest, exist_ok=True)
            print("[Build] Created empty 'midi_files' folder in 'dist/'")
            
        # 6. 生成管理員啟動 bat 檔案 (因為原神遊戲視窗需要高權限鍵盤模擬)
        bat_content = """@echo off
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    pushd "%CD%"
    CD /D "%~dp0"

echo Starting Genshin Lyre Player...
start "" "GenshinLyrePlayer.exe"
"""
        with open(os.path.join(dist_dir, "run_admin.bat"), "w", encoding="utf-8") as f:
            f.write(bat_content)
        print("[Build] Generated 'run_admin.bat' for administrator privilege execution.")
        
        print("\n" + "="*50)
        print("[完成] 原神詩琴助手打包完成！")
        print("請打開以下目錄取得綠色免安裝包：")
        print(f"路徑: {dist_dir}")
        print("內含檔案：")
        print(" 1. GenshinLyrePlayer.exe (主程式)")
        print(" 2. midi_files/ (存放琴譜的資料夾)")
        print(" 3. run_admin.bat (右鍵或雙擊以管理員權限執行，必備！)")
        print("="*50 + "\n")
    else:
        print(f"[Build] PyInstaller failed with return code {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
