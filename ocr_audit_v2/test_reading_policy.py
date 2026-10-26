"""Bounded evidence-driven rereads; no accounting-guided replacement."""
import copy
from unittest.mock import patch
import vlm_reader as V
from label_review import candidate,target_hash,validate_human_approval
from reading_policy import reading_signals

def receipt():
    return {'page_type':'receipt','ids':{'receipt_no':'STO0000006831','po_no':'PON0000001265','invoice_no':'5002603722'},
            'dates':{},'items':[{'line_no':'1','item_code':'GEN-065','qty':'20','unit_price':'112.50','line_total':'1800'}],
            'totals':{'net_excl_vat':'1800'},'unreadable_fields':[]}

def invoice(code='GEN-065'):
    return {'page_type':'invoice','ids':{'invoice_no':'5002603722'},'dates':{},
            'items':[{'line_no':'1','item_code':code,'qty':'16','unit_price':'112.50','line_total':'1872','commission':'72','vat':'0'}],'totals':{}}

def test_retry():
    calls=[]
    first=receipt();second=copy.deepcopy(first);second['items'][0]['qty']='16'
    with patch.object(V,'_reader2',return_value=None),patch.object(V,'read_preds',return_value=[first]),patch.object(V,'_reread_pages',side_effect=lambda *a,**kw:calls.append(a)):
        b=V.read_bundle_vlm('x.pdf',max_retries=100)
        assert calls==[]
        assert b.receipts[0].items[0].qty==20 and b.receipts[0].items[0].line_total==1800
    first['unreadable_fields']=['items.0.qty']
    with patch.object(V,'_reader2',return_value=None),patch.object(V,'read_preds',return_value=[first]),patch.object(V,'_reread_pages',return_value={1:second}) as retry:
        b=V.read_bundle_vlm('x.pdf',max_retries=100)
        assert retry.call_count==1
        assert b.receipts[0].items[0].qty==20
        assert b.agree_issues and b.raw_readings[0]['_readings'][1]['items'][0]['qty']=='16'
    with patch.object(V,'_reader2',return_value=None),patch.object(V,'read_preds',return_value=[first]),patch.object(V,'_reread_pages',return_value={1:copy.deepcopy(first)}) as retry:
        b=V.read_bundle_vlm('x.pdf');assert retry.call_count==1 and b.agree_issues
        assert b.raw_readings[0]['_agreement_is_source_verification'] is False
    with patch.object(V,'_reader2',return_value={'model':'second'}),patch.object(V,'read_preds',return_value=[first]),patch.object(V,'_reread_pages') as retry:
        b=V.read_bundle_vlm('x.pdf');assert not retry.called and b.agree_issues

def test_printed():
    p=receipt();p['items'][0].update(qty='1',unit_price='20',line_total='20',line_total_halala=None)
    b=V.bundle_from_preds('x.pdf',[p]);assert b.receipts[0].items[0].line_total==20
    assert not getattr(b.receipts[0],'flags',[]) and not V.suspect_pages(b)
    p['items'][0]['line_total_halala']='80'
    b=V.bundle_from_preds('x.pdf',[p]);assert str(b.receipts[0].items[0].line_total)=='20.8'
    p=invoice();p['items'][0]['line_total']='1800'
    b=V.bundle_from_preds('x.pdf',[p])
    assert len(b.invoices[0].items)==1 and b.invoices[0].items[0].total==1800
    assert b.invoices[0].flags[0]['seen']=='1800'

def test_labels():
    r=candidate({'page_type':'receipt','ids':{'receipt_no':'STO0000001111'}},{'competition':'TRAIN-901','source_document_id':'doc-1','image_sha256':'abc',
      'evidence':{'ids.receipt_no':{'text':'STO0000001111','bbox':[10,10,200,50]}}})
    assert not r['training_eligible']
    def denied(x):
        try:validate_human_approval(x)
        except ValueError:return
        raise AssertionError('Unreviewed or reserved label accepted')
    denied(r)
    r['label_approval']={'status':'approved','reviewer':'test reviewer','scope':'all_visible_target_fields','target_sha256':target_hash(r['target']),
      'image_sha256':'abc','source_document_id':'doc-1','reviewed_at':'2026-10-19T20:00:00+03:00'}
    assert validate_human_approval(r)
    changed=copy.deepcopy(r);changed['target']['page_type']='invoice';denied(changed)
    for comp in ('MED-2026-327','MED-HOLDOUT-730','MED-2027-842'):
        changed=copy.deepcopy(r);changed['competition']=comp;denied(changed)
    changed=copy.deepcopy(r);changed['label_approval']['scope']='audit_approved';denied(changed)
    changed=copy.deepcopy(r);changed['image_sha256']='different';denied(changed)
    changed=copy.deepcopy(r);changed['evidence']={};denied(changed)
    changed=copy.deepcopy(r);changed['evidence']['ids.receipt_no']['bbox']=[10,10,0,0];denied(changed)

def test_job_candidate():
    import tempfile
    from pathlib import Path
    import job_pipeline as J
    with tempfile.TemporaryDirectory() as tmp:
        j=J.Job('policy-test',root=tmp);Path(j.dir).mkdir()
        j.save({'decisions':{},'pending':[{'key':'field-1','file':'example.pdf','page':1}],'log':[]})
        J.review(j,'field-1','verified_ok',note='Checked audit finding',reviewer='Test reviewer')
        c=j.load()['label_review_candidates']['field-1']
        assert c['training_eligible'] is False and c['status']=='pending_field_label_review'
        assert not list(Path(tmp).rglob('train.jsonl'))

def test_signals_and_invoice_hold():
    p=receipt();p['confidence']=0.1
    assert not reading_signals(p)  # Uncalibrated self-confidence is not evidence.
    p['_reading_signals']=[{'kind':'calibrated_low_confidence'}]
    assert reading_signals(p)
    p=receipt();p['ids']['receipt_no']='STO123';assert reading_signals(p)
    p=receipt();p['totals']['total']='107,500';assert reading_signals(p)
    inv=invoice();other=copy.deepcopy(inv);other['items'][0]['qty']='17'
    merged=V.merge_preds(inv,other);b=V.bundle_from_preds('x.pdf',[receipt(),merged])
    assert 2 in b.agree_issues
    import report_writer as RW
    unresolved=[];held=RW._ocr_review(b,{},unresolved)
    assert 'STO0000006831' in held

if __name__=='__main__':
    for f in (test_retry,test_printed,test_labels,test_job_candidate,test_signals_and_invoice_hold):f();print(f.__name__,'passed')
