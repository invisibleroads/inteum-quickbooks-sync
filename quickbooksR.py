import re
import datetime
from collections import OrderedDict, defaultdict

from quickbooks import ParseSkip, ParseError, MismatchError
from parameters import *


class QBRosetta(object):

    pattern_memo = re.compile(r'Inv (.*) Ref (.*)    (.*)')

    def __init__(self, technologies, patents, patentTypes, lawFirms, countries):
        self.technologyByID = dict((x['id'], x) for x in technologies)
        self.technologyByCase = dict((x['case'].lower(), x) for x in technologies)
        self.patentByID = dict((x['id'], x) for x in patents)
        self.patentByLawFirmCase = dict((x['lawFirmCase'].lower(), x) for x in patents)
        self.patentTypeByID = dict((x['id'], x) for x in patentTypes)
        self.patentTypeByName = dict((x['name'].lower(), x) for x in patentTypes)
        self.lawFirmByID = dict((x['id'], x) for x in lawFirms)
        self.lawFirmByName = dict((x['name'].lower(), x) for x in lawFirms)
        self.countryByID = dict((x['id'], x) for x in countries)


    # Customer

    def parse_customer(self, customer):
        'Return technology given customer'
        if customer.get('ParentRef'):
            raise ParseSkip # Skip jobs
        return self.parse_customer_name(customer.get('Name'))

    def parse_customer_name(self, customerName):
        try:
            technologyCase, technologyTitle = customerName.split(QUICKBOOKS_SEPARATOR)[:2]
        except ValueError:
            QUICKBOOKS_SEPARATOR_RSTRIPPED = QUICKBOOKS_SEPARATOR.rstrip()
            if customerName.endswith(QUICKBOOKS_SEPARATOR_RSTRIPPED):
                technologyCase = customerName[:-len(QUICKBOOKS_SEPARATOR_RSTRIPPED)]
                technologyTitle = ''
            else:
                raise ParseError('Could not parse customerName=%s' % customerName)
        return {
            'case': technologyCase.strip(),
            'title': technologyTitle.strip(),
        }

    def format_customer(self, technology, show_format_error=lambda error: None):
        return {'Name': self.get_customer_name(technology)}

    def equal_technology(self, technology1, technology2):
        try:
            technology1 = self.parse_customer(self.format_customer(technology1))
            technology2 = self.parse_customer(self.format_customer(technology2))
        except RosettaError:
            return False
        if technology1['case'].lower() != technology2['case'].lower():
            return False
        if technology1['case'] != technology2['case']:
            raise MismatchError
        if technology1['title'] != technology2['title']:
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
            patentTypeName, patentSerial, countryName = jobName.split(QUICKBOOKS_SEPARATOR)[:3]
        except ValueError:
            QUICKBOOKS_SEPARATOR_RSTRIPPED = QUICKBOOKS_SEPARATOR.rstrip()
            if jobName.endswith(QUICKBOOKS_SEPARATOR_RSTRIPPED):
                try:
                    countryName = ''
                    patentTypeName, patentSerial = jobName[:-len(QUICKBOOKS_SEPARATOR_RSTRIPPED)].split(QUICKBOOKS_SEPARATOR)[:2]
                except ValueError:
                    patentSerial = ''
                    patentTypeName = jobName[:-len(QUICKBOOKS_SEPARATOR_RSTRIPPED)]
            else:
                raise ParseError('Could not parse jobName=%s' % jobName)
        technologyCase = self.parse_customer_name(job['ParentRef']['FullName'])['case']
        try:
            technology = self.technologyByCase[technologyCase.lower()]
        except KeyError:
            raise ParseError('Could not find matching technology for technologyCase=%s' % technologyCase)
        technologyID = technology['id']
        patentTypeID = self.patentTypeByName[patentTypeName.lower()]['id'] if patentTypeName else 0
        for country in self.countryByID.values():
            if country['name'].lower().startswith(countryName.lower()):
                break
        else:
            country = None
        countryID = country['id'] if country else 0
        return {
            'technologyID': technologyID,
            'typeID': patentTypeID,
            'serial': patentSerial.strip(),
            'countryID': countryID,
        }

    def format_job(self, patent, show_format_error=lambda error: None):
        technologyID = patent['technologyID']
        technology = self.technologyByID[technologyID]
        return {
            'Name': self.get_job_name(patent),
            'ParentRef': {'FullName': self.get_customer_name(technology)}
        }

    def equal_patent(self, patent1, patent2):
        try:
            patent1 = self.parse_job(self.format_job(patent1))
            patent2 = self.parse_job(self.format_job(patent2))
        except RosettaError:
            return False
        if patent1['serial'].lower() != patent2['serial'].lower():
            return False
        if patent1['countryID'] != patent2['countryID']:
            return False
        if patent1['technologyID'] != patent2['technologyID']:
            raise MismatchError
        if patent1['typeID'] != patent2['typeID']:
            raise MismatchError
        return True

    def get_job_name(self, patent):
        patentTypeID = patent['typeID']
        patentTypeName = self.patentTypeByID[patentTypeID]['name'] if patentTypeID else ''
        patentSerial = patent['serial']
        countryID = patent['countryID']
        countryName = self.countryByID[countryID]['name'] if countryID else ''
        return make_customer_name(patentTypeName, patentSerial, countryName)

    # Vendor

    def parse_vendor(self, vendor):
        return {'name': vendor['Name']}

    def format_vendor(self, lawFirm, show_format_error=lambda error: None):
        return {'Name': lawFirm['name'][:QUICKBOOKS_VENDOR_NAME_LEN_MAX]}

    def equal_lawFirm(self, lawFirm1, lawFirm2):
        vendor1 = self.format_vendor(lawFirm1)
        vendor2 = self.format_vendor(lawFirm2)
        lawFirm1 = self.parse_vendor(vendor1)
        lawFirm2 = self.parse_vendor(vendor2)
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

    def update_bill(self, lawFirmExpense1, show_format_error):
        txnLineID = lawFirmExpense1['TxnLineID']
        expenseLines = []
        for lawFirmExpense2 in self.parse_bill(lawFirmExpense1['Bill'])['lawFirmExpenses']:
            if lawFirmExpense2['TxnLineID'] != txnLineID:
                expenseLine = self.format_expense(lawFirmExpense2, show_format_error, withTxnLineID=True)
            else:
                expenseLine = self.format_expense(lawFirmExpense1, show_format_error, withTxnLineID=True)
            expenseLines.append(expenseLine)
        return OrderedDict([
            ('TxnDate', lawFirmExpense1['invoiceDate'].strftime('%Y-%m-%d')),
            ('ExpenseLineMod', expenseLines),
        ])

    def format_bill(self, lawFirmBill, show_format_error=lambda error: None):
        lawFirmID = lawFirmBill['lawFirmID']
        lawFirm = self.lawFirmByID[lawFirmID]
        return OrderedDict([
            ('VendorRef', {'FullName': lawFirm['name']}),
            ('TxnDate', lawFirmBill['invoiceDate'].strftime('%Y-%m-%d')),
            ('ExpenseLineAdd', [self.format_expense(x, show_format_error) for x in lawFirmBill['lawFirmExpenses']]),
        ])

    def format_expense(self, lawFirmExpense, show_format_error=lambda error: None, withTxnLineID=False):
        # Format memo
        if 'memo' in lawFirmExpense:
            memo = lawFirmExpense['memo']
            try:
                invoiceNumber, lawFirmCase, description = self.pattern_memo.match(memo).groups()
            except AttributeError:
                # Force update
                return {}
            lawFirmExpense.update({
                'invoiceNumber': invoiceNumber,
                'lawFirmCase': lawFirmCase,
                'description': description,
            })
        else:
            memo = 'Inv %s Ref %s    %s' % (lawFirmExpense['invoiceNumber'], lawFirmExpense['lawFirmCase'], lawFirmExpense['description'])
        # Build expenseLine
        expenseLineParts = [
            ('AccountRef', {'FullName': '6100 - Patent Related Expenses'}),
            ('Amount', '%.02f' % float(lawFirmExpense['invoiceAmount'])),
            ('Memo', memo[:QUICKBOOKS_MEMO_LEN_MAX]),
        ]
        # Add link to patent
        try:
            patent = self.patentByLawFirmCase[lawFirmExpense['lawFirmCase'].lower()]
        except KeyError:
            show_format_error('Could not find matching patent for lawFirmCase=%s' % lawFirmExpense['lawFirmCase'])
        else:
            technology = self.technologyByID[patent['technologyID']]
            expenseLineParts.append(
                ('CustomerRef', {
                    'FullName': '%s:%s' % (self.get_customer_name(technology), self.get_job_name(patent))
                }))
        # Add TxnLineID
        if withTxnLineID:
            expenseLineParts.insert(0, ('TxnLineID', lawFirmExpense['TxnLineID']))
        return OrderedDict(expenseLineParts)

    def equal_expense(self, lawFirmExpense1, lawFirmExpense2):
        if lawFirmExpense1['lawFirmID'] != lawFirmExpense2['lawFirmID']:
            return False
        if lawFirmExpense1['invoiceNumber'].lower() not in lawFirmExpense2['memo'].lower():
            return False
        lawFirmExpense1['TxnLineID'] = lawFirmExpense2['TxnLineID']
        lawFirmExpense1['Bill'] = lawFirmExpense2['Bill']
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


class RosettaError(Exception):
    pass


def make_customer_name(*parts):
    customerName = QUICKBOOKS_SEPARATOR.join(x.replace(QUICKBOOKS_SEPARATOR, ' ') for x in parts)
    return customerName[:QUICKBOOKS_CUSTOMER_NAME_LEN_MAX].replace(':', '').strip()
