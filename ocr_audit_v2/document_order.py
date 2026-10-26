"""Paper sequence for report rows; document identifiers never define row order."""
import os
import re

def ordered_bundle_paths(paths):
    """Natural bundle filename order, stable for equal names (2 precedes 10)."""
    def key(path):
        name=os.path.basename(str(path)).casefold()
        return tuple((1,int(part)) if part.isdigit() else (0,part)
                     for part in re.split(r'(\d+)',name))
    return sorted(paths,key=key)

def ordered_receipts(receipts):
    """First source page, then known vertical position; stable ties preserve extraction."""
    def key(receipt):
        pages=[p for p in getattr(receipt,'pages',[]) if isinstance(p,int) and p>0]
        page=min(pages) if pages else float('inf')
        positions=[]
        for item in getattr(receipt,'items',[]):
            ev=getattr(item,'ev',None);box=getattr(ev,'box',None)
            if getattr(ev,'page',None)==page and box and len(box)==4 and box[3]>box[1]:
                positions.append(box[1])
        return page,min(positions) if positions else float('inf')
    return sorted(receipts,key=key)

def batch_receipt_ids(data,excluded=()):
    available=data['results'];blocked=set(excluded);seen=set();order=[]
    receipts=list(data['receipts'].values())
    for receipt in ordered_receipts(receipts):
        if receipt.sto in available and receipt.sto not in seen and receipt.sto not in blocked:
            order.append(receipt.sto);seen.add(receipt.sto)
    return order

def competition_receipt_ids(data,excluded=()):
    blocked=set(excluded);by_file={}
    for sto,receipt in data['receipts'].items():
        if sto in data['results'] and sto not in blocked:
            by_file.setdefault(data['bundle_of'][sto],[]).append(receipt)
    return [receipt.sto for filename in ordered_bundle_paths(by_file)
            for receipt in ordered_receipts(by_file[filename])]
