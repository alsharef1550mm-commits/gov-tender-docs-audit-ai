"""No GPU allocation: exercise the password, budget, stop and provider identity boundaries."""
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import model_service as MS
import model_password as MP
import model_remote_guard as RG


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "adapter").mkdir()
        weights = root / "adapter/adapter_model.safetensors"
        weights.write_bytes(b"test adapter only")
        cfg = root / "config.json"
        cfg.write_text(json.dumps({"adapter_dir": "adapter", "adapter_sha256": MS.hashlib.sha256(weights.read_bytes()).hexdigest(), "cap_usd": 2, "max_minutes": 180}))
        pg = Mock()
        pg.req.return_value = []
        pc = Mock()
        with patch.object(MS, "HERE", root), patch.object(MS, "CONFIG", cfg), \
             patch.object(MS, "_api", return_value=(pc, pg, "test-key")), \
             patch.object(MS, "_balance", return_value=1), patch.object(MS, "save_state") as save, \
             patch.object(MS, "stop") as stop, patch.object(MS.subprocess, "Popen") as spawn, \
             patch.object(MS.urllib.request, "urlopen") as request:
            MS._run_start()
            assert "الرصيد" in save.call_args.kwargs["message"]
            request.assert_not_called()
            spawn.assert_not_called()
            stop.assert_called_once_with(keep_message=True)
        with patch.object(MS, "load_state", return_value={"pod_id": "owned"}), \
             patch.object(MS, "_api", return_value=(pc, pg, "test-key")), \
             patch.object(MS, "save_state") as save:
            pg.stop_and_verify.return_value = False
            MS.stop()
            assert "pod_id" not in save.call_args.kwargs, "Failed stop must retain the Pod identity"
            assert save.call_args.kwargs["status"] == "error"
        init = root / "provider.env"
        init.write_bytes(b"RUNPOD_POD_ID=owned\0RUNPOD_API_KEY=provider-test-key\0")
        assert RG.provider_environment("owned", {}, init)["RUNPOD_API_KEY"] == "provider-test-key"
        try:
            RG.provider_environment("wrong", {}, init)
            raise AssertionError("wrong provider identity accepted")
        except AssertionError as exc:
            assert "conflicting" in str(exc)
        assert not RG.own_pod_read("owned", {})["passed"]
    print("PASS: insufficient balance allocates nothing; failed stop preserves Pod; provider identity is scoped")


if __name__ == "__main__":
    main()
