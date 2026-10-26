"""Password that guards turning the vision model ON (turning it off never needs it).

Only a salted PBKDF2-SHA256 hash is stored, in %LOCALAPPDATA%\\audit_model\\switch_password.json,
outside the project. Five wrong attempts lock starting for ten minutes.

Set or change it (typed by the owner, never echoed):  python model_password.py
"""
from datetime import datetime, timedelta, timezone
from getpass import getpass
from pathlib import Path
import hashlib
import hmac
import json
import os
import secrets

FILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "audit_model" / "switch_password.json"
ROUNDS = 240_000
MAX_TRIES, LOCK_MIN = 5, 10


def _derive(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ROUNDS).hex()


def _load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(data):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(FILE)


def is_set():
    return bool((_load() or {}).get("hash"))


def check(password):
    """Return (ok, message). Counts failures and enforces the temporary lock."""
    data = _load()
    if not data or not data.get("hash"):
        return False, "لم يُضبط باسورد التشغيل بعد: شغّل الأمر python ocr_audit_v2/model_password.py"
    now = datetime.now(timezone.utc)
    until = data.get("locked_until")
    if until and datetime.fromisoformat(until) > now:
        return False, "التشغيل مقفل مؤقتاً بعد محاولات خاطئة؛ حاول بعد %d دقيقة" % (
            int((datetime.fromisoformat(until) - now).total_seconds() // 60) + 1)
    if hmac.compare_digest(_derive(password or "", data["salt"]), data["hash"]):
        data.update(fails=0, locked_until=None)
        _save(data)
        return True, ""
    data["fails"] = int(data.get("fails", 0)) + 1
    if data["fails"] >= MAX_TRIES:
        data.update(fails=0, locked_until=(now + timedelta(minutes=LOCK_MIN)).isoformat())
        _save(data)
        return False, "باسورد غير صحيح؛ أُقفل التشغيل %d دقائق" % LOCK_MIN
    _save(data)
    return False, "باسورد غير صحيح (تبقّى %d محاولات)" % (MAX_TRIES - data["fails"])


def main():
    first = getpass("باسورد تشغيل النموذج الجديد: ")
    if len(first) < 6:
        print("قصير جداً: 6 أحرف على الأقل")
        return
    if getpass("أعد كتابته للتأكيد: ") != first:
        print("غير متطابقين؛ لم يُحفظ شيء")
        return
    salt = secrets.token_hex(16)
    _save({"salt": salt, "hash": _derive(first, salt), "fails": 0, "locked_until": None,
           "set_utc": datetime.now(timezone.utc).isoformat()})
    print("حُفظ (البصمة فقط) في", FILE)


if __name__ == "__main__":
    main()
