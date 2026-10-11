import subprocess, time, sys, json, urllib.request

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
time.sleep(6)

def api(method, path, body=None, token=None):
    url = f"http://127.0.0.1:8765{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

try:
    print("=== health ===")
    print(api("GET", "/health"))

    print("\n=== rooms ===")
    s, r = api("GET", "/api/rooms?page=1&page_size=10")
    d = r["data"]
    print(f"status={s} total={d['total']} items={len(d['items'])}")
    for rm in d["items"]:
        print(f"  id={rm['id']} {rm['name']}")

    print("\n=== seats room 1 ===")
    s, r = api("GET", "/api/rooms/1/seats")
    seats = r["data"]
    print(f"status={s} count={len(seats)}")
    print(f"  first: {seats[0]}")

    print("\n=== availability room 1 ===")
    s, r = api("GET", "/api/rooms/1/availability?date=2026-10-12")
    avail = r["data"]
    print(f"status={s} seats={len(avail['seats'])}")
    print(f"  first: {avail['seats'][0]}")

    print("\n=== register ===")
    print(api("POST", "/api/auth/register", {
        "username": "teststu", "email": "teststu@test.com",
        "password": "123456", "student_id": "20260001", "name": "测试学生"
    }))

    print("\n=== login ===")
    s, r = api("POST", "/api/auth/login", {"username": "teststu", "password": "123456"})
    token = r["data"]["access_token"]
    print(f"status={s} token={token[:20]}...")

    print("\n=== create reservation ===")
    s, r = api("POST", "/api/reservations", {
        "seat_id": 3, "room_id": 1, "reservation_date": "2026-10-12",
        "start_time": "09:00:00", "end_time": "12:00:00"
    }, token)
    print(f"status={s} {r}")
    res_id = r["data"]["id"]

    print("\n=== my reservations ===")
    s, r = api("GET", "/api/reservations", token=token)
    print(f"status={s} count={len(r['data'])}")

    print("\n=== cancel ===")
    s, r = api("PUT", f"/api/reservations/{res_id}/cancel", token=token)
    print(f"status={s} status={r['data']['status']}")

    print("\nALL DONE")
finally:
    proc.terminate()
    proc.wait()
