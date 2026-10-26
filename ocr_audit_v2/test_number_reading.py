from decimal import Decimal as D
from number_reading import decimal_reading as read,amount_reading as amount

def test_formats():
    for raw,expected in [('107.50','107.50'),('١٠٧٫٥٠','107.50'),('۱٬۲۰۷٫۵۰','1207.50'),
                         ('1,207.50','1207.50'),('107,50','107.50'),('107.505','107.505'),
                         ('1 207.50','1207.50'),('(107.50)','-107.50'),('SAR 107.50','107.50')]:
        assert read(raw)==D(expected),(raw,read(raw))
    for raw in ['107,500','1,20,700','10 75','NaN','Infinity','107.50.2','107٫50.2',True]:assert read(raw) is None,raw
    assert read('107,500',',')==D('107.500')
    assert read('107,500','.')==D('107500')
    assert amount('107','50')==D('107.50')
    assert amount('١٠٧','٠٥')==D('107.05')
    assert amount('107.50',None)==D('107.50')
    assert amount('107.50','50')==D('107.50') and amount('107.50','0.50')==D('107.50')   # whole amount printed in the riyal column, fraction repeated
    assert amount('107.50','40') is None and amount('107.50','0.40') is None             # the two prints disagree
    assert amount('107','100') is None
    assert amount('107','1.5') is None
    assert amount('-107','50')==D('-107.50')

if __name__=='__main__':test_formats();print('number formats: passed')
