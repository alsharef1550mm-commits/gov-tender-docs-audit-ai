"""يشغّل مهمة فحص في عملية مستقلة، فيستطيع زر «إلغاء الفحص» إيقافها بالكامل (قتل العملية وما تحتها) لا مجرد طلب توقف.

  python job_runner.py <job_id> [run|export]
"""
import sys

import job_pipeline as JP

if __name__ == "__main__":
    job = JP.Job(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2] == "export":
        JP.approve_and_export(job)
    else:
        JP.run_job(job)
