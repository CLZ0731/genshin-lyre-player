import sys
import os
import basic_pitch
from cx_Freeze import setup, Executable

# 1. 取得 basic_pitch 套件中的權重模型路徑
basic_pitch_dir = os.path.dirname(basic_pitch.__file__)
saved_models_src = os.path.join(basic_pitch_dir, "saved_models")

# 2. 設定 cx_Freeze 封裝選項
build_exe_options = {
    "packages": [
        "os", "sys", "numpy", "scipy", "soundfile", "av", "PyQt5", 
        "mido", "pretty_midi", "librosa", "basic_pitch", "onnxruntime"
    ],
    "include_files": [
        # (來源路徑, 目標相對路徑)
        (saved_models_src, os.path.join("lib", "basic_pitch", "saved_models")),
        ("midi_files", "midi_files")
    ],
    "excludes": ["tkinter"],
    "include_msvcr": True
}

# 3. 設定 Windows Installer (MSI) 選項
bdist_msi_options = {
    "upgrade_code": "{0e33efb4-ca42-4c8d-a05e-869c1b1a8649}", # 產品的唯一升級碼 GUID
    "add_to_path": False,
    "initial_target_dir": r"[AppDataFolder]\GenshinLyrePlayer", # 安裝在 AppData 確保 config.json 可以無阻礙地寫入
}

base = None
if sys.platform == "win32":
    base = "Win32GUI"  # 隱藏後台控制台視窗，作為純 GUI 軟體啟動

# 4. 定義產出的 Executable 執行檔
executables = [
    Executable(
        "main.py",
        base=base,
        target_name="GenshinLyrePlayer.exe",
        manifest="app.manifest",  # 嵌入 UAC 管理員權限清單，讓程式原生以管理員執行
        shortcut_name="原神風物之詩琴助手",
        shortcut_dir="DesktopFolder"  # 在安裝時自動在桌面建立捷徑
    )
]

from core.version import __version__ as APP_VERSION

# 5. 呼叫 setup 執行打包
setup(
    name="GenshinLyrePlayer",
    version=APP_VERSION,
    description="Genshin Impact Lyre Auto Player with AI Audio-to-MIDI transcription",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options
    },
    executables=executables
)
