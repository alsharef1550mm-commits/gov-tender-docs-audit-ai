"""يشغّل مهمة فحص في عملية مستقلة، فيستطيع زر «إلغاء الفحص» إيقافها بالكامل (قتل العملية وما تحتها) لا مجرد طلب توقف.

  python job_runner.py <job_id> [run|export]
"""
import os
import sys
import traceback

import job_pipeline as JP

if __name__ == "__main__":
    job = JP.Job(sys.argv[1])
    try:
        job.update(pid=os.getpid())
        job.log("بدأت عملية الفحص على خادم التطبيق")
        if len(sys.argv) > 2 and sys.argv[2] == "export":
            JP.approve_and_export(job)
        else:
            JP.run_job(job)
    except Exception as exc:
        traceback.print_exc()
        job.set_state("failed", error=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1500:])
        raise
