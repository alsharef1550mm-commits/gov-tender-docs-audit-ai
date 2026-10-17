"""سند استلام بالرقم نفسه في أكثر من ربطة (ازدواج سداد محتمل): يُحتسب مرة واحدة ويُبلَّغ عنه ويُحجز حتى يراجعه مراجع."""
import glob, io, os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import competition_writer as CW, report_template as T


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    folder = glob.glob(os.path.join(T.ROOT, "المنافسات", "*MED-2026-305"))[0]
    contract = glob.glob(os.path.join(folder, "العقد", "*.pdf"))[0]
    b2 = os.path.join(folder, "MED-2026-305-01-002.pdf")
    d = tempfile.mkdtemp()
    copy = os.path.join(d, "MED-2026-305-01-098.pdf")
    shutil.copy(b2, copy)                                                    # الربطة نفسها بتسمية أخرى: كل سنداتها تتكرر
    one = CW.collect_competition([b2], contract, {}, 1, None, None)
    two = CW.collect_competition([b2, copy], contract, {}, 1, None, None)
    assert two["order"] == one["order"] and len(two["order"]) >= 2, (two["order"], one["order"])          # لا تضاعف الأعداد ولا المبالغ
    assert {s: str(two["results"][s].payable) for s in two["order"]} == {s: str(one["results"][s].payable) for s in one["order"]}
    dup = [u for u in two["unresolved"] if u["reason"].startswith("سند استلام مكرر")]
    assert sorted(u["sto"] for u in dup) == sorted(two["order"]), dup
    assert all({u["dup_file"], u["file"]} == {"MED-2026-305-01-098.pdf", "MED-2026-305-01-002.pdf"} and "المحتوى مطابق" in u["why"] for u in dup)   # ترتيب الظهور حسب ترتيب المعالجة
    assert all(s in two["review_stos"] for s in two["order"])                  # تُحجز حتى المراجعة
    assert not [u for u in one["unresolved"] if u["reason"].startswith("سند استلام مكرر")]
    print("OK", len(dup), "بنود مكررة")


if __name__ == "__main__":
    main()
