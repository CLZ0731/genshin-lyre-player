import os
import sys
import json
import urllib.request
import urllib.error

# 優先從環境變數讀取 TOKEN，若沒有則讀取本地 gitignored 的 github_token.txt 檔案
TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github_token.txt")
    if os.path.exists(token_path):
        with open(token_path, "r", encoding="utf-8") as f:
            TOKEN = f.read().strip()
            
if not TOKEN:
    raise ValueError("找不到 GitHub TOKEN！請設定 GITHUB_TOKEN 環境變數或建立 github_token.txt 檔案。")

OWNER = "CLZ0731"
REPO = "genshin-lyre-player"
TAG_NAME = "v1.13.0"
MSI_FILE = r"dist\GenshinLyrePlayer-1.13.0-win64.msi"
PORTABLE_DIR = r"build\exe.win-amd64-3.12"
ZIP_FILE = r"dist\GenshinLyrePlayer-1.13.0-portable.zip"

def make_request(url, headers, method="GET", payload=None, data=None):
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

def create_release():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    payload = {
        "tag_name": TAG_NAME,
        "name": f"Genshin Lyre Player {TAG_NAME}",
        "body": "## 更新內容\n- **新增「自動/手動匯出文字檔鍵盤譜」功能**：\n  - **自動匯出**：於參數設定新增「自動匯出鍵盤譜」核取方塊。啟用後，當播放完畢時，程式會自動將該 MIDI 樂曲轉換為精心排版、可讀性極高的純文字鍵盤譜檔 (.txt) 並自動開啟。\n  - **一鍵手動匯出**：在音軌設定旁新增「匯出鍵盤譜」按鈕，讓您可以不用聽完整首歌，隨時一鍵直接轉換並在 exports 資料夾生成文字鍵盤譜。\n  - **高可讀性鍵盤譜排版**：單音與和弦（中括號 [] 包裹）分明，且依據音符延遲時間進行貼心的自動空格拉開與換行，完美符合玩家日常彈奏與練習習慣！",
        "draft": False,
        "prerelease": False
    }
    
    print(f"正在創建 Release {TAG_NAME}...")
    status, result = make_request(url, headers, method="POST", payload=payload)
    if status == 201:
        print(f"成功創建 Release! ID: {result['id']}")
        return result['id']
    elif status == 422 and "already_exists" in str(result):
        print("Release 已存在，將取得現有 Release ID...")
        # 取得已存在的 release
        status, result = make_request(f"https://api.github.com/repos/{OWNER}/{REPO}/releases/tags/{TAG_NAME}", headers)
        if status == 200:
            return result['id']
    
    print(f"創建 Release 失敗: {status} - {result}")
    return None

def upload_asset(release_id, file_path):
    if not os.path.exists(file_path):
        print(f"找不到檔案: {file_path}")
        return False
        
    name = os.path.basename(file_path)
    url = f"https://uploads.github.com/repos/{OWNER}/{REPO}/releases/{release_id}/assets?name={name}"
    
    with open(file_path, "rb") as f:
        data = f.read()
        
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/octet-stream"
    }
    
    print(f"正在上傳安裝包 {name} (大小: {len(data)/1024/1024:.2f} MB)...")
    status, result = make_request(url, headers, method="POST", data=data)
    
    if status == 201:
        print("上傳成功！")
        return True
    else:
        print(f"上傳失敗: {status} - {result}")
        return False

def main():
    # 建立 ZIP 免安裝版
    print(f"正在打包免安裝版 ZIP...")
    import shutil
    import os
    
    if not os.path.exists("dist"):
        os.makedirs("dist")
        
    # shutil.make_archive 會自動加上 .zip 副檔名，所以要把 ZIP_FILE 去除 .zip
    zip_base = ZIP_FILE[:-4] if ZIP_FILE.endswith(".zip") else ZIP_FILE
    shutil.make_archive(zip_base, 'zip', PORTABLE_DIR)
    
    release_id = create_release()
    if release_id:
        upload_asset(release_id, MSI_FILE)
        upload_asset(release_id, ZIP_FILE)

if __name__ == "__main__":
    main()
