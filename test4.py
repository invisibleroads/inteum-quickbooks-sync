'Update vendors'
from quickbooks import QBRequestProcessor
from parameters import APPLICATION_NAME


# Get vendors from QuickBooks
qbRequestProcessor = QBRequestProcessor(applicationName=APPLICATION_NAME)
results = qbRequestProcessor.call('VendorQueryRq', {})
# Determine new vendors
allVendorNames = [
    'xxx',
    'yyy',
]
oldVendorNames = [x['Name'] for x in results]
newVendorNames = set(allVendorNames).difference(oldVendorNames)
# Confirm
if oldVendorNames:
    print 'Here are the existing vendors:\n' + '\n'.join(oldVendorNames)
if newVendorNames:
    print 'Here are the vendors we will add:\n' + '\n'.join(newVendorNames)
    if raw_input('Proceed (y/[n])? ').lower() == 'y':
        # Add new vendors
        for vendorName in newVendorNames:
            qbRequestProcessor.call('VendorAddRq', {
                'VendorAdd': {
                    'Name': vendorName,
                },
            })
