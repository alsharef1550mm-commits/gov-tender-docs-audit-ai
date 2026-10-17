"""فحص دفعة بلا عقد: على ربطات سليمة من عقود بقواعد ضريبة مختلفة، النتيجة بلا عقد تطابق نتيجة العقد في الصافي والعمولة والضريبة والإجمالي،
ولا تظهر ملاحظات حسابية كاذبة، ويُضاف بند مراجعة واحد يذكر أن العقد لم يُرفع."""
import glob, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import report_template as T
import report_writer as RW

ROOT = T.ROOT
CASES = []
for comp, folder, contract_glob in [("MED-2026-144", "منافسة جراحة العظام MED-2026-144", "العقد"), ("MED-2026-231", "منافسة غسيل الكلى MED-2026-231", "العقد"),
                                    ("MED-2026-327", "منافسة العيون MED-2026-327", "العقد"), ("MED-2026-339", "منافسة العناية بالجروح MED-2026-339", "العقد"),
                                    ("MED-2026-318", "منافسة الرعاية التنفسية MED-2026-318", "العقد")]:
    base = os.path.join(ROOT, "المنافسات", folder)
    b = sorted(glob.glob(os.path.join(base, f"{comp}-*.pdf")))
    c = os.path.join(base, contract_glob, "عقد المنافسة.pdf")
    if b and os.path.exists(c):
        CASES.append((comp, b[len(b) // 2], c))                 # ربطة من منتصف المنافسة
assert CASES, "لا ربطات"
for comp, bundle, contract in CASES:
    with_c = RW.collect_batch(bundle, contract)
    no_c = RW.collect_batch(bundle, None)
    assert with_c["results"].keys() == no_c["results"].keys()
    bad_vals, bad_issues = [], []
    for sto, r1 in with_c["results"].items():
        r0 = no_c["results"][sto]
        if (r1.net, r1.commission, r1.vat, r1.total) != (r0.net, r0.commission, r0.vat, r0.total):
            bad_vals.append((sto, (r1.vat, r0.vat)))
        if r0.issues:
            bad_issues.append((sto, [i.code for i in r0.issues]))
    notes = [u for u in no_c["unresolved"] if "لم يُرفع عقد" in u.get("reason", "")]
    print(f"{comp}: {len(with_c['results'])} سنداً | فروق قيم بلا عقد: {len(bad_vals)} | ملاحظات حسابية كاذبة: {len(bad_issues)} | بند عدم العقد: {len(notes)}")
    assert not bad_vals, bad_vals[:3]
    assert not bad_issues, bad_issues[:3]
    assert len(notes) == 0, notes                              # لا بند مراجعة عام عن غياب العقد
    assert no_c["no_contract_note"] and "السند الأول" in no_c["no_contract_note"]
print("OK")

# تقنية السند المرجع: أول سند يحدد العمولة وأساس الضريبة، وأي سند لاحق يخالفهما يُكشف ويُحال للمراجعة
import extract, engine
comp, bundle, _c = next(c for c in CASES if c[0] == "MED-2026-339")
b = extract.read_bundle(bundle)
rules = engine.read_rules(None, comp)
ref_rules = engine.infer_bundle_rules(b, rules)
assert ref_rules.evidence["inferred"]["ref_receipt"] == b.receipts[0].sto
taxable = [x for x in b.receipts if any((i.vat_rate or 0) > 0 for i in x.items)]
assert len(taxable) >= 2
D = type(taxable[0].printed["vat"])

# (1) سند لاحق بضريبة على الصافي فقط بينما المرجع على الصافي والعمولة
late = taxable[1]
orig_vat = late.printed["vat"]
late.printed["vat"] = sum((engine.r2(engine.r2(i.qty * i.unit_price) * D("0.15")) for i in late.items if (i.vat_rate or 0) > 0), D(0))
res = engine.check_bundle(b, rules)
bad = next(x for x in res if x.sto == late.sto)
assert any(i.code == "vat" for i in bad.issues), [i.code for i in bad.issues]
assert all(not x.issues for x in res if x.sto != late.sto)
late.printed["vat"] = orig_vat
print("سند لاحق بأساس ضريبة مختلف عن المرجع: مكشوف | بقية السندات بلا ملاحظات")

# (2) سند لاحق بعمولة مختلفة
other = b.receipts[2]
orig = other.printed["nupco"]
other.printed["nupco"] = orig + D("40")
res = engine.check_bundle(b, rules)
assert any(i.code == "commission" for i in next(x for x in res if x.sto == other.sto).issues)
other.printed["nupco"] = orig
print("سند لاحق بعمولة مختلفة عن المرجع: مكشوف")

# (3) ما يصل للمراجع: بند إحالة للسند المخالف ويبقى حكمه فارغاً (لا «غير سليم»)
import extract as _e
orig_read = RW.extract.read_bundle
def patched(path, *a, **k):
    bb = orig_read(path, *a, **k)
    if os.path.samefile(path, bundle):
        bb.receipts[2].printed["nupco"] = bb.receipts[2].printed["nupco"] + D("40")
    return bb
RW.extract.read_bundle = patched
try:
    data = RW.collect_batch(bundle, None)
finally:
    RW.extract.read_bundle = orig_read
sto = data["bundle"].receipts[2].sto
items = [u for u in data["unresolved"] if u.get("sto") == sto]
assert items and "المرجع" in items[0]["reason"] and sto in data["review_stos"]
assert "السند الأول" in data["no_contract_note"] and not any("لم يُرفع عقد" in u["reason"] for u in data["unresolved"])
print("بند إحالة للسند المخالف + حكمه محجوز للمراجعة")
print("OK2")
