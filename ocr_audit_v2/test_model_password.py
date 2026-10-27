"""Model start password: hash only, right/wrong answers, and the temporary lock (uses a temp file, never the real one)."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

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
        with patch.object(MP, "SEED", Path(tmp) / "no-seed.json"):
            assert not MP.is_set() and MP.check("x")[0] is False


def test_deployment_seed_and_corrupt_state():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        seed = Path(tmp) / "seed.json"
        seed.write_bytes(MP.FILE.read_bytes())
        MP.FILE.unlink()
        with patch.object(MP, "SEED", seed):
            assert MP.check("test-only-value") == (True, "")
            MP.FILE.write_text("broken")
            assert not MP.check("test-only-value")[0]


def test_service_gate_no_password_no_side_effects():
    import model_service as MS
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        with patch.object(MS, "status") as status, patch.object(MS, "save_state") as save, \
                patch.object(MS.subprocess, "Popen") as spawn, patch.object(MS, "_api") as provider:
            for password in (None, "", "incorrect"):
                try:
                    MS.start(password)
                    raise AssertionError("unauthenticated start accepted")
                except PermissionError:
                    pass
            status.assert_not_called()
            save.assert_not_called()
            spawn.assert_not_called()
            provider.assert_not_called()
            status.return_value = {"status": "on"}
            assert MS.start("test-only-value") == {"status": "on"}
            status.assert_called_once()
            spawn.assert_not_called()


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)


if __name__ == "__main__":
    main()
