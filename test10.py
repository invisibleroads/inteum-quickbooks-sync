from quickbooks.qbcom import QuickBooks
from parameters import *


class Inteum(object):
    'Dummy interface'

    def __init__(self, dsn):
        pass

    def get_technologies(self):
        return [dict(
            id=1,
            case='AAA',
            title='BBB',
        )]

    def get_patents(self):
        return [dict(
            id=10,
            technologyID=1,
            title='XXX',
            lawFirmID=30,
            lawFirmCase='YYY',
            filingDate='20000101',
            serial='ZZZ',
            statusID=40,
            typeID=50,
            countryID=60,
        )]

    def get_patent_types(self):
        return [dict(
            id=50,
            name='MMM',
        )]



class InteumQB(Inteum):

    def __init__(self, dsn):
        technologies = self.get_technologies()
        self.technologyByID = dict((x['id'], x) for x in technologies)
        self.technologyByCase = dict((x['case'].lower(), x) for x in technologies)

        patents = self.get_patents()
        self.patentByID = dict((x['id'], x) for x in patents)

        patentTypes = self.get_patent_types()
        self.patentTypeByID = dict((x['id'], x) for x in patentTypes)
        self.patentTypeByName = dict((x['name'].lower(), x) for x in patentTypes)

    def get_customer_name(self, technology):
        technologyCase = technology['case']
        technologyTitle = technology['title']
        return make_customer_name(technologyCase, technologyTitle)

    def get_job_name(self, patent):
        technologyID = patent['technologyID']
        technology = self.technologyByID[technologyID]
        technologyCase = technology['case']
        patentTypeID = patent['typeID']
        patentType = self.patentTypeByID[patentTypeID]
        patentTypeName = patentType['name']
        patentSerial = patent['serial']
        return make_customer_name(technologyCase, patentTypeName, patentSerial)

    def format_customer(self, technology):
        return {
            'Name': self.get_customer_name(technology),
        }

    def format_job(self, patent):
        technologyID = patent['technologyID']
        technology = self.technologyByID[technologyID]
        return {
            'Name': self.get_job_name(patent),
            'ParentRef': {
                'FullName': self.get_customer_name(technology),
            }
        }

    def parse_customer(self, customer):
        'Return technology given customer'
        customerName = customer.get('Name')
        try:
            technologyCase, technologyTitle = customerName.split(QUICKBOOKS_SEPARATOR)[:2]
        except ValueError:
            raise ApplicationError
        return {
            'case': technologyCase.strip(),
            'title': technologyTitle.strip(),
        }

    def parse_job(self, job):
        'Return patent given job'
        if not job.get('ParentRef'):
            raise ApplicationError
        jobName = job.get('Name')
        try:
            technologyCase, patentTypeName, patentSerial = jobName.split(QUICKBOOKS_SEPARATOR)[:3]
        except ValueError:
            raise ApplicationError
        technology = self.technologyByCase[technologyCase.lower()]
        technologyID = technology['id']
        patentType = self.patentTypeByName[patentTypeName.lower()]
        patentTypeID = patent['id']
        return {
            'technologyID': technologyID,
            'typeID': patentTypeID,
            'serial': patentSerial.strip(),
        }

    def equal_technology(self, technology1, technology2):
        try:
            technology1 = self.parse_customer(self.format_customer(technology1))
            technology2 = self.parse_customer(self.format_customer(technology2))
        except ApplicationError:
            return False
        if technology1['case'].lower() != technology2['case'].lower():
            return False
        if technology1['case'] != technology2['case']:
            raise ApplicationError('%s != %s' % (technology1['case'], technology2['case']))
        if technology1['title'] != technology2['title']:
            raise ApplicationError('%s != %s' % (technology1['title'], technology2['title']))
        return True

    def equal_patent(self, patent1, patent2):
        patent1 = self.parse_job(self.format_job(patent1))
        patent2 = self.parse_job(self.format_job(patent2))
        if patent1['serial'].lower() != patent2['serial'].lower():
            return False
        if patent1['technologyID'] != patent2['technologyID']:
            raise ApplicationError('%s != %s' % (patent1['technologyID'], patent2['technologyID']))
        if patent1['typeID'] != patent2['typeID']:
            raise ApplicationError('%s != %s' % (patent1['typeID'], patent2['typeID']))
        return True


def make_customer_name(*parts):
    customerName = QUICKBOOKS_SEPARATOR.join(x.replace(QUICKBOOKS_SEPARATOR, ' ') for x in parts)
    return customerName[:QUICKBOOKS_CUSTOMER_NAME_LEN_MAX].replace(':', '')


class ApplicationError(Exception):
    pass


def equal(t1, t2):
    t1 = transform(untransform(t1))
    t2 = transform(untransform(t2))
    if t1['case'].lower() != t2['case'].lower():
        return False
    if t1['case'] != t2['case']:
        raise Exception('"%s" != "%s"' % (t1['case'], t2['case']))
    return True


def get_new(requestProcessor, itemName, allPacks, transform, equal):
    'Get new data'
    requestName = itemName + 'Query'
    oldPacks = []
    for result in requestProcessor.call(requestName + 'Rq', {}):
        try:
            oldPacks.append(transform(result))
        except ApplicationError:
            pass
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


def synchronize(allPacks, transform, untransform, equal):
    print '-' * 10
    print 'Total: %s' % len(allPacks)
    itemName = 'Customer'
    newPacks = get_new(qb, itemName, allPacks, transform, equal)
    print 'New: %s' % len(newPacks)
    if not newPacks:
        return
    if raw_input('Proceed (y/[n])? ').lower() != 'y':
        return
    add_new(qb, itemName, newPacks, untransform)


if __name__ == '__main__':
    qb = QuickBooks(applicationName=QUICKBOOKS_APPLICATION_NAME)
    inteumQB = InteumQB(INTEUM_DSN)
    synchronize(inteumQB.get_technologies(), inteumQB.parse_customer, inteumQB.format_customer, inteumQB.equal_technology)
    synchronize(inteumQB.get_patents(), inteumQB.parse_job, inteumQB.format_job, inteumQB.equal_patent)
