import re
import datetime
from collections import OrderedDict, defaultdict

from quickbooks.qbcom import QuickBooks, ParseSkip, ParseError, MismatchError
from parameters import *


class QBRosetta(object):

    def __init__(self, technologies, patents, patentTypes, lawFirms):
        self.technologyByID = dict((x['id'], x) for x in technologies)
        self.technologyByCase = dict((x['case'].lower(), x) for x in technologies)
        self.patentByID = dict((x['id'], x) for x in patents)
        self.patentByLawFirmCase = dict((x['lawFirmCase'].lower(), x) for x in patents)
        self.patentTypeByID = dict((x['id'], x) for x in patentTypes)
        self.patentTypeByName = dict((x['name'].lower(), x) for x in patentTypes)
        self.lawFirmByID = dict((x['id'], x) for x in lawFirms)
        self.lawFirmByName = dict((x['name'].lower(), x) for x in lawFirms)

    # Customer

    def parse_customer(self, customer):
        'Return technology given customer'
        if customer.get('ParentRef'):
            raise ParseSkip # Skip jobs
        customerName = customer.get('Name')
        try:
            technologyCase, technologyTitle = customerName.split(QUICKBOOKS_SEPARATOR)[:2]
        except ValueError:
            raise ParseError('Could not parse customerName=%s' % customerName)
        return {
            'case': technologyCase.strip(),
            'title': technologyTitle.strip(),
        }

    def format_customer(self, technology):
        return {'Name': self.get_customer_name(technology)}

    def equal_technology(self, technology1, technology2):
        try:
            customer1 = self.format_customer(technology1)
            customer2 = self.format_customer(technology2)
            technology1 = self.parse_customer(customer1)
            technology2 = self.parse_customer(customer2)
        except ApplicationError:
            return False
        if technology1['case'].lower() != technology2['case'].lower():
            return False
        if customer1 != customer2:
            raise MismatchError
        return True

    def get_customer_name(self, technology):
        technologyCase = technology['case']
        technologyTitle = technology['title']
        return make_customer_name(technologyCase, technologyTitle)

    # Job

    def parse_job(self, job):
        'Return patent given job'
        if not job.get('ParentRef'):
            raise ParseSkip # Skip customers
        jobName = job.get('Name')
        try:
            technologyCase, patentTypeName, patentSerial = jobName.split(QUICKBOOKS_SEPARATOR)[:3]
        except ValueError:
            raise ParseError('Could not parse jobName=%s' % jobName)
        technology = self.technologyByCase[technologyCase.lower()]
        technologyID = technology['id']
        patentType = self.patentTypeByName[patentTypeName.lower()]
        patentTypeID = patentType['id']
        return {
            'technologyID': technologyID,
            'typeID': patentTypeID,
            'serial': patentSerial.strip(),
        }

    def format_job(self, patent):
        technologyID = patent['technologyID']
        technology = self.technologyByID[technologyID]
        return {
            'Name': self.get_job_name(patent),
            'ParentRef': {'FullName': self.get_customer_name(technology)}
        }

    def equal_patent(self, patent1, patent2):
        try:
            job1 = self.format_job(patent1)
            job2 = self.format_job(patent2)
            patent1 = self.parse_job(job1)
            patent2 = self.parse_job(job2)
        except ApplicationError:
            return False
        if patent1['serial'].lower() != patent2['serial'].lower():
            return False
        if job1 != job2:
            raise MismatchError
        return True

    def get_job_name(self, patent):
        technologyID = patent['technologyID']
        technology = self.technologyByID[technologyID]
        technologyCase = technology['case']
        patentTypeID = patent['typeID']
        patentType = self.patentTypeByID[patentTypeID]
        patentTypeName = patentType['name']
        patentSerial = patent['serial']
        return make_customer_name(technologyCase, patentTypeName, patentSerial)

    # Vendor

    def parse_vendor(self, vendor):
        return {'name': vendor['Name']}

    def format_vendor(self, lawFirm):
        return {'Name': lawFirm['name']}

    def equal_lawFirm(self, lawFirm1, lawFirm2):
        if lawFirm1['name'].lower() != lawFirm2['name'].lower():
            return False
        if lawFirm1['name'] != lawFirm2['name']:
            raise MismatchError
        return True

    # Bill

    def parse_bill(self, bill):
        lawFirmName = bill['VendorRef']['FullName']
        try:
            lawFirm = self.lawFirmByName[lawFirmName.lower()]
        except KeyError:
            raise ParseError('Could not parse lawFirmName=%s' % lawFirmName)
        lawFirmID = lawFirm['id']
        invoiceDate = datetime.datetime.strptime(bill['TxnDate'], '%Y-%m-%d').date()
        lawFirmExpenses = []
        if hasattr(bill['ExpenseLineRet'], 'iteritems'):
            bill['ExpenseLineRet'] = [bill['ExpenseLineRet']]
        for expenseLine in bill['ExpenseLineRet']:
            lawFirmExpenses.append({
                'lawFirmID': lawFirmID,
                'invoiceDate': invoiceDate,
                'invoiceAmount': expenseLine['Amount'],
                'memo': expenseLine['Memo'],
                'TxnLineID': expenseLine['TxnLineID'],
            })
        return {
            'lawFirmID': lawFirmID,
            'lawFirmExpenses': lawFirmExpenses,
            'invoiceDate': invoiceDate,
        }

    def update_bill(self, lawFirmExpense):
        patent = self.patentByLawFirmCase[lawFirmExpense['lawFirmCase'].lower()]
        return OrderedDict([
            ('TxnDate', lawFirmExpense['invoiceDate'].strftime('%Y-%m-%d')),
            ('ExpenseLineMod', OrderedDict({
                'TxnLineID': lawFirmExpense['TxnLineID'],
            }.items() + self.format_expense(lawFirmExpense).items())),
        ])

    def format_bill(self, lawFirmBill):
        lawFirmID = lawFirmBill['lawFirmID']
        lawFirm = self.lawFirmByID[lawFirmID]
        resultDictionary = OrderedDict([
            ('VendorRef', {'FullName': lawFirm['name']}),
            ('TxnDate', lawFirmBill['invoiceDate'].strftime('%Y-%m-%d')),
        ])
        for lawFirmExpense in lawFirmBill['lawFirmExpenses']:
            resultDictionary = OrderedDict(resultDictionary.items() + {
                'ExpenseLineAdd': self.format_expense(lawFirmExpense),
            }.items())
        return resultDictionary

    def format_expense(self, lawFirmExpense):
        if 'memo' in lawFirmExpense:
            memo = lawFirmExpense['memo']
            try:
                invoiceNumber, lawFirmCase, description = re.match('Inv (.*) Ref (.*) = (.*)', memo).groups()
            except AttributeError:
                # Force update
                return {}
            lawFirmExpense.update({
                'invoiceNumber': invoiceNumber,
                'lawFirmCase': lawFirmCase,
                'description': description,
            })
        else:
            memo = 'Inv %s Ref %s = %s' % (lawFirmExpense['invoiceNumber'], lawFirmExpense['lawFirmCase'], lawFirmExpense['description'])
        patent = self.patentByLawFirmCase[lawFirmExpense['lawFirmCase'].lower()]
        technology = self.technologyByID[patent['technologyID']]
        return OrderedDict([
            ('AccountRef', {'FullName': '6100 - Patent Related Expenses'}),
            ('Amount', '%.02f' % float(lawFirmExpense['invoiceAmount'])),
            ('Memo', memo),
            ('CustomerRef', {'FullName': '%s:%s' % (self.get_customer_name(technology), self.get_job_name(patent))}),
        ])

    def equal_expense(self, lawFirmExpense1, lawFirmExpense2):
        if lawFirmExpense1['lawFirmID'] != lawFirmExpense2['lawFirmID']:
            return False
        if lawFirmExpense1['invoiceNumber'].lower() not in lawFirmExpense2['memo'].lower():
            return False
        lawFirmExpense1['TxnLineID'] = lawFirmExpense2['TxnLineID']
        if lawFirmExpense1['invoiceDate'] != lawFirmExpense2['invoiceDate']:
            raise MismatchError
        if self.format_expense(lawFirmExpense1) != self.format_expense(lawFirmExpense2):
            raise MismatchError
        return True

    def expand_bills(self, lawFirmBills):
        lawFirmExpenses = []
        for lawFirmBill in lawFirmBills:
            for lawFirmExpense in lawFirmBill['lawFirmExpenses']:
                lawFirmExpense['Bill'] = lawFirmBill['Bill']
                lawFirmExpenses.append(lawFirmExpense)
        return lawFirmExpenses

    def collapse_expenses(self, lawFirmExpenses):
        lawFirmExpensesDictionary = defaultdict(list)
        for lawFirmExpense in lawFirmExpenses:
            lawFirmID = lawFirmExpense['lawFirmID']
            invoiceDate = lawFirmExpense['invoiceDate']
            lawFirmExpensesDictionary[(lawFirmID, invoiceDate)].append(lawFirmExpense)
        lawFirmBills = []
        for (lawFirmID, invoiceDate), lawFirmExpenses in lawFirmExpensesDictionary.iteritems():
            lawFirmBills.append({
                'lawFirmID': lawFirmID,
                'lawFirmExpenses': lawFirmExpenses,
                'invoiceDate': invoiceDate,
            })
        return lawFirmBills


