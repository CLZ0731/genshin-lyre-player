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
TAG_NAME = "v1.12.0"
MSI_FILE = r"dist\GenshinLyrePlayer-1.12.0-win64.msi"
PORTABLE_DIR = r"build\exe.win-amd64-3.12"
ZIP_FILE = r"dist\GenshinLyrePlayer-1.12.0-portable.zip"

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
        "body": "## 更新內容\n- **新增單一程式「雙目標視窗」同步演奏功能（無延遲雙開聯彈）**：\n  - **主介面直接選取雙視窗**：現在不需要開啟兩個程式並用網路配對碼連線了！主介面直接新增「主控視窗」與「協同視窗」兩個下拉選單。\n  - **視覺化音域分配**：主控視窗與協同視窗右側皆新增「低/中/高」音域勾選框。您可以自由指定哪一區音軌在主控視窗（如 PC 原神）彈奏，哪一區音軌在協同視窗（如安卓模擬器）彈奏！\n  - **完美解決延遲與操作繁瑣問題**：完全消除了網路通訊帶來的任何微小延遲。同時只須執行一個軟體即可直接控制兩個遊戲客戶端，體驗極致流暢的二重奏！",
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
