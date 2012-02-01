'List vendors in QuickBooks'
from quickbooks import QBRequestProcessor
from parameters import APPLICATION_NAME


qbRequestProcessor = QBRequestProcessor(applicationName=APPLICATION_NAME)
results = qbRequestProcessor.call('VendorQueryRq', {})
