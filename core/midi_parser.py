"""
MIDI 解析與音符轉換模組

讀取 MIDI 檔案，提取 BPM / Tempo 資訊，
將標準 MIDI 音符映射到原神風物之詩琴的 21 個按鍵。
支援解析精確的 `note_on` (按下) 和 `note_off` (放開) 時間，
以適應圓號等長音（延音）樂器。
"""

import os
from dataclasses import dataclass, field

import mido
# 解決部分非標準 MIDI 包含損毀的 key_signature 元數據（例如超限的升降音記號）導致 mido.KeySignatureError 崩潰的問題
try:
    import mido.midifiles.meta as meta
    if 0x59 in meta._META_SPECS:
        del meta._META_SPECS[0x59]
    if 'key_signature' in meta._META_SPEC_BY_TYPE:
        del meta._META_SPEC_BY_TYPE['key_signature']
except Exception:
    pass


# ─────────────────────────── GM 樂器分類 ───────────────────────────

GM_INSTRUMENTS = {
    range(0, 8): "Piano", range(8, 16): "Chromatic Perc.",
    range(16, 24): "Organ", range(24, 32): "Guitar",
    range(32, 40): "Bass", range(40, 48): "Strings",
    range(48, 56): "Ensemble", range(56, 64): "Brass",
    range(64, 72): "Reed", range(72, 80): "Pipe/Flute",
    range(80, 88): "Synth Lead", range(88, 96): "Synth Pad",
    range(96, 104): "Synth FX", range(104, 112): "Ethnic",
    range(112, 120): "Percussive", range(120, 128): "Sound FX",
}

SUITABILITY_SCORES = {
    "Piano": 95, "Guitar": 80, "Strings": 85, "Ensemble": 75,
    "Pipe/Flute": 90, "Brass": 70, "Reed": 75, "Organ": 60,
    "Chromatic Perc.": 50, "Ethnic": 65, "Synth Lead": 40,
    "Synth Pad": 20, "Synth FX": 15, "Bass": 30,
    "Percussive": 10, "Sound FX": 5,
}

def _gm_program_to_instrument(program: int) -> str:
    """將 GM Program Number 轉換為樂器類別名稱。"""
    for r, name in GM_INSTRUMENTS.items():
        if program in r:
            return name
    return "Unknown"

def _gm_program_to_suitability(program: int) -> int:
    """將 GM Program Number 轉換為適配分數 (0-100)。"""
    name = _gm_program_to_instrument(program)
    return SUITABILITY_SCORES.get(name, 50)


# ─────────────────────────── 音符映射常數 ───────────────────────────

LYRE_MIN_NOTE = 48   # C3
LYRE_MAX_NOTE = 83   # B5

WHITE_KEY_OFFSETS = [0, 2, 4, 5, 7, 9, 11]

SEMITONE_TO_WHITE = {
    0: 0, 1: 0, 2: 2, 3: 2, 4: 4, 5: 5,
    6: 7, 7: 7, 8: 9, 9: 9, 10: 9, 11: 11,
}

NOTE_TO_KEY = {}

_LOW_KEYS = ['Z', 'X', 'C', 'V', 'B', 'N', 'M']
for i, offset in enumerate(WHITE_KEY_OFFSETS):
    NOTE_TO_KEY[48 + offset] = _LOW_KEYS[i]

_MID_KEYS = ['A', 'S', 'D', 'F', 'G', 'H', 'J']
for i, offset in enumerate(WHITE_KEY_OFFSETS):
    NOTE_TO_KEY[60 + offset] = _MID_KEYS[i]

_HIGH_KEYS = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U']
for i, offset in enumerate(WHITE_KEY_OFFSETS):
    NOTE_TO_KEY[72 + offset] = _HIGH_KEYS[i]


# ─────────────────────────── 資料結構 ───────────────────────────

