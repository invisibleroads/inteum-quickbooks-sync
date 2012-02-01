from quickbooks import QuickBooks
from collections import OrderedDict

qb = QuickBooks()
# results1 = qb.call('BillQueryRq', {
    # 'IncludeLineItems': 1,
# }, saveXML=True)
results2 = qb.call('BillAddRq', {
    'BillAdd': OrderedDict([
        ('VendorRef', {
            'FullName': 'Patton Hardware Supplies',
        }),
        ('ExpenseLineAdd', {
            'AccountRef': {
                'FullName': 'Utilities:Telephone',
            },
            'Amount': '100.00',
        }),
    ]),
}, saveXML=True)
results3 = qb.call('BillModRq', {
    'BillMod': OrderedDict([
        ('TxnID', results2[0]['TxnID']),
        ('EditSequence', results2[0]['EditSequence']),
        ('TxnDate', '2011-01-01'),
        ('ExpenseLineMod', {
            'TxnLineID': results2[0]['ExpenseLineRet']['TxnLineID'],
            'Amount': '99.99',
        }),
    ]),
}, saveXML=True)
results4 = qb.call('TxnDelRq', OrderedDict([
    ('TxnDelType', 'Bill'),
    ('TxnID', results3[0]['TxnID']),
]), saveXML=True)
