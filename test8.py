from test7 import Inteum
from quickbooks import QuickBooks
from parameters import INTEUM_DSN, QUICKBOOKS_APPLICATION_NAME


# Load technologies from Inteum
inteum = Inteum(INTEUM_DSN)
allTechnologies = inteum.get_technologies()
# Load technologies from QuickBooks
quickbooks = QuickBooks(applicationName=QUICKBOOKS_APPLICATION_NAME)
oldTechnologies = []
for result in quickbooks.call('CustomerQueryRq', {}):
    customerName = result.get('Name')
    technologyCase, separator, technologyTitle = customerName.partition('-')
    oldTechnologies.append({
        'case': technologyCase.strip(),
        'title': technologyTitle.strip(),
    })


newTechologies = []
for oneTechnology in allTechnologies:
    for oldTechnology in oldTechnologies:
        if oneTechnology['case'] != oldTechnology['case']:
            continue
        if oneTechnology['title'] != oldTechnology['title']:
            print 'MISMATCH'
            print oneTechnology
            print oldTechnology
            continue
    else:
        newTechologies.append(oneTechnology)


print len(newTechologies)
