"""Reading evidence policy. Accounting consistency never chooses a reading."""
from copy import deepcopy
import re
from number_reading import decimal_reading, amount_reading, quantity_reading, page_separator

POLICY_VERSION = 'evidence-first-v1'
MAX_REREADS = 1

def reading_signals(pred):
    if not isinstance(pred, dict):return ['failed_read']
    reasons=[]
    for key in ('unreadable_fields','_id_conflicts','_dropped','_value_conflicts'):
        if pred.get(key):reasons.append(key)
    if pred.get('_type_conflict') or pred.get('_failed'):reasons.append('reader_disagreement')
    for key,pattern in [('receipt_no',r'STO\d{10}'),('po_no',r'PON\d{10}'),('invoice_no',r'(?:TF)?\d{10}')]:
        value=(pred.get('ids') or {}).get(key)
        if value not in (None,'') and not re.fullmatch(pattern,re.sub(r'\s','',str(value))):
            reasons.append('ids.'+key+':unrecognized_identifier')
    sep=page_separator(pred)
    for key,value in (pred.get('totals') or {}).items():
        if value not in (None,'') and decimal_reading(value,sep) is None:reasons.append('totals.'+key+':unreadable_number')
    # Numeric confidence is actionable only if a separately calibrated reader
    # marked it; a language model's self-reported confidence is not calibration.
    for signal in pred.get('_reading_signals',[]):
        if isinstance(signal,dict) and signal.get('kind') in ('truncated_token','column_ambiguity','blurred_region','independent_disagreement','calibrated_low_confidence'):
            reasons.append(signal['kind'])
    for i,item in enumerate(pred.get('items') or []):
        if not isinstance(item,dict):reasons.append('malformed_row');continue
        for k in ('qty','unit_price','line_total'):
            value=(quantity_reading(item.get(k),sep) if k=='qty' else amount_reading(item.get(k),item.get(k+'_halala'),sep))
            if value is None:reasons.append(f'items.{i}.{k}:unreadable_number')
    return sorted(set(reasons))

def visible_fields(pred):
    return {k:deepcopy(pred.get(k)) for k in ('page_type','ids','dates','items','totals','inspection')}

def reconcile_readings(first, second):
    """Keep both observations. A changed value is unresolved, not a repair."""
    if not isinstance(first,dict):
        out=deepcopy(second) if isinstance(second,dict) else {'page_type':'other'}
        out['_reading_review']=['first_read_failed; enhanced_read_requires_review']
    else:
        out=deepcopy(first)
        if not isinstance(second,dict):out['_reading_review']=['enhanced_read_failed']
        elif visible_fields(first)!=visible_fields(second):out['_reading_review']=['readings_disagree; original_values_preserved']
        elif reading_signals(first) or reading_signals(second):out['_reading_review']=['agreement_does_not_resolve_missing_or_ambiguous_evidence']
    out['_readings']=[deepcopy(first),deepcopy(second)]
    out['_reading_policy']=POLICY_VERSION
    out['_agreement_is_source_verification']=False
    return out
