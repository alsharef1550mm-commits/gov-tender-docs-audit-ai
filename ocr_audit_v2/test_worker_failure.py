"""A crashed inspection must become failed, never remain indefinitely pending."""
import os
from pathlib import Path
import runpy
import sys
import tempfile
from unittest.mock import Mock, patch

import app
import job_pipeline as JP


def main():
    with tempfile.TemporaryDirectory() as root, patch.object(JP, "ROOT", root):
        job = JP.Job("worker-test")
        Path(job.dir).mkdir()
        job.save({"state": "files_checked", "log": []})
        with patch.object(JP, "run_job", side_effect=SyntaxError("report-import-probe")), \
                patch.object(sys, "argv", ["job_runner.py", job.id]):
            try:
                runpy.run_path(str(Path(__file__).with_name("job_runner.py")), run_name="__main__")
            except SyntaxError:
                pass
        state = job.load()
        assert state["state"] == "failed"
        assert "report-import-probe" in state["error"]
        assert state["pid"] == os.getpid()

        process = Mock()
        process.wait.return_value = 1
        job.save({"state": "files_checked", "log": []})
        app._watch_worker(job.id, process)
        assert job.load()["state"] == "failed"

        for terminal in ("awaiting_review", "exported", "failed"):
            job.save({"state": terminal, "log": []})
            app._watch_worker(job.id, process)
            assert job.load()["state"] == terminal
    print("PASS: startup failure is visible; abrupt exit is detected; completed/cancelled states are retained")


if __name__ == "__main__":
    main()
