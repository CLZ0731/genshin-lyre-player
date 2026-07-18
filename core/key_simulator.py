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
            # 傳送啟用與聚焦訊息，欺騙視窗使其在背景也能正常處理按鍵
            ctypes.windll.user32.PostMessageW(hwnd, 0x0006, 1, 0)  # WM_ACTIVATE = 0x0006, WA_ACTIVE = 1
            ctypes.windll.user32.PostMessageW(hwnd, 0x0007, 0, 0)  # WM_SETFOCUS = 0x0007
            ctypes.windll.user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lParam)
    else:
        _send_input(scan_code, KEYEVENTF_SCANCODE)


def release_key(scan_code: int, hwnd: int | None = None, key_char: str | None = None) -> None:
    """釋放按鍵。"""
    if hwnd:
        if key_char:
            vk = ord(key_char.upper())
            lParam = 1 | (scan_code << 16) | 0xC0000000
            # 傳送啟用與聚焦訊息，欺騙視窗使其在背景也能正常處理按鍵
            ctypes.windll.user32.PostMessageW(hwnd, 0x0006, 1, 0)  # WM_ACTIVATE = 0x0006, WA_ACTIVE = 1
            ctypes.windll.user32.PostMessageW(hwnd, 0x0007, 0, 0)  # WM_SETFOCUS = 0x0007
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
    """掃描所有相關視窗（包含原神 PC 版及常見模擬器或所有可見主視窗），返回 (hwnd, title_with_pid) 列表"""
    windows = []
    
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    
    def enum_window_proc(hwnd, lParam):
        # 1. 必須是可見視窗
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
            
        # 2. 獲取標題
        title = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, 512)
        t_name = title.value.strip()
        if not t_name:
            return True
            
        # 3. 排除常見的系統視窗
        ignore_titles = {
            "Program Manager", "Settings", "Start", "Microsoft Store",
            "NVIDIA GeForce Overlay", "Windows Input Experience", "taskbar",
            "Action Center", "Cortana", "搜索", "Search", "工作管理員", "Task Manager"
        }
        if t_name in ignore_titles:
            return True
            
        # 4. 獲取類別名稱
        class_name = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, class_name, 256)
        c_name = class_name.value
        
        # 排除無關的 Windows 內部類別
        if c_name in ("Windows.UI.Core.CoreWindow", "ApplicationFrameWindow", "Shell_TrayWnd", "IME"):
            return True

        # 5. 獲取 PID
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        lower_title = t_name.lower()
        is_game_or_emulator = (
            c_name == "UnityWndClass" or
            "原神" in t_name or
            "genshin" in lower_title or
            "模擬器" in t_name or
            "player" in lower_title or
            "bluestacks" in lower_title or
            "nox" in lower_title or
            "mumu" in lower_title or
            "雷電" in t_name or
            "夜神" in t_name or
            "逍遙" in t_name
        )
        
        if is_game_or_emulator:
            prefix = "🎮 " if ("原神" in t_name or "genshin" in lower_title) else "📱 "
            windows.append((hwnd, f"{prefix}{t_name} (PID: {pid.value})", 0))  # 優先度 0
        else:
            if len(t_name) >= 2 and "Genshin Lyre Player" not in t_name and "GenshinLyrePlayer" not in t_name:
                windows.append((hwnd, f"🪟 {t_name} (PID: {pid.value})", 1))  # 優先度 1
            
        return True

    callback = WNDENUMPROC(enum_window_proc)
    ctypes.windll.user32.EnumWindows(callback, 0)
    
    # 按照優先度排序，讓原神和模擬器排在最上面！
    windows.sort(key=lambda x: x[2])
    
    return [(w[0], w[1]) for w in windows]


def get_input_target_hwnd(parent_hwnd: int) -> int:
    """如果父視窗是常見模擬器，尋找其內部真正接收鍵盤事件的子視窗；否則直接返回父視窗。"""
    if not parent_hwnd:
        return 0
        
    class_name = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(parent_hwnd, class_name, 256)
    p_class = class_name.value
    
    # 儲存找到的子視窗
    target_child = [parent_hwnd]
    
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    
    # 優先尋找明確的渲染類別名
    def enum_child_proc_priority(hwnd, lParam):
        c_class = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, c_class, 256)
        c_class_val = c_class.value
        
        # 常見模擬器接收輸入的渲染子視窗類名
        if c_class_val in ("RenderWindow", "ScreenWindow", "SgRenderWindow", "subWin"):
            target_child[0] = hwnd
            return False  # 停止尋找
        return True
        
    callback_priority = WNDENUMPROC(enum_child_proc_priority)
    ctypes.windll.user32.EnumChildWindows(parent_hwnd, callback_priority, 0)
    
    # 如果沒找到明確的渲染類別，且為 Qt 相關模擬器，則尋找其內部的 Qt 子視窗
    if target_child[0] == parent_hwnd:
        def enum_child_proc_qt(hwnd, lParam):
            c_class = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, c_class, 256)
            c_class_val = c_class.value
            
            if c_class_val in ("Qt5156QWindowIcon", "Qt5QWindowIcon") and hwnd != parent_hwnd:
                target_child[0] = hwnd
                return False  # 停止尋找
            return True
            
        callback_qt = WNDENUMPROC(enum_child_proc_qt)
        ctypes.windll.user32.EnumChildWindows(parent_hwnd, callback_qt, 0)
        
    return target_child[0]
