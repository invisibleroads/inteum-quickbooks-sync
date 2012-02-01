from quickbooks.qbcom import QuickBooks
from parameters import *
from test7 import Inteum


def transform(x):
    customerName = x.get('Name')
    technologyCase, technologyTitle = customerName.split(QUICKBOOKS_SEPARATOR)
    return {
        'case': technologyCase.strip(),
        'title': technologyTitle.strip(),
    }


def equal(t1, t2):
    t1 = transform(untransform(t1))
    t2 = transform(untransform(t2))
    if t1['case'] != t2['case']:
        return False
    if t1['title'] != t2['title']:
        raise Exception('%s: "%s" != "%s"' % (t1['case'], t1['title'], t2['title']))
    return True


def untransform(t):
    name = QUICKBOOKS_SEPARATOR.join(x.replace(QUICKBOOKS_SEPARATOR, ' ') for x in [
        t['case'], 
        t['title']])
    return {
        'Name': name[:QUICKBOOKS_CUSTOMER_NAME_LEN_MAX].replace(':', ''),
    }


def get_new(requestProcessor, itemName, allPacks, transform, equal):
    'Get new data'
    requestName = itemName + 'Query'
    oldPacks = []
    for result in requestProcessor.call(requestName + 'Rq', {}):
        oldPacks.append(transform(result))
    newPacks = []
    for onePack in allPacks:
        for oldPack in oldPacks:
            if equal(onePack, oldPack):
                break
        else:
            newPacks.append(onePack)
    return newPacks


def add_new(requestProcessor, itemName, newPacks, untransform):
    'Add new data'
    requestName = itemName + 'Add'
    for onePack in newPacks:
        print requestProcessor.call(requestName + 'Rq', {
            requestName: untransform(onePack)
        })


def run():
    inteum = Inteum(INTEUM_DSN)
    allPacks = inteum.get_technologies()
    print 'Total: %s' % len(allPacks)
    qb = QuickBooks(applicationName=QUICKBOOKS_APPLICATION_NAME)
    itemName = 'Customer'
    newPacks = get_new(qb, itemName, allPacks, transform, equal)
    print 'New: %s' % len(newPacks)
    if not newPacks:
        return
    if raw_input('Proceed (y/[n])? ').lower() != 'y':
        return
    add_new(qb, itemName, newPacks, untransform)
