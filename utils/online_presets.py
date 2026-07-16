"""
線上社區預設庫模組

從 GitHub 下載社區共享的 MIDI 最佳設定，並提供比對與快取功能。
"""

import hashlib
import json
import os
import urllib.request
import urllib.error

# 線上預設庫 URL (GitHub Raw)
PRESET_URL = "https://raw.githubusercontent.com/genshin-lyre-community/presets/main/presets.json"
CACHE_FILENAME = "online_presets_cache.json"


def _get_cache_path() -> str:
    """取得快取檔案路徑。"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, CACHE_FILENAME)


def _file_md5(filepath: str) -> str:
    """計算 MIDI 檔案的 MD5 雜湊。"""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, OSError):
        return ""


def fetch_online_presets(timeout: float = 5.0) -> dict:
    """
    從 GitHub 下載社區預設 JSON。
    
    成功時回傳 dict 並更新本地快取。
    失敗時嘗試讀取本地快取。
    若快取也不存在，回傳空 dict。
    """
    cache_path = _get_cache_path()
    
    try:
        req = urllib.request.Request(PRESET_URL, headers={"User-Agent": "GenshinLyrePlayer/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
            # 更新本地快取
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except (IOError, OSError):
                pass
            
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, 
            json.JSONDecodeError, OSError, TimeoutError):
        pass
    
    # 嘗試讀取本地快取
    try:
        if os.path.isfile(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        pass
    
    return {}


def lookup_preset(filepath: str, presets: dict) -> dict | None:
    """
    在預設庫中查找匹配的設定。
    
    先以 MD5 比對，再以檔名比對。
    回傳匹配的設定 dict，或 None。
    """
    if not presets or 'songs' not in presets:
        return None
    
    songs = presets['songs']
    filename = os.path.basename(filepath)
    file_hash = _file_md5(filepath)
    
    # 先以 MD5 精確比對
    if file_hash:
        for entry in songs:
            if entry.get('md5') == file_hash:
                return entry.get('settings')
    
    # 再以檔名模糊比對
    name_no_ext = os.path.splitext(filename)[0].lower()
    for entry in songs:
        entry_name = entry.get('name', '').lower()
        if entry_name and (entry_name == name_no_ext or entry_name in name_no_ext):
            return entry.get('settings')
    
    return None


def export_preset(filepath: str, pitch_shift: int, speed_multiplier: float, 
                  enabled_tracks: list[int] | None, dynamic_shift: bool) -> dict:
    """
    匯出目前的設定為可分享的 JSON 格式。
    """
    filename = os.path.basename(filepath)
    file_hash = _file_md5(filepath)
    
    return {
        "name": os.path.splitext(filename)[0],
        "md5": file_hash,
        "settings": {
            "pitch_shift": pitch_shift,
            "speed_multiplier": speed_multiplier,
            "enabled_tracks": enabled_tracks,
            "dynamic_shift": dynamic_shift,
        }
    }
