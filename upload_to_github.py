import os
import sys
import base64
import json
import urllib.request
import urllib.error
import urllib.parse

# 要忽略的目錄與檔案
IGNORE_DIRS = {'build', 'dist', '__pycache__', '.git', '.venv', 'venv', 'GenshinLyrePlayer.egg-info'}
IGNORE_FILES = {'config.json', 'diagnostic.txt', 'GenshinLyrePlayer.spec', 'upload_to_github.py'}

def safe_print(message):
    """防止在 Big5 (cp950) 終端機下列印日文等特殊字元時崩潰"""
    try:
        print(message)
    except UnicodeEncodeError:
        try:
            enc = sys.stdout.encoding or 'utf-8'
            print(message.encode(enc, errors='replace').decode(enc))
        except Exception:
            # 最後的防線：直接轉為純 ASCII 或忽略錯誤
            print(message.encode('ascii', errors='ignore').decode('ascii'))

def should_ignore(path, root_dir):
    rel_path = os.path.relpath(path, root_dir)
    parts = rel_path.split(os.sep)
    
    # 檢查目錄
    for part in parts[:-1]:
        if part in IGNORE_DIRS:
            return True
            
    # 檢查檔名
    filename = parts[-1]
    if filename in IGNORE_FILES:
        return True
    if filename.endswith('.lnk') or filename.endswith('.pyc') or filename.endswith('.log'):
        return True
        
    return False

def make_request(url, headers, method="GET", payload=None):
    data = None
    if payload:
        data = json.dumps(payload).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            res_data = json.loads(e.read().decode("utf-8"))
        except Exception:
            res_data = e.reason
        return e.code, res_data
    except Exception as e:
        return -1, str(e)

def create_github_repo(token, repo_name, is_private=False):
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GenshinLyrePlayer-Uploader",
        "Content-Type": "application/json"
    }
    payload = {
        "name": repo_name,
        "description": "Genshin Impact Lyre Auto Player with AI Audio-to-MIDI transcription",
        "private": is_private,
        "auto_init": False
    }
    
    safe_print(f"[API] 正在創建 GitHub 倉庫: {repo_name}...")
    status, result = make_request(url, headers, method="POST", payload=payload)
    if status == 201:
        safe_print(f"[OK] 成功創建倉庫! 網址: {result['html_url']}")
        return True
    elif status == 422:
        # 倉庫已存在
        safe_print("[INFO] 倉庫已存在，將直接開始上傳檔案...")
        return True
    else:
        safe_print(f"[FAIL] 創建倉庫失敗 (狀態碼: {status})")
        safe_print(result)
        return False

def upload_file(token, owner, repo, local_path, git_path):
    # 進行 URL 百分比編碼，解決中文路徑（例如：啟動.bat）導致 urlopen 拋出 ascii 編碼錯誤的問題
    quoted_path = urllib.parse.quote(git_path)
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{quoted_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GenshinLyrePlayer-Uploader",
        "Content-Type": "application/json"
    }
    
    try:
        with open(local_path, "rb") as f:
            content_bytes = f.read()
        content_b64 = base64.b64encode(content_bytes).decode("utf-8")
    except Exception as e:
        safe_print(f"[FAIL] 無法讀取本地檔案 {local_path}: {e}")
        return False
    
    # 檢查檔案是否已存在，若存在獲取 sha
    sha = None
    status, result = make_request(url, headers, method="GET")
    if status == 200:
        sha = result["sha"]
        
    payload = {
        "message": f"Upload {git_path} via API",
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha
        
    status, result = make_request(url, headers, method="PUT", payload=payload)
    if status in (200, 201):
        safe_print(f"[OK] 已上傳: {git_path}")
        return True
    else:
        safe_print(f"[FAIL] 上傳失敗: {git_path} (狀態碼: {status})")
        safe_print(result)
        return False

def main():
    safe_print("="*60)
    safe_print("[+] 免 Git 直接上傳專案至 GitHub 工具 (無依賴 Big5 相容版)")
    safe_print("="*60)
    
    username = None
    token = None
    
    # 支援從命令列參數傳入
    if len(sys.argv) >= 3:
        username = sys.argv[1].strip()
        token = sys.argv[2].strip()
        
    if not username:
        username = input("請輸入你的 GitHub 帳號名稱 (Username): ").strip()
    if not username:
        safe_print("錯誤: 帳號名稱不能為空。")
        return
        
    if not token:
        token = input("請貼上你的 GitHub Personal Access Token (PAT): ").strip()
    if not token:
        safe_print("錯誤: Token 不能為空。")
        return
        
    repo_name = "genshin-lyre-player"
    
    # 1. 創立倉庫
    if not create_github_repo(token, repo_name, is_private=False):
        safe_print("上傳終止。")
        return
        
    # 2. 遍歷目錄上傳檔案
    root_dir = os.getcwd()
    success_count = 0
    fail_count = 0
    
    safe_print("\n[開始上傳檔案]...")
    for root, dirs, files in os.walk(root_dir):
        # 排除忽略目錄
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            local_path = os.path.join(root, file)
            if should_ignore(local_path, root_dir):
                continue
                
            # 計算在 Git 上的相對路徑
            git_path = os.path.relpath(local_path, root_dir).replace(os.sep, '/')
            
            # 執行上傳
            if upload_file(token, username, repo_name, local_path, git_path):
                success_count += 1
            else:
                fail_count += 1
                
    safe_print("\n" + "="*60)
    safe_print(f"[FINISHED] 上傳完成! 成功: {success_count} 筆, 失敗: {fail_count} 筆")
    safe_print(f"專案 GitHub 網址: https://github.com/{username}/{repo_name}")
    safe_print("="*60 + "\n")

if __name__ == "__main__":
    main()
