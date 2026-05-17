import os, base64, sys, traceback
import requests

TOKEN = open(r"C:\Users\Administrator\Desktop\key.txt").read().strip()
REPO = "ydsgangge-ux/dramatica-flow"
TARGET = "master"
EMAIL = "ydsgangge@gmail.com"
NAME = "ydsgangge-ux"
WORK_DIR = r"h:\测试\dramatica-flow-main"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github.v3+json"}
API = "https://api.github.com"

IGNORE_DIRS = {"__pycache__", ".git", ".pytest_cache", ".egg-info"}
IGNORE_FILES = {"push_to_github.py", "check_push.py", "push_log.txt"}

def log(msg):
    print(msg)
    sys.stdout.flush()

try:
    log("=== 开始推送 ===")
    log(f"Token: {TOKEN[:10]}...")

    # 检查仓库
    r = requests.get(f"{API}/repos/{REPO}", headers=HEADERS)
    log(f"仓库检查: {r.status_code}")
    if r.status_code == 404:
        r = requests.post(f"{API}/user/repos", headers=HEADERS,
                          json={"name": "dramatica-flow", "private": False})
        r.raise_for_status()
        log("仓库已创建")

    # 获取文件列表
    files = []
    for root, dirs, entries in os.walk(WORK_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for f in entries:
            if f in IGNORE_FILES or f.endswith(".pyc") or f == ".gitkeep":
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, WORK_DIR).replace("\\", "/")
            files.append((rel, full))
    files.sort()
    n = len(files)
    log(f"共 {n} 个文件")

    # 创建 blobs
    tree = []
    for i, (rel, full) in enumerate(files, 1):
        with open(full, "rb") as f:
            data = f.read()
        try:
            txt = data.decode("utf-8")
            p = {"content": txt, "encoding": "utf-8"}
        except UnicodeDecodeError:
            p = {"content": base64.b64encode(data).decode(), "encoding": "base64"}
        r = requests.post(f"{API}/repos/{REPO}/git/blobs", headers=HEADERS, json=p)
        r.raise_for_status()
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": r.json()["sha"]})
        if i % 50 == 0:
            log(f"  blobs: {i}/{n}")
    log(f"所有 blobs 创建完成 ({n})")

    # 查找 parent
    r = requests.get(f"{API}/repos/{REPO}/git/ref/heads/{TARGET}", headers=HEADERS)
    parent = None
    if r.status_code == 200:
        parent = r.json()["object"]["sha"]
        log(f"master 已存在: {parent[:12]}")
    else:
        r2 = requests.get(f"{API}/repos/{REPO}/git/ref/heads/main", headers=HEADERS)
        if r2.status_code == 200:
            parent = r2.json()["object"]["sha"]
            log(f"基于 main: {parent[:12]}")

    base_tree = None
    if parent:
        r3 = requests.get(f"{API}/repos/{REPO}/git/commits/{parent}", headers=HEADERS)
        base_tree = r3.json()["tree"]["sha"]

    # 创建 tree
    tp = {"tree": tree}
    if base_tree:
        tp["base_tree"] = base_tree
    r = requests.post(f"{API}/repos/{REPO}/git/trees", headers=HEADERS, json=tp)
    r.raise_for_status()
    tree_sha = r.json()["sha"]
    log(f"tree: {tree_sha[:12]}")

    # 创建 commit
    cp = {
        "message": "feat: 支持所有 OpenAI 兼容模型",
        "tree": tree_sha,
        "parents": [parent] if parent else [],
        "author": {"name": NAME, "email": EMAIL}
    }
    r = requests.post(f"{API}/repos/{REPO}/git/commits", headers=HEADERS, json=cp)
    r.raise_for_status()
    commit_sha = r.json()["sha"]
    log(f"commit: {commit_sha[:12]}")

    # 更新分支
    ref = f"refs/heads/{TARGET}"
    if parent:
        r = requests.patch(f"{API}/repos/{REPO}/git/refs/{ref}", headers=HEADERS,
                           json={"sha": commit_sha, "force": True})
        r.raise_for_status()
    else:
        r = requests.post(f"{API}/repos/{REPO}/git/refs", headers=HEADERS,
                          json={"ref": ref, "sha": commit_sha})
        r.raise_for_status_code = r.status_code
        r.raise_for_status()
        log(f"分支创建: {r.status_code}")
    log(f"✅ 推送成功！https://github.com/{REPO}/tree/{TARGET}")

except Exception as e:
    log(f"❌ 错误: {e}")
    traceback.print_exc()
    sys.exit(1)