@dataclass
class KeyEvent:
    """代表一個按鍵操作事件 (按下或放開)。"""
    time_seconds: float       # 距離上一個事件的延遲秒數
    action: str               # 'press' 或 'release'
    keys: list[str]           # 該時間點要操作的按鍵列表
    midi_notes: list[int]     # 原始 MIDI 音符編號（供除錯用）
    velocity: int = 100       # 力度 (0-127)，僅 press 有效


@dataclass
class MidiTrackInfo:
    """MIDI 音軌資訊。"""
    index: int
    name: str
    note_count: int
    instrument: str = "Unknown"   # GM 樂器名稱
    gm_program: int = 0           # GM Program Number
    suitability: int = 50         # 適配分數 (0-100)


@dataclass
class ParsedMidi:
    """MIDI 解析結果。"""
    filename: str
    title: str
    bpm: float
    total_notes: int          # 按下音符的總次數
    duration_seconds: float   # 預估總時長
    events: list[KeyEvent] = field(default_factory=list)  # 播放事件序列
    tracks_info: list[MidiTrackInfo] = field(default_factory=list) # 可用音軌列表


# ─────────────────────────── 音符處理函式 ───────────────────────────

def _clamp_to_range(midi_note: int, wrap_octave: bool = True) -> int | None:
    if wrap_octave:
        while midi_note < LYRE_MIN_NOTE:
            midi_note += 12
        while midi_note > LYRE_MAX_NOTE:
            midi_note -= 12
        return midi_note
    else:
        if LYRE_MIN_NOTE <= midi_note <= LYRE_MAX_NOTE:
            return midi_note
        return None

def _snap_to_white_key(midi_note: int) -> int:
    octave = midi_note // 12
    semitone = midi_note % 12
    white_semitone = SEMITONE_TO_WHITE[semitone]
    return octave * 12 + white_semitone

def midi_note_to_key(midi_note: int, wrap_octave: bool = True) -> str | None:
    note = _clamp_to_range(midi_note, wrap_octave)
    if note is None:
        return None
    note = _snap_to_white_key(note)
    return NOTE_TO_KEY.get(note)


# ─────────────────────────── MIDI 解析 ───────────────────────────

def analyze_best_pitch_shift(filepath: str, enabled_tracks: list[int] | None = None) -> int:
    """
    快速掃描 MIDI 檔案，回傳全曲最佳的基礎平移半音數（黑鍵最少）。
    不會完整轉換為事件序列。
    """
    if filepath.lower().endswith('.txt'):
        return 0
    try:
        midi_file = mido.MidiFile(filepath)
    except Exception:
        return 0
        
    all_notes = []
    for i, track in enumerate(midi_file.tracks):
        # 如果有指定啟用的軌道，且目前軌道不在名單內，則跳過
        if enabled_tracks is not None and i not in enabled_tracks:
            continue
            
        for msg in track:
            if msg.type == 'note_on' and getattr(msg, 'channel', 0) != 9 and msg.velocity > 0:
                all_notes.append(msg.note)
                
    if not all_notes:
        return 0
        
    best_shift = 0
    min_black_keys = float('inf')
    
    for shift in range(-11, 12):
        black_keys = 0
        for note in all_notes:
            semitone = (note + shift) % 12
            if semitone in (1, 3, 6, 8, 10):
                black_keys += 1
                
        if black_keys < min_black_keys or (black_keys == min_black_keys and abs(shift) < abs(best_shift)):
            min_black_keys = black_keys
            best_shift = shift
            
    return best_shift

