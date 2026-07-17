"""
DirectInput 鍵盤模擬模組

使用 ctypes 呼叫 Windows API SendInput，以 DirectInput 硬體掃描碼
模擬按鍵事件。此方法可繞過遊戲的高階輸入攔截。
"""

import ctypes
import time
import random

# ─────────────────────────── Windows API 常數 ───────────────────────────
INPUT_KEYBOARD = 1
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002

# ─────────────────────────── C 結構體定義 ───────────────────────────
PUL = ctypes.POINTER(ctypes.c_ulong)


class KEYBDINPUT(ctypes.Structure):
    """KEYBDINPUT 結構體，對應 Windows SDK 定義。"""
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", INPUT_UNION),
    ]


# ─────────────────────────── DirectInput 掃描碼表 ───────────────────────────
# 原神風物之詩琴使用的 21 個按鍵對應的硬體掃描碼
SCAN_CODES = {
    # 高音行 (Top row)
    'Q': 0x10, 'W': 0x11, 'E': 0x12, 'R': 0x13,
    'T': 0x14, 'Y': 0x15, 'U': 0x16,
    # 中音行 (Middle row)
    'A': 0x1E, 'S': 0x1F, 'D': 0x20, 'F': 0x21,
    'G': 0x22, 'H': 0x23, 'J': 0x24,
    # 低音行 (Bottom row)
    'Z': 0x2C, 'X': 0x2D, 'C': 0x2E, 'V': 0x2F,
    'B': 0x30, 'N': 0x31, 'M': 0x32,
}


# ─────────────────────────── Windows API 訊息常數 ───────────────────────────
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

# ─────────────────────────── 底層按鍵函式 ───────────────────────────
def _send_input(scan_code: int, flags: int) -> None:
    """透過 SendInput 發送單一鍵盤事件。"""
    extra = ctypes.c_ulong(0)
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ii.ki = KEYBDINPUT(
        wVk=0,  # 不使用虛擬鍵碼
        wScan=scan_code,
        dwFlags=flags,
        time=0,
        dwExtraInfo=ctypes.pointer(extra),
    )
    ctypes.windll.user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))


def press_key(scan_code: int, hwnd: int | None = None, key_char: str | None = None) -> None:
    """按下按鍵（不釋放）。"""
    if hwnd:
        if key_char:
            vk = ord(key_char.upper())
            lParam = 1 | (scan_code << 16)
            ctypes.windll.user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lParam)
    else:
        _send_input(scan_code, KEYEVENTF_SCANCODE)


def release_key(scan_code: int, hwnd: int | None = None, key_char: str | None = None) -> None:
    """釋放按鍵。"""
    if hwnd:
        if key_char:
            vk = ord(key_char.upper())
            lParam = 1 | (scan_code << 16) | 0xC0000000
            ctypes.windll.user32.PostMessageW(hwnd, WM_KEYUP, vk, lParam)
    else:
        _send_input(scan_code, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)


def press_and_release(key_char: str, delay_min: float = 0.02,
                      delay_max: float = 0.05, hwnd: int | None = None) -> None:
    """
    按下並釋放指定按鍵，中間加入隨機延遲以模擬真人按壓節奏。

    Args:
        key_char: 按鍵字元（如 'Q', 'A', 'Z'），必須為大寫
        delay_min: 按下到釋放的最小延遲秒數
        delay_max: 按下到釋放的最大延遲秒數
        hwnd: 目標視窗的控制代碼，若為 None 則發送至前景活動視窗
    """
    scan_code = SCAN_CODES.get(key_char.upper())
    if scan_code is None:
        return  # 不支援的按鍵，靜默忽略

    press_key(scan_code, hwnd, key_char)
    time.sleep(random.uniform(delay_min, delay_max))
    release_key(scan_code, hwnd, key_char)


def press_multiple_keys(key_chars: list[str], delay_min: float = 0.02,
                        delay_max: float = 0.05, hwnd: int | None = None) -> None:
    """
    同時按下多個按鍵（和弦），然後依序釋放。

    用於處理 MIDI 中同一時刻觸發的多個音符。

    Args:
        key_chars: 按鍵字元列表
        delay_min: 按下到釋放的最小延遲秒數
        delay_max: 按下到釋放的最大延遲秒數
        hwnd: 目標視窗的控制代碼，若為 None 則發送至前景活動視窗
    """
    pressed = []
    for key_char in key_chars:
        scan_code = SCAN_CODES.get(key_char.upper())
        if scan_code is not None:
            press_key(scan_code, hwnd, key_char)
            pressed.append((scan_code, key_char))

    if pressed:
        time.sleep(random.uniform(delay_min, delay_max))
        for scan_code, key_char in pressed:
            release_key(scan_code, hwnd, key_char)


def get_genshin_windows() -> list[tuple[int, str]]:
    """掃描所有原神遊戲視窗，返回 (hwnd, title_with_pid) 列表"""
    windows = []
    
    # 宣告 callback 類型
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    
    def enum_window_proc(hwnd, lParam):
        # 獲取視窗類別名稱
        class_name = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, class_name, 256)
        
        # 獲取視窗標題
        title = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, 256)
        
        c_name = class_name.value
        t_name = title.value
        
        # 原神遊戲視窗類名為 "UnityWndClass"
        if c_name == "UnityWndClass" and ("原神" in t_name or "Genshin Impact" in t_name):
            # 獲取 PID
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            windows.append((hwnd, f"{t_name} (PID: {pid.value})"))
            
        return True

    callback = WNDENUMPROC(enum_window_proc)
    ctypes.windll.user32.EnumWindows(callback, 0)
    return windows
