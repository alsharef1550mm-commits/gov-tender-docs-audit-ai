"""Prepare an allowlisted HF update; no upload, provider call, secret read or GPU start."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request


def build(output):
    root = Path(__file__).resolve().parent
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    cfg = json.loads((root / "model_service.json").read_text(encoding="utf-8"))
    adapter = root / cfg["adapter_dir"]
    with (adapter / "adapter_model.safetensors").open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == cfg["adapter_sha256"]
    files = [(adapter / f, "model_assets/adapter/" + f)
             for f in ("adapter_config.json", "adapter_model.safetensors")]
    files.extend((root / p, "model_assets/" + Path(p).name) for p in cfg["support_files"])
    files.extend((root / "vlm" / p, "vlm/" + p) for p in ("pod_ctl.py", "pod_guard.py"))
    with tarfile.open(output / "model_assets.tar.gz", "w:gz", compresslevel=1) as archive:
        for source, destination in files:
            assert source.is_file() and not source.is_symlink()
            archive.add(source, arcname=destination)
    cfg["adapter_dir"] = "model_assets/adapter"
    cfg["support_files"] = ["model_assets/" + Path(x).name for x in cfg["support_files"]]
    cfg.pop("fallback", None)  # Local backup is preserved; it is not part of this deployment.
    (output / "model_service.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in ("app.py", "model_service.py", "model_password.py", "model_password_seed.json", "model_remote_guard.py"):
        shutil.copy2(root / name, output / name)
    shutil.copy2(root / "static/presentation.html", output / "presentation.html")
    url = "https://huggingface.co/spaces/abade1990/audit-review-private/raw/main/Dockerfile"
    docker = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    assert "tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng" in docker
    docker = docker.replace("tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng", "tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng openssh-client ca-certificates")
    docker = docker.replace("COPY --chown=user . .", "COPY --chown=user . .\nRUN tar --no-same-owner -xzf model_assets.tar.gz && rm model_assets.tar.gz")
    (output / "Dockerfile").write_text(docker, encoding="utf-8", newline="\n")
    manifest = []
    for p in sorted(output.iterdir()):
        with p.open("rb") as stream:
            manifest.append({"name": p.name, "bytes": p.stat().st_size, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()})
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(manifest), "bytes": sum(x["bytes"] for x in manifest), "model_sha256": cfg["adapter_sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    build(parser.parse_args().output)
