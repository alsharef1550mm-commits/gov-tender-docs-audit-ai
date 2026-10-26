"""Model start password: hash only, right/wrong answers, and the temporary lock (uses a temp file, never the real one)."""
import json
import tempfile
from pathlib import Path

import model_password as MP


def setup(tmp):
    MP.FILE = Path(tmp) / "switch_password.json"
    salt = "00" * 16
    MP._save({"salt": salt, "hash": MP._derive("test-only-value", salt), "fails": 0, "locked_until": None})


def test_only_hash_is_stored():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        assert "test-only-value" not in MP.FILE.read_text(encoding="utf-8")


def test_right_and_wrong():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        assert MP.check("wrong")[0] is False
        assert MP.check("test-only-value") == (True, "")
        assert json.loads(MP.FILE.read_text())["fails"] == 0


def test_lock_after_five_wrong():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        for _ in range(MP.MAX_TRIES):
            MP.check("wrong")
        ok, why = MP.check("test-only-value")
        assert not ok and "مقفل" in why, why


def test_unset_password_refuses():
    with tempfile.TemporaryDirectory() as tmp:
        MP.FILE = Path(tmp) / "none.json"
        assert not MP.is_set() and MP.check("x")[0] is False


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
