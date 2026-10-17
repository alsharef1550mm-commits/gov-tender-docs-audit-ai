"""مراقب إيقاف خارجي يعمل على جهازك (لا على الـPod) ويوقف الـPod عند الموعد أو عند تجاوز السقف.

المفتاح من متغير بيئة `RUNPOD_API_KEY` فقط (يضعه المستخدم؛ لا يُكتب في أي ملف ولا يُطبع).
واجهة REST الموثقة: POST https://rest.runpod.io/v1/pods/{id}/stop  و  GET /v1/pods/{id}  (Authorization: Bearer).

الأوامر:
  python pod_guard.py status  --pod ID
  python pod_guard.py stop    --pod ID                       # إيقاف فوري + تحقق
  python pod_guard.py watch   --pod ID --deadline-min 180 --price-per-hour 0.99 --cap-usd 8
  أي أمر + --dry-run  يطبع ما سيفعله دون أي اتصال (للاختبار قبل التشغيل الحقيقي)
"""
import argparse
import json
import os
import sys
import time
import urllib.request

BASE = "https://rest.runpod.io/v1"


def req(method, path, key, dry):
    url = BASE + path
    if dry:
        print(f"[dry-run] {method} {url}  (Authorization: Bearer ***)")
        return {"desiredStatus": "DRY"}
    r = urllib.request.Request(url, method=method, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                                         "User-Agent": "curl/8.5.0", "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        body = resp.read()
    return json.loads(body) if body else {}


def status(pod, key, dry):
    js = req("GET", f"/pods/{pod}", key, dry)
    return js.get("desiredStatus"), js


def safe_status(pod, key, dry):
    """خطأ شبكة لا يُسقط المراقب: يعيد (None, {}) ويستمر."""
    try:
        return status(pod, key, dry)
    except Exception as e:  # noqa: BLE001
        print("status read failed:", type(e).__name__, e, flush=True)
        return None, {}


def parse_utc(s):
    """'2026-10-15 18:17:34.974 +0000 UTC' أو '2026-10-15 18:17:34' => epoch (UTC)."""
    import calendar
    import re
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s or "")
    return calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0)) if m else None


def stop_and_verify(pod, key, dry, tries=8):
    for i in range(tries):
        try:
            req("POST", f"/pods/{pod}/stop", key, dry)
        except Exception as e:  # noqa: BLE001
            print("stop attempt", i + 1, "failed:", type(e).__name__, e, flush=True)
        time.sleep(0 if dry else 10)
        st, _ = safe_status(pod, key, dry)
        print("status after stop:", st, flush=True)
        if dry or st in ("EXITED", "STOPPED", "TERMINATED"):
            return True
    print("!!! لم يتأكد الإيقاف. أوقف الـPod يدوياً من لوحة التحكم الآن.")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "info", "stop", "watch"])
    ap.add_argument("--pod", required=True)
    ap.add_argument("--deadline-min", type=float, default=180)
    ap.add_argument("--price-per-hour", type=float, default=1.0)
    ap.add_argument("--cap-usd", type=float, default=8.0)
    ap.add_argument("--start-utc", default="", help="بداية الحساب بتوقيت UTC (الافتراضي lastStartedAt من الـPod)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not key and sys.platform == "win32":
        # تطبيقات Windows الجارية لا ترى setx الجديد؛ اقرأه من متغيرات المستخدم المحفوظة (لا يُطبع)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, "RUNPOD_API_KEY")[0]
        except OSError:
            key = ""
    if not key and not a.dry_run:
        sys.exit("ضع RUNPOD_API_KEY في متغيرات البيئة (مفتاح مقيّد) ثم أعد التشغيل.")
    if a.cmd == "info":
        js = status(a.pod, key, a.dry_run)[1]
        print(json.dumps({k: js.get(k) for k in ("id", "desiredStatus", "costPerHr", "publicIp", "portMappings", "gpu", "image",
                                                  "lastStartedAt")}, ensure_ascii=False, default=str))
    elif a.cmd == "status":
        print(status(a.pod, key, a.dry_run)[0])
    elif a.cmd == "stop":
        stop_and_verify(a.pod, key, a.dry_run)
    else:
        # الموعد مطلق من بدء الـPod نفسه (lastStartedAt) لا من بدء المراقب
        t0 = time.time()
        if a.start_utc:
            t0 = parse_utc(a.start_utc) or t0
        else:
            _, js0 = safe_status(a.pod, key, a.dry_run)
            t0 = parse_utc(str(js0.get("lastStartedAt", ""))) or t0
        # الأقل بين الموعد وما يسمح به السقف عند السعر المعلن (مع هامش 10%)؛ السقف تقدير لا حدّ آلي من RunPod
        cap_min = a.cap_usd / (a.price_per_hour * 1.1) * 60
        limit = min(a.deadline_min, cap_min)
        stop_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t0 + limit * 60))
        print(f"يراقب الـPod {a.pod}: موعد الإيقاف المطلق {stop_at} ({limit:.0f} دقيقة من بدئه؛ موعد {a.deadline_min:.0f}، سقف {a.cap_usd}$ ≈ {cap_min:.0f})", flush=True)
        fails = 0
        while True:
            el = (time.time() - t0) / 60
            st, _ = safe_status(a.pod, key, a.dry_run)
            fails = fails + 1 if st is None else 0
            print(f"{time.strftime('%H:%M:%S', time.gmtime())}Z | {el:.0f} دقيقة | الحالة {st} | أخطاء قراءة متتالية {fails}", flush=True)
            if st in ("EXITED", "STOPPED", "TERMINATED"):
                print("الـPod متوقف بالفعل. انتهت المراقبة.")
                return
            if el >= limit or a.dry_run:
                stop_and_verify(a.pod, key, a.dry_run)
                return
            time.sleep(60)


if __name__ == "__main__":
    main()