def parse_midi(
    filepath: str, 
    enabled_tracks: list[int] | None = None,
    pitch_shift: int = 0,
    speed_multiplier: float = 1.0,
    dynamic_shift: bool = False,
    wrap_octave: bool = True,
    chord_threshold: float = 0.005,
    melody_only: bool = False
) -> ParsedMidi:
    """
    解析 MIDI 檔案，提取所有 note_on 和 note_off 事件。
    將它們合併到同一時間軸，並轉換為按鍵序列。
    如果提供了 enabled_tracks，則只載入該清單中的音軌編號 (0-indexed)。
    """
    if filepath.lower().endswith('.txt'):
        return parse_txt_sheet(filepath, speed_multiplier)

    midi_file = mido.MidiFile(filepath)
    ticks_per_beat = midi_file.ticks_per_beat

    filename = os.path.basename(filepath)
    title = os.path.splitext(filename)[0]

    # 格式：(absolute_tick, event_type, data, velocity)
    # velocity 只在 press 時有意義，release/tempo 預設為 0
    all_events = []
    tracks_info = []
    raw_notes = [] # 儲存所有音符 (pitch, start_tick, end_tick, velocity)

    for i, track in enumerate(midi_file.tracks):
        track_name = track.name.strip() if track.name else f"Track {i+1}"
        note_count = sum(1 for m in track if m.type == 'note_on' and getattr(m, 'channel', 0) != 9)
        
        # 偵測 GM 樂器：找出這軌的第一個 program_change
        gm_program = 0
        for m in track:
            if m.type == 'program_change' and getattr(m, 'channel', 0) != 9:
                gm_program = m.program
                break
        
        instrument = _gm_program_to_instrument(gm_program)
        suitability = _gm_program_to_suitability(gm_program)
        
        if note_count > 0:
            tracks_info.append(MidiTrackInfo(
                index=i, name=track_name, note_count=note_count,
                instrument=instrument, gm_program=gm_program, suitability=suitability
            ))

        # 遇到 set_tempo 時，無論這軌有沒有被禁用都要抓出來（有些 MIDI 速度寫在空軌）
        abs_tick = 0
        active_notes = {} # 紀錄每個音符的 (start_tick, velocity)
        for msg in track:
            abs_tick += msg.time
            if msg.type == 'set_tempo':
                all_events.append((abs_tick, 'tempo', msg.tempo, 0))
            elif msg.type in ('note_on', 'note_off'):
                # 忽略打擊樂器通道 (MIDI Channel 10, index 9)
                if getattr(msg, 'channel', 0) == 9:
                    continue
                
                # 如果有指定啟用的軌道，且目前軌道不在名單內，則跳過音符
                if enabled_tracks is not None and i not in enabled_tracks:
                    continue
                
                pitch = msg.note
                vel = msg.velocity if msg.type == 'note_on' else 0
                
                if msg.type == 'note_on' and vel > 0:
                    if pitch in active_notes:
                        # 處理重疊同音符
                        start_tick, prev_vel = active_notes.pop(pitch)
                        raw_notes.append((pitch, start_tick, abs_tick, prev_vel))
                    active_notes[pitch] = (abs_tick, vel)
                else: # note_off 或 velocity == 0
                    if pitch in active_notes:
                        start_tick, prev_vel = active_notes.pop(pitch)
                        raw_notes.append((pitch, start_tick, abs_tick, prev_vel))
        
        # 清理未釋放的音符
        for pitch, (start_tick, vel) in active_notes.items():
            raw_notes.append((pitch, start_tick, abs_tick, vel))

    # 如果啟用 Skyline 主旋律提取，過濾掉伴奏/低音聲部
    if melody_only:
        raw_notes.sort(key=lambda x: x[1]) # 按 start_tick 排序
        filtered_notes = []
        for j, n1 in enumerate(raw_notes):
            pitch1, start1, end1, vel1 = n1
            shadowed = False
            for n2 in raw_notes:
                pitch2, start2, end2, vel2 = n2
                if pitch2 > pitch1:
                    # 檢查時間是否有實質重疊 (ticks)
                    overlap_start = max(start1, start2)
                    overlap_end = min(end1, end2)
                    if overlap_start < overlap_end:
                        # 實質重疊：重疊 ticks 大於一定比例 (例如 10 ticks)
                        if (overlap_end - overlap_start) > 10:
                            shadowed = True
                            break
            if not shadowed:
                filtered_notes.append(n1)
        raw_notes = filtered_notes

    # 將收集到的音符轉換為 press/release 事件
    for pitch, start_tick, end_tick, vel in raw_notes:
        all_events.append((start_tick, 'press', pitch, vel))
        all_events.append((end_tick, 'release', pitch, 0))

    # 按絕對 tick 排序，如果時間相同，先放開後按下
    all_events.sort(key=lambda e: (e[0], 0 if e[1] == 'tempo' else (1 if e[1] == 'release' else 2)))

    # 將 tick 轉換為秒數
    primary_bpm = 120.0
    tempo_found = False

    tempo_changes = []
    for tick, etype, data, _vel in all_events:
        if etype == 'tempo':
            tempo_changes.append((tick, data))
            if not tempo_found:
                primary_bpm = mido.tempo2bpm(data)
                tempo_found = True

    if not tempo_changes:
        tempo_changes = [(0, 500000)]

    def tick_to_seconds(target_tick: int) -> float:
        seconds = 0.0
        prev_tick = 0
        tempo = 500000

        for change_tick, change_tempo in tempo_changes:
            if target_tick <= change_tick:
                break
            delta_ticks = change_tick - prev_tick
            seconds += ((delta_ticks / ticks_per_beat) * (tempo / 1_000_000)) / speed_multiplier
            prev_tick = change_tick
            tempo = change_tempo

        delta_ticks = target_tick - prev_tick
        seconds += ((delta_ticks / ticks_per_beat) * (tempo / 1_000_000)) / speed_multiplier
        return seconds

    # ── 轉調 (Transpose) 演算法 ──
    # key_events_raw: (abs_seconds, etype, key, shifted_data, velocity)
    key_events_raw = []
    
    if not dynamic_shift:
        for tick, etype, data, vel in all_events:
            if etype not in ('press', 'release'):
                continue
            shifted_data = data + pitch_shift
            key = midi_note_to_key(shifted_data, wrap_octave=wrap_octave)
            if key is not None:
                abs_seconds = tick_to_seconds(tick)
                key_events_raw.append((abs_seconds, etype, key, shifted_data, vel))
    else:
        # 動態轉調：播放過程中遇到變調時自動平移
        WINDOW_SIZE = 20
        current_shift = pitch_shift
        active_shifts = {}  # 紀錄每個按下音符所套用的 shift，確保 release 時一致
        
        press_events = [(i, e) for i, e in enumerate(all_events) if e[1] == 'press']
        
        for i, (tick, etype, data, vel) in enumerate(all_events):
            if etype not in ('press', 'release'):
                continue
                
            if etype == 'press':
                # 尋找未來 WINDOW_SIZE 個 press_events
                future_notes = []
                idx = next((pi for pi, (orig_i, _) in enumerate(press_events) if orig_i >= i), -1)
                if idx != -1:
                    future_notes = [e[2] for _, e in press_events[idx : idx + WINDOW_SIZE]]
                
                # 若當前 shift 導致黑鍵，重新評估最佳 shift
                semitone = (data + current_shift) % 12
                if semitone in (1, 3, 6, 8, 10):
                    min_black = float('inf')
                    best_local_shift = current_shift
                    for offset in range(-11, 12):
                        test_shift = pitch_shift + offset
                        blacks = sum(1 for n in future_notes if (n + test_shift) % 12 in (1, 3, 6, 8, 10))
                        
                        if blacks < min_black or (blacks == min_black and abs(offset) < abs(best_local_shift - pitch_shift)):
                            min_black = blacks
                            best_local_shift = test_shift
                            
                    current_shift = best_local_shift
                
                active_shifts[data] = current_shift
                applied_shift = current_shift
            else:
                applied_shift = active_shifts.pop(data, current_shift)
                
            shifted_data = data + applied_shift
            key = midi_note_to_key(shifted_data, wrap_octave=wrap_octave)
            if key is not None:
                abs_seconds = tick_to_seconds(tick)
                key_events_raw.append((abs_seconds, etype, key, shifted_data, vel))

    if not key_events_raw:
        return ParsedMidi(
            filename=filename, title=title, bpm=primary_bpm,
            total_notes=0, duration_seconds=0.0, events=[]
        )

    # 合併同一時刻 (容差 chord_threshold) 的相同動作 (press / release)
    CHORD_THRESHOLD = chord_threshold

    # grouped: (abs_sec, action, keys[], notes[], max_velocity)
    grouped: list[tuple[float, str, list[str], list[int], int]] = []
    
    current_time = key_events_raw[0][0]
    current_action = key_events_raw[0][1]
    current_keys = [key_events_raw[0][2]]
    current_notes = [key_events_raw[0][3]]
    current_vel = key_events_raw[0][4]

    for abs_sec, action, key, midi_note, vel in key_events_raw[1:]:
        if abs_sec - current_time < CHORD_THRESHOLD and action == current_action:
            if key not in current_keys:
                current_keys.append(key)
                current_notes.append(midi_note)
            current_vel = max(current_vel, vel)
        else:
            grouped.append((current_time, current_action, current_keys, current_notes, current_vel))
            current_time = abs_sec
            current_action = action
            current_keys = [key]
            current_notes = [midi_note]
            current_vel = vel

    grouped.append((current_time, current_action, current_keys, current_notes, current_vel))

    # 計算相鄰事件間的延遲
    events = []
    prev_time = 0.0
    total_notes = 0

    for abs_sec, action, keys, notes, vel in grouped:
        delay = max(0.0, abs_sec - prev_time)
        events.append(KeyEvent(
            time_seconds=delay,
            action=action,
            keys=keys,
            midi_notes=notes,
            velocity=vel,
        ))
        prev_time = abs_sec
        if action == 'press':
            total_notes += len(keys)

    duration = grouped[-1][0] if grouped else 0.0

    return ParsedMidi(
        filename=filename,
        title=title,
        bpm=primary_bpm * speed_multiplier,
        total_notes=total_notes,
        duration_seconds=duration,
        events=events,
        tracks_info=tracks_info,
    )


