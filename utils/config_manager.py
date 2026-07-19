"""
設定檔管理模組

讀寫 config.json，管理使用者偏好設定（快捷鍵、延遲參數等）。
"""

import json
import os

DEFAULT_CONFIG = {
    "hotkeys": {
        "play_pause": "F8",
        "next_track": "F9",
        "prev_track": "F7",
        "force_stop": "F12",
    },
    "press_delay_min": 0.02,
    "press_delay_max": 0.05,
    "transcribe_sensitivity": "medium",
    "track_preferences": {},
    "auto_export_sheet": True,
}


class ConfigManager:
    """
    設定檔管理器。

    自動載入 config.json，若檔案不存在則建立預設配置。
    提供讀取與儲存設定的方法。
    """

    def __init__(self, config_path: str = None):
        if config_path is None:
            # 預設為程式所在目錄的 config.json
            import sys
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.json")

        self._config_path = config_path
        self._config: dict = {}
        self.load()

    def load(self) -> dict:
        """載入設定檔，不存在則建立預設配置。"""
        if os.path.isfile(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._config = dict(DEFAULT_CONFIG)
                self.save()
        else:
            self._config = dict(DEFAULT_CONFIG)
            self.save()

        # 確保所有預設鍵都存在
        for key, value in DEFAULT_CONFIG.items():
            if key not in self._config:
                self._config[key] = value

        return self._config

    def save(self) -> None:
        """儲存設定到 config.json。"""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    @property
    def hotkeys(self) -> dict:
        """取得快捷鍵設定。"""
        return self._config.get("hotkeys", DEFAULT_CONFIG["hotkeys"])

    @hotkeys.setter
    def hotkeys(self, value: dict) -> None:
        """設定快捷鍵並儲存。"""
        self._config["hotkeys"] = value
        self.save()

    @property
    def press_delay_min(self) -> float:
        return self._config.get("press_delay_min", DEFAULT_CONFIG["press_delay_min"])

    @property
    def press_delay_max(self) -> float:
        return self._config.get("press_delay_max", DEFAULT_CONFIG["press_delay_max"])

    @property
    def transcribe_sensitivity(self) -> str:
        return self._config.get("transcribe_sensitivity", "medium")

    @transcribe_sensitivity.setter
    def transcribe_sensitivity(self, value: str) -> None:
        self._config["transcribe_sensitivity"] = value
        self.save()

    @property
    def auto_export_sheet(self) -> bool:
        return self._config.get("auto_export_sheet", DEFAULT_CONFIG["auto_export_sheet"])

    @auto_export_sheet.setter
    def auto_export_sheet(self, value: bool) -> None:
        self._config["auto_export_sheet"] = value
        self.save()

    def get(self, key: str, default=None):
        """取得設定值。"""
        return self._config.get(key, default)

    def set(self, key: str, value) -> None:
        """設定值並儲存。"""
        self._config[key] = value
        self.save()

    def get_track_pref(self, filename: str) -> dict:
        """取得特定音軌的儲存偏好設定。"""
        prefs = self._config.get("track_preferences", {})
        return prefs.get(filename, {})

    def set_track_pref(self, filename: str, pitch_shift: int, speed_multiplier: float, enabled_tracks: list[int] | None, dynamic_shift: bool, velocity_dynamics: bool = True, wrap_octave: bool = True, chord_threshold: float = 0.005, melody_only: bool = False) -> None:
        """儲存特定音軌的偏好設定。"""
        if "track_preferences" not in self._config:
            self._config["track_preferences"] = {}
        
        self._config["track_preferences"][filename] = {
            "pitch_shift": pitch_shift,
            "speed_multiplier": speed_multiplier,
            "enabled_tracks": enabled_tracks,
            "dynamic_shift": dynamic_shift,
            "velocity_dynamics": velocity_dynamics,
            "wrap_octave": wrap_octave,
            "chord_threshold": chord_threshold,
            "melody_only": melody_only
        }
        self.save()

    def clear_track_pref(self, filename: str) -> None:
        """清除特定音軌的儲存偏好設定。"""
        if "track_preferences" in self._config:
            if filename in self._config["track_preferences"]:
                del self._config["track_preferences"][filename]
                self.save()
