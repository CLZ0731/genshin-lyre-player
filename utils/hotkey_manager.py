"""
全域快捷鍵管理模組

使用 keyboard 庫註冊全域快捷鍵，支持動態更換按鍵綁定。
即使遊戲視窗處於焦點也能觸發。
"""

import keyboard
from PyQt5.QtCore import QObject, pyqtSignal


class HotkeyManager(QObject):
    """
    全域快捷鍵管理器。

    將 keyboard 庫的回調橋接到 Qt 信號系統，
    確保快捷鍵事件能安全地在主執行緒中處理。

    Signals:
        play_pause_triggered(): 播放/暫停快捷鍵觸發
        next_track_triggered(): 下一首快捷鍵觸發
        prev_track_triggered(): 上一首快捷鍵觸發
        force_stop_triggered(): 強制停止快捷鍵觸發
    """

    play_pause_triggered = pyqtSignal()
    next_track_triggered = pyqtSignal()
    prev_track_triggered = pyqtSignal()
    force_stop_triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registered_hotkeys: list[str] = []
        self._bindings: dict[str, str] = {}

    def register(self, hotkey_config: dict) -> None:
        """
        根據設定註冊全域快捷鍵。

        Args:
            hotkey_config: 快捷鍵設定字典，格式如：
                {
                    "play_pause": "F8",
                    "next_track": "F9",
                    "prev_track": "F7",
                    "force_stop": "F12"
                }
        """
        # 先移除舊的註冊
        self.unregister_all()

        action_signal_map = {
            "play_pause": self.play_pause_triggered,
            "next_track": self.next_track_triggered,
            "prev_track": self.prev_track_triggered,
            "force_stop": self.force_stop_triggered,
        }

        for action, key in hotkey_config.items():
            signal = action_signal_map.get(action)
            if signal and key:
                try:
                    keyboard.add_hotkey(
                        key,
                        signal.emit,
                        suppress=False,  # 不攔截按鍵本身
                    )
                    self._registered_hotkeys.append(key)
                    self._bindings[action] = key
                except Exception as e:
                    print(f"[HotkeyManager] 註冊快捷鍵 {key} 失敗: {e}")

    def unregister_all(self) -> None:
        """移除所有已註冊的全域快捷鍵。"""
        for key in self._registered_hotkeys:
            try:
                keyboard.remove_hotkey(key)
            except (KeyError, ValueError):
                pass  # 已經被移除或不存在
        self._registered_hotkeys.clear()
        self._bindings.clear()

    def update_hotkey(self, action: str, new_key: str) -> bool:
        """
        更新單一快捷鍵綁定。

        Args:
            action: 動作名稱 (play_pause / next_track / prev_track / force_stop)
            new_key: 新的按鍵名稱

        Returns:
            是否更新成功
        """
        old_key = self._bindings.get(action)
        if old_key:
            try:
                keyboard.remove_hotkey(old_key)
                self._registered_hotkeys.remove(old_key)
            except (KeyError, ValueError):
                pass

        action_signal_map = {
            "play_pause": self.play_pause_triggered,
            "next_track": self.next_track_triggered,
            "prev_track": self.prev_track_triggered,
            "force_stop": self.force_stop_triggered,
        }

        signal = action_signal_map.get(action)
        if signal and new_key:
            try:
                keyboard.add_hotkey(new_key, signal.emit, suppress=False)
                self._registered_hotkeys.append(new_key)
                self._bindings[action] = new_key
                return True
            except Exception as e:
                print(f"[HotkeyManager] 更新快捷鍵 {new_key} 失敗: {e}")
                return False
        return False

    @property
    def current_bindings(self) -> dict:
        """取得當前的快捷鍵綁定。"""
        return dict(self._bindings)