class ApplicationError(Exception):
    pass


def make_customer_name(*parts):
    customerName = QUICKBOOKS_SEPARATOR.join(x.replace(QUICKBOOKS_SEPARATOR, ' ') for x in parts)
    return customerName[:QUICKBOOKS_CUSTOMER_NAME_LEN_MAX].replace(':', '')


def summarize_candidatePacks(packs):
    packCount = len(packs)
    print '%i candidate%s' % (packCount, 's' if packCount != 1 else '')


def summarize_mismatches(mismatches):
    mismatchCount = len(mismatches)
    print '%i mismatch%s' % (mismatchCount, 'es' if mismatchCount != 1 else '')


def summarize_newPacks(packs):
    packCount = len(packs)
    print '%i new' % packCount


if __name__ == '__main__':
    technologies = [{
        'id': 1,
        'case': 'AAA',
        'title': 'BBB',
    }]
    patents = [{
        'id': 10,
        'technologyID': 1,
        'title': 'XXX',
        'lawFirmID': 30,
        'lawFirmCase': 'YYY',
        'filingDate': '20000101',
        'serial': 'ZZZ',
        'statusID': 40,
        'typeID': 50,
        'countryID': 60,
    }]
    patentTypes = [{
        'id': 50,
        'name': 'MMM',
    }]
    lawFirms = [{
        'id': 1000,
        'name': 'WWW',
    }]
    lawFirmExpenses = [{
        'lawFirmID': 1000,
        'lawFirmCase': 'YYY',
        'invoiceDate': datetime.datetime(2011, 1, 1).date(),
        'invoiceNumber': '000000',
        'invoiceAmount': '9.99',
        'description': 'ABCDEF',
    }]
    qb = QuickBooks(applicationName=QUICKBOOKS_APPLICATION_NAME)
    qbr = QBRosetta(technologies, patents, patentTypes, lawFirms)
    print '--- Technologies ---'
    qb.synchronize(technologies, 'Customer', dict(
        equal=qbr.equal_technology,
        parse_result=qbr.parse_customer,
        update_result=qbr.format_customer,
        format_result=qbr.format_customer,
        # expand_results=
        # collapse_packs=
        prompt_update=lambda pack, oldPack: True,
        prompt_save=lambda newPacks, newResults: True,
        # show_parse_error=
        summarize_candidatePacks=summarize_candidatePacks,
        summarize_mismatches=summarize_mismatches,
        summarize_newPacks=summarize_newPacks,
    ))
    print '--- Patents ---'
    qb.synchronize(patents, 'Customer', dict(
        equal=qbr.equal_patent,
        parse_result=qbr.parse_job,
        update_result=qbr.format_job,
        format_result=qbr.format_job,
        # expand_results=
        # collapse_packs=
        prompt_update=lambda pack, oldPack: True,
        prompt_save=lambda newPacks, newResults: True,
        # show_parse_error=
        summarize_candidatePacks=summarize_candidatePacks,
        summarize_mismatches=summarize_mismatches,
        summarize_newPacks=summarize_newPacks,
    ))
    print '--- Law Firms ---'
    qb.synchronize(lawFirms, 'Vendor', dict(
        equal=qbr.equal_lawFirm,
        parse_result=qbr.parse_vendor,
        update_result=qbr.format_vendor,
        format_result=qbr.format_vendor,
        # expand_results=
        # collapse_packs=
        prompt_update=lambda pack, oldPack: True,
        prompt_save=lambda newPacks, newResults: True,
        # show_parse_error=
        summarize_candidatePacks=summarize_candidatePacks,
        summarize_mismatches=summarize_mismatches,
        summarize_newPacks=summarize_newPacks,
    ))
    print '--- Expense Accounts ---'
    qb.synchronize([{'name': '6100 - Patent Related Expenses'}], 'Account', dict(
        equal=lambda account1, account2: account1['name'].lower() == account2['name'].lower(),
        parse_result=lambda result: {'name': result['FullName']},
        # update_result=,
        format_result=lambda account: OrderedDict([('Name', account['name']), ('AccountType', 'Expense')]),
        # expand_results=,
        # collapse_packs=,
        # prompt_update=,
        prompt_save=lambda newPacks, newResults: True,
        # show_parse_error=
        summarize_candidatePacks=summarize_candidatePacks,
        summarize_mismatches=summarize_mismatches,
        summarize_newPacks=summarize_newPacks,
    ))
    print '--- Expenses ---'
    qb.synchronize(lawFirmExpenses, 'Bill', dict(
        equal=qbr.equal_expense,
        parse_result=qbr.parse_bill,
        update_result=qbr.update_bill,
        format_result=qbr.format_bill,
        expand_results=qbr.expand_bills,
        collapse_packs=qbr.collapse_expenses,
        prompt_update=lambda pack, oldPack: True,
        prompt_save=lambda newPacks, newResults: True,
        # show_parse_error=
        summarize_candidatePacks=summarize_candidatePacks,
        summarize_mismatches=summarize_mismatches,
        summarize_newPacks=summarize_newPacks,
    ), {'IncludeLineItems': 1})
