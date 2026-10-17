"""تقدّم حقيقي للقراءة: القارئات (OCR/نموذج الرؤية) تُبلغ عن كل صفحة تنتهي منها، ومهمة الفحص تحوّل ذلك إلى نسبة مئوية في شريط المتابعة.

المُبلِّغ خاص بكل خيط (thread-local) فلا تتداخل مهام متزامنة، ولا يعمل داخل عمليات Pool الفرعية (فيها يُبلَّغ عن اكتمال كل ربطة فقط).
"""
import threading

_tl = threading.local()


class Cancelled(Exception):
    """طلب المستخدم إلغاء الفحص."""


def set_reporter(fn):
    _tl.fn = fn


def report(stage: str, done: int, total: int, note: str = ""):
    fn = getattr(_tl, "fn", None)
    if fn:
        fn(stage, done, total, note)
