import json, urllib.request

BASE = "http://127.0.0.1:8010"
r = urllib.request.Request(BASE + "/api/auth/login", method="POST")
r.add_header("Content-Type", "application/json")
tok = json.loads(urllib.request.urlopen(r, json.dumps({"usuario": "admin", "password": "admin123"}).encode()).read())["access_token"]

r2 = urllib.request.Request(BASE + "/api/auth/me", headers={"Authorization": "Bearer " + tok})
resp = urllib.request.urlopen(r2)
data = json.loads(resp.read())
print(f"Login OK: {data}")