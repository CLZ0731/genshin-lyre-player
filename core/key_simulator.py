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


def press_key(scan_code: int) -> None:
    """按下按鍵（不釋放）。"""
    _send_input(scan_code, KEYEVENTF_SCANCODE)


def release_key(scan_code: int) -> None:
    """釋放按鍵。"""
    _send_input(scan_code, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)


def press_and_release(key_char: str, delay_min: float = 0.02,
                      delay_max: float = 0.05) -> None:
    """
    按下並釋放指定按鍵，中間加入隨機延遲以模擬真人按壓節奏。

    Args:
        key_char: 按鍵字元（如 'Q', 'A', 'Z'），必須為大寫
        delay_min: 按下到釋放的最小延遲秒數
        delay_max: 按下到釋放的最大延遲秒數
    """
    scan_code = SCAN_CODES.get(key_char.upper())
    if scan_code is None:
        return  # 不支援的按鍵，靜默忽略

    press_key(scan_code)
    time.sleep(random.uniform(delay_min, delay_max))
    release_key(scan_code)


def press_multiple_keys(key_chars: list[str], delay_min: float = 0.02,
                        delay_max: float = 0.05) -> None:
    """
    同時按下多個按鍵（和弦），然後依序釋放。

    用於處理 MIDI 中同一時刻觸發的多個音符。

    Args:
        key_chars: 按鍵字元列表
        delay_min: 按下到釋放的最小延遲秒數
        delay_max: 按下到釋放的最大延遲秒數
    """
    pressed = []
    for key_char in key_chars:
        scan_code = SCAN_CODES.get(key_char.upper())
        if scan_code is not None:
            press_key(scan_code)
            pressed.append(scan_code)

    if pressed:
        time.sleep(random.uniform(delay_min, delay_max))
        for scan_code in pressed:
            release_key(scan_code)