def parse_txt_sheet(filepath: str, speed_multiplier: float = 1.0) -> ParsedMidi:
    """
    解析 .txt 格式的文字鍵盤譜，並生成與 parse_midi 同樣結構的 ParsedMidi 對象。
    """
    import re
    
    filename = os.path.basename(filepath)
    title = os.path.splitext(filename)[0]
    
    # 預設 BPM
    bpm = 120.0
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        # 備用編碼
        try:
            with open(filepath, "r", encoding="gbk", errors="ignore") as f:
                content = f.read()
        except Exception:
            content = ""
            
    # 偵測 BPM
    bpm_match = re.search(r"(?i)bpm\s*[:=]\s*(\d+(\.\d+)?)", content)
    if bpm_match:
        bpm = float(bpm_match.group(1))
        
    # 計算時間間隔
    tick_duration = (30.0 / bpm) / speed_multiplier
    release_duration = min(0.15, tick_duration * 0.7)
    
    lines = content.splitlines()
    current_time = 0.0
    abs_events = []
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        # 1. 排除包含中文字的行（中文歌詞、注釋等）
        if any(ord(c) >= 0x4e00 and ord(c) <= 0x9fff for c in line_str):
            continue
            
        # 2. 判斷是否為音符行
        letters = [c for c in line_str if c.isalpha()]
        if not letters:
            continue
            
        uppercase_valid = [c for c in letters if c.isupper() and c in "QWERTYUASDFGHJZXCVBNM"]
        ratio = len(uppercase_valid) / len(letters)
        if ratio <= 0.8:
            continue
            
        # 3. Tokenize 行
        tokens = []
        i = 0
        while i < len(line_str):
            c = line_str[i]
            if c == ' ':
                tokens.append(('space', 1))
                i += 1
            elif c == '/':
                tokens.append(('slash', 1))
                i += 1
            elif c in ('[', '('):
                end_char = ']' if c == '[' else ')'
                j = line_str.find(end_char, i)
                if j != -1:
                    chord_content = line_str[i+1:j]
                    keys = [k for k in chord_content.upper() if k in "QWERTYUASDFGHJZXCVBNM"]
                    if keys:
                        tokens.append(('chord', keys))
                    i = j + 1
                else:
                    i += 1
            elif c.upper() in "QWERTYUASDFGHJZXCVBNM":
                tokens.append(('note', c.upper()))
                i += 1
            else:
                i += 1
                
        # 4. 生成絕對時間事件
        for token_type, value in tokens:
            if token_type == 'space':
                current_time += tick_duration
            elif token_type == 'slash':
                current_time += 2 * tick_duration
            elif token_type == 'note':
                abs_events.append((current_time, 'press', [value]))
                abs_events.append((current_time + release_duration, 'release', [value]))
                current_time += 0.01
            elif token_type == 'chord':
                abs_events.append((current_time, 'press', value))
                abs_events.append((current_time + release_duration, 'release', value))
                current_time += 0.01
                
        # 換行延遲以區分樂句
        if tokens and tokens[-1][0] not in ('space', 'slash'):
            current_time += tick_duration
        else:
            current_time += tick_duration

    # 按絕對時間與動作排序（release 先行）
    abs_events.sort(key=lambda e: (e[0], 0 if e[1] == 'release' else 1))
    
    # 轉換成 delta time 的 KeyEvent
    events = []
    last_time = 0.0
    total_notes = 0
    
    for abs_time, action, keys in abs_events:
        delta = abs_time - last_time
        last_time = abs_time
        
        events.append(KeyEvent(
            time_seconds=delta,
            action=action,
            keys=keys,
            midi_notes=[],
            velocity=100
        ))
        
        if action == 'press':
            total_notes += len(keys)
            
    # 模擬一個音軌資訊以供 UI 使用
    tracks_info = [MidiTrackInfo(
        index=0,
        name="Text Sheet Track",
        note_count=total_notes,
        instrument="Keyboard Sheet",
        gm_program=0,
        suitability=100
    )]
    
    duration = last_time if last_time > 0 else 0.0
    
    return ParsedMidi(
        filename=filename,
        title=title,
        bpm=bpm * speed_multiplier,
        total_notes=total_notes,
        duration_seconds=duration,
        events=events,
        tracks_info=tracks_info
    )


