"""Turn the approved vision model on and off from the app (one RunPod GPU, capped and time-limited).

  on  : create ONE pod (refused if any pod is already running), start the external guard
        (absolute stop + cost cap), upload the approved adapter, merge it, serve it with vLLM,
        open an SSH tunnel to http://127.0.0.1:18080/v1 and mark the service "on".
  off : stop the pod through the guard, close the tunnel, mark "off".
State lives in out/model_service/state.json so the app can show it and survive restarts.
The approved adapter is named in model_service.json (path + SHA-256); nothing else is served.

  python model_service.py status | start | stop
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
VLM = HERE / "vlm"
OUT = HERE / "out" / "model_service"
STATE = OUT / "state.json"
CONFIG = HERE / "model_service.json"
PORT = 18080
GPUS = ["NVIDIA A40", "NVIDIA L40S"]
# Not under AppData: the Microsoft Store Python redirects its AppData writes to a private copy that
# ssh-keygen/ssh (separate programs) cannot see, so key creation failed there.
KEY = Path.home() / ".audit_model" / "ssh_key"
DETACHED = getattr(subprocess, "CREATE_NO_WINDOW", 0) | 0x00000008
SERVE = r"""#!/bin/bash
set -euo pipefail
cd /root/svc
export HF_HOME=/root/hf VLLM_USE_FLASHINFER_SAMPLER=0
step() { echo "$(date -u +%FT%TZ) $1" >> progress.log; }
step setup
python3 -m venv /root/venv
/root/venv/bin/python -m pip install -q vllm==0.32.0 torch==2.13.0 peft==0.21.2 transformers==5.19.0 pillow==13.0.0 ninja
/root/venv/bin/python -m pip install -q --no-deps fla_core-0.5.2-py3-none-any.whl flash_linear_attention-0.5.2-py3-none-any.whl
step merge
tar --no-same-owner -xzf adapter.tar.gz
/root/venv/bin/python merge_candidate_copy.py --adapter adapter --output /root/merged --revision c202236235762e1c871ad0ccb60c8ee5ba337b9a > merge.log 2>&1
step serve
exec /root/venv/bin/vllm serve /root/merged --served-model-name ft --host 127.0.0.1 --port 8000 --dtype bfloat16 \
  --max-model-len 16384 --gpu-memory-utilization 0.85 --enforce-eager --no-enable-prefix-caching \
  --limit-mm-per-prompt '{"image": 1}' --mm-processor-kwargs '{"max_pixels": 2800000}' --max-num-seqs 4 --seed 104729
