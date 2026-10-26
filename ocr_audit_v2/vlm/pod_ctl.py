"""إنشاء Pod عبر REST بإعدادات محسوبة التكلفة، وتسجيل معرّفه. الإيقاف عبر pod_guard.py.

  python pod_ctl.py create --preset test   --confirm-spend     # Pod رخيص لاختبار الإيقاف (~دقيقة)
  python pod_ctl.py create --preset main   --confirm-spend [--gpu "NVIDIA L40S"] [--volume-gb 40]
  python pod_ctl.py list
المفتاح من RUNPOD_API_KEY (أو متغيرات المستخدم في السجل) ولا يُطبع. --dry-run يعرض الجسم دون اتصال.
"""
import argparse
import json
import os
import sys
import time

import pod_guard as pg

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(os.path.dirname(HERE), "out", "pods.json")
IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"

PRESETS = {
    "test": {"name": "ocr-guard-test", "gpuTypeIds": ["NVIDIA RTX 2000 Ada Generation"], "cloudType": "COMMUNITY",
             "containerDiskInGb": 10, "volumeInGb": 0, "ports": [], "dockerStartCmd": ["sleep", "600"]},
    "main": {"name": "ocr-vlm-compare", "gpuTypeIds": ["NVIDIA L40S"], "cloudType": "COMMUNITY", "containerDiskInGb": 40,
             "volumeInGb": 40, "volumeMountPath": "/workspace", "ports": ["8888/http", "22/tcp"]},
}


def get_key(dry):
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not key and sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, "RUNPOD_API_KEY")[0]
        except OSError:
            pass
    if not key and not dry:
        sys.exit("RUNPOD_API_KEY غير متاح.")
    return key


def post(path, body, key, dry):
    import urllib.request
    url = pg.BASE + path
    if dry:
        print("[dry-run] POST", url, json.dumps(body, ensure_ascii=False))
        return {"id": "DRY", "costPerHr": 0}
    r = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                               headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                        "User-Agent": "curl/8.5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", "?")
        try:
            detail = e.read().decode("utf-8", "ignore")[:400]
        except Exception:  # noqa: BLE001
            detail = ""
        sys.exit(f"فشل الإنشاء: HTTP {code} {detail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["create", "list"])
    ap.add_argument("--preset", choices=list(PRESETS), default="test")
    ap.add_argument("--gpu", default="")
    ap.add_argument("--cloud", default="")
    ap.add_argument("--volume-gb", type=int, default=-1)
    ap.add_argument("--pubkey-file", default="")
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    key = get_key(a.dry_run)
    if a.cmd == "list":
        js = pg.req("GET", "/pods", key, a.dry_run)
        for p in js if isinstance(js, list) else js.get("pods", []):
            print(p.get("id"), p.get("name"), p.get("desiredStatus"), p.get("costPerHr"))
        return
    if not a.confirm_spend and not a.dry_run:
        sys.exit("أضف --confirm-spend: الإنشاء يبدأ الفوترة.")
    body = {"imageName": IMAGE, "gpuCount": 1, "interruptible": False, **PRESETS[a.preset]}
    if a.gpu:
        body["gpuTypeIds"] = [a.gpu]
    if a.cloud:
        body["cloudType"] = a.cloud
    if a.volume_gb >= 0:
        body["volumeInGb"] = a.volume_gb
    if a.pubkey_file:
        body["env"] = {"PUBLIC_KEY": open(a.pubkey_file).read().strip()}
    res = post("/pods", body, key, a.dry_run)
    print("pod:", res.get("id"), "| costPerHr:", res.get("costPerHr"), "| status:", res.get("desiredStatus"))
    if not a.dry_run:
        os.makedirs(os.path.dirname(REG), exist_ok=True)
        reg = json.load(open(REG, encoding="utf-8")) if os.path.exists(REG) else []
        reg.append({"id": res.get("id"), "preset": a.preset, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "costPerHr": res.get("costPerHr")})
        json.dump(reg, open(REG, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