def scan_midi_folder(folder_path: str) -> list[str]:
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path, exist_ok=True)
        return []

    midi_extensions = {'.mid', '.midi', '.txt'}
    files = []

    for name in sorted(os.listdir(folder_path)):
        ext = os.path.splitext(name)[1].lower()
        if ext in midi_extensions:
            files.append(os.path.join(folder_path, name))

    return files


def export_keyboard_sheet_text(parsed_midi) -> str:
    """
    將解析後的 Midi 轉化為易讀的鍵盤譜文字。
    """
    lines = []
    lines.append(f"曲名: {parsed_midi.title}")
    lines.append(f"原檔名: {parsed_midi.filename}")
    lines.append(f"總音符數: {parsed_midi.total_notes}")
    lines.append(f"BPM: {parsed_midi.bpm:.0f}")
    lines.append("=" * 40)
    lines.append("")
    
    current_line = []
    
    for event in parsed_midi.events:
        if event.action != 'press' or not event.keys:
            continue
            
        # 根據延遲時間決定換行或加空格
        delay = event.time_seconds
        if delay > 1.2:
            # 延遲很大，直接新起一行，且加個空行
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []
            lines.append("")  # 空行
        elif delay > 0.6:
            # 延遲較大，新起一行
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []
        elif delay > 0.3:
            # 延遲中等，加個大間隔
            current_line.append(" ")
            
        # 處理單音與和弦 (去除重複按鍵)
        seen = set()
        keys = []
        for k in event.keys:
            k_up = k.upper()
            if k_up not in seen:
                seen.add(k_up)
                keys.append(k_up)
                
        if len(keys) == 1:
            current_line.append(keys[0])
        elif len(keys) > 1:
            # 和弦用中括號包起來，例如 [QAZ]
            current_line.append(f"[{''.join(keys)}]")
            
    if current_line:
        lines.append(" ".join(current_line))
        
    return "\n".join(lines).strip()