"""


def now():
    return datetime.now(timezone.utc)


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "off"}


def save_state(**kw):
    OUT.mkdir(parents=True, exist_ok=True)
    s = load_state()
    s.update(kw, updated_utc=now().isoformat())
    text = json.dumps(s, ensure_ascii=False, indent=1)
    tmp = STATE.with_suffix(".tmp")
    # Windows/OneDrive may hold the file for a moment while the app reads it: retry, then write in place.
    for attempt in range(10):
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(STATE)
            return s
        except PermissionError:
            time.sleep(0.15 * (attempt + 1))
    STATE.write_text(text, encoding="utf-8")
    return s


def reachable(url, timeout=4):
    try:
        urllib.request.urlopen(url.rstrip("/") + "/models", timeout=timeout)
        return True
    except Exception:  # noqa: BLE001
        return False


def status():
    """Current state; "on" is confirmed by the model actually answering through the tunnel."""
    s = load_state()
    if s.get("status") == "on" and not reachable(s.get("url", "")):
        s = save_state(status="error", message="الخادم لا يستجيب؛ أعد التشغيل أو أوقفه")
    return s


def _api():
    sys.path.insert(0, str(VLM))
    import pod_ctl as pc
    import pod_guard as pg
    return pc, pg, pc.get_key(False)


def _ssh(host, port, cmd, timeout=60):
    known = KEY.parent / "known_hosts"
    return subprocess.run(["ssh", "-i", str(KEY), "-o", f"UserKnownHostsFile={known}", "-o", "StrictHostKeyChecking=accept-new",
                           "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-p", str(port), f"root@{host}", cmd],
                          capture_output=True, text=True, timeout=timeout)


def start():
    """Spawn the background starter and return at once; progress is written to the state file."""
    s = status()
    if s.get("status") in ("starting", "on"):
        return s
    s = save_state(status="starting", step="تجهيز", message="جارٍ التشغيل", started_utc=now().isoformat(), pod_id=None)
    subprocess.Popen([sys.executable, str(Path(__file__)), "_run_start"], cwd=str(HERE), creationflags=DETACHED,
                     stdout=open(OUT / "start.log", "a"), stderr=subprocess.STDOUT)
    return s


def _run_start():
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        adapter = (HERE / cfg["adapter_dir"]).resolve()
        assert hashlib.sha256((adapter / "adapter_model.safetensors").read_bytes()).hexdigest() == cfg["adapter_sha256"], \
            "النموذج المعتمد تغيّر عن بصمته"
        pc, pg, key = _api()
        if any(p.get("desiredStatus") == "RUNNING" for p in pg.req("GET", "/pods", key, False)):
            raise RuntimeError("يوجد خادم آخر يعمل الآن (مثل التدريب)؛ لا يُشغَّل خادمان معاً")
        if not KEY.exists():
            KEY.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "audit-model", "-f", str(KEY)], check=True)
        public = subprocess.check_output(["ssh-keygen", "-y", "-f", str(KEY)], text=True).strip()
        created, last = None, None
        for gpu in GPUS:
            body = {"name": "audit-model-service", "image": pc.IMAGE, "disk": 80, "cloud": "SECURE", "ports": ["22/tcp"],
                    "env": {"PUBLIC_KEY": public}, "startSsh": True, "gpu": {"id": gpu, "count": 1, "minCudaVersion": "13.0"}}
            req = urllib.request.Request("https://api.runpod.io/v2/pods", data=json.dumps(body).encode(), method="POST",
                                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "curl/8.5.0"})
            try:
                with urllib.request.urlopen(req, timeout=45) as r:
                    created = json.load(r)
                break
            except urllib.error.HTTPError as e:
                last = f"{gpu}: {e.code}"
        if not created:
            raise RuntimeError("لا يتوفر خادم GPU الآن: " + str(last))
        pod = created["id"]
        info = pg.req("GET", "/pods/" + pod, key, False)
        rate = float(info.get("costPerHr") or 0.59)
        minutes, cap = int(cfg.get("max_minutes", 180)), float(cfg.get("cap_usd", 2.0))
        start_utc = now()
        guard = subprocess.Popen([sys.executable, str(VLM / "pod_guard.py"), "watch", "--pod", pod, "--deadline-min", str(minutes),
                                  "--price-per-hour", str(rate), "--cap-usd", str(cap), "--start-utc", start_utc.strftime("%Y-%m-%d %H:%M:%S")],
                                 cwd=str(VLM), creationflags=DETACHED, env=dict(os.environ, PYTHONUTF8="1"),
                                 stdout=open(OUT / "guard.log", "ab"), stderr=subprocess.STDOUT)
        save_state(pod_id=pod, guard_pid=guard.pid, cost_per_hr=rate, cap_usd=cap,
                   stop_utc=(start_utc + timedelta(minutes=min(minutes, cap / rate * 60))).isoformat(), step="حجز الخادم")
        host = port = None
        for _ in range(40):
            info = pg.req("GET", "/pods/" + pod, key, False)
            if info.get("publicIp") and (info.get("portMappings") or {}).get("22"):
                host, port = info["publicIp"], info["portMappings"]["22"]
                if _ssh(host, port, "echo ok", 30).returncode == 0:
                    break
            time.sleep(15)
        else:
            raise RuntimeError("الخادم لم يفتح الاتصال خلال 10 دقائق")
        save_state(step="رفع النموذج")
        with tarfile.open(OUT / "adapter.tar.gz", "w:gz") as t:
            for f in ("adapter_config.json", "adapter_model.safetensors"):
                t.add(adapter / f, arcname="adapter/" + f)
        (OUT / "serve.sh").write_text(SERVE, encoding="utf-8", newline="\n")
        known = KEY.parent / "known_hosts"
        for f in (OUT / "adapter.tar.gz", OUT / "serve.sh") + tuple(HERE / x for x in cfg["support_files"]):
            subprocess.run(["scp", "-q", "-i", str(KEY), "-o", f"UserKnownHostsFile={known}", "-o", "BatchMode=yes", "-P", str(port),
                            str(f), f"root@{host}:/root/svc_in_" + Path(f).name], check=True, timeout=900)
        _ssh(host, port, "mkdir -p /root/svc && for f in /root/svc_in_*; do mv \"$f\" /root/svc/${f#/root/svc_in_}; done && "
                         "(setsid nohup bash /root/svc/serve.sh > /root/svc/serve.log 2>&1 < /dev/null &)", 60)
        save_state(step="تحميل النموذج على الخادم")
        tunnel = subprocess.Popen(["ssh", "-i", str(KEY), "-o", f"UserKnownHostsFile={known}", "-o", "BatchMode=yes",
                                   "-o", "ServerAliveInterval=20", "-o", "ExitOnForwardFailure=yes", "-N",
                                   "-L", f"{PORT}:127.0.0.1:8000", "-p", str(port), f"root@{host}"], creationflags=DETACHED)
        url = f"http://127.0.0.1:{PORT}/v1"
        save_state(tunnel_pid=tunnel.pid, url=url)
        deadline = time.time() + 30 * 60
        while time.time() < deadline:
            if load_state().get("status") != "starting":
                return                                      # the user switched it off meanwhile
            if reachable(url):
                save_state(status="on", step="جاهز", message="النموذج شغال")
                return
            time.sleep(15)
        raise RuntimeError("النموذج لم يجهز خلال 30 دقيقة")
    except Exception as e:  # noqa: BLE001
        save_state(status="error", message=str(e)[:300])
        stop(keep_message=True)


def stop(keep_message=False):
    s = load_state()
    if s.get("pod_id"):
        subprocess.run([sys.executable, str(VLM / "pod_guard.py"), "stop", "--pod", s["pod_id"]], cwd=str(VLM),
                       env=dict(os.environ, PYTHONUTF8="1"), capture_output=True, timeout=300)
    for pid in (s.get("tunnel_pid"), s.get("guard_pid")):
        if pid:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    kw = {"status": "error" if keep_message else "off", "pod_id": None, "tunnel_pid": None, "guard_pid": None, "url": None, "step": None}
    if not keep_message:
        kw["message"] = "النموذج مقفل"
    return save_state(**kw)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    out = {"status": status, "start": start, "stop": stop, "_run_start": _run_start}[cmd]()
    if out is not None:
        print(json.dumps(out, ensure_ascii=False, indent=1))
