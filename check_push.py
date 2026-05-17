import requests
t = open(r"C:\Users\Administrator\Desktop\key.txt").read().strip()
h = {"Authorization": f"Bearer {t}"}

api = "https://api.github.com"
for b in ["master", "main"]:
    r = requests.get(f"{api}/repos/ydsgangge-ux/dramatica-flow/branches/{b}", headers=h)
    if r.status_code == 200:
        sha = r.json()["commit"]["sha"][:12]
        print(f"{b}: {sha}")
    else:
        print(f"{b}: not found")