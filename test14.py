import re
import csv
import datetime
from collections import OrderedDict, defaultdict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from quickbooks.qbcom import QuickBooks, ParseSkip, ParseError, MismatchError
from parameters import *


class Inteum(object):

    def __init__(self, dsn):
        engine = create_engine('mssql+pyodbc://' + dsn)
        self.Base = declarative_base()
        self.Base.metadata.reflect(engine)
        self.db = sessionmaker(engine)()
        self.tables = self.Base.metadata.tables

    def get_technologies(self):
        class Technology(self.Base):
            __table__ = self.tables['TECHNOL']
        technologies = []
        for technology in self.db.query(Technology):
            technologies.append({
                'id': int(technology.PRIMARYKEY),
                'case': strip(technology.TECHID),
                'title': strip(technology.NAME),
            })
        return technologies

    def get_patents(self):
        class Patent(self.Base):
            __table__ = self.tables['PATENTS']
        patents = []
        for patent in self.db.query(Patent):
            patents.append({
                'id': int(patent.PRIMARYKEY),
                'technologyID': int(patent.TECHNOLFK),
                'title': strip(patent.NAME),
                'lawFirmID': int(patent.LAWFIRMFK),
                'lawFirmCase': strip(patent.LEGALREFNO),
                'filingDate': patent.FILEDATE.strftime('%Y%m%d') if patent.FILEDATE.year != 1899 else '',
                'serial': patent.SERIALNO,
                'statusID': int(patent.PATSTATFK),
                'typeID': int(patent.PAPPTYPEFK),
                'countryID': int(patent.COUNTRYFK),
            })
        return patents

    def get_patentTypes(self):
        class PatentType(self.Base):
            __table__ = self.tables['PAPPTYPE']
        patentTypes = []
        for patentType in self.db.query(PatentType):
            patentTypes.append({
                'id': int(patentType.PRIMARYKEY),
                'name': strip(patentType.NAME),
            })
        return patentTypes

    def get_lawFirms(self):
        class Company(Base):
            __table__ = self.tables['COMPANY']
        lawFirms = []
        for lawFirm in self.db.query(Company).filter_by(TYPE='L'):
            lawFirms.append({
                'id': lawFirm.PRIMARYKEY,
                'name': lawFirm.NAME,
            })
        return lawFirms


class QBRosetta(object):

    pattern_memo = re.compile(r'Inv (.*) Ref (.*)    (.*)')

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

    def format_customer(self, technology, show_format_error=lambda error: None):
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

    def format_job(self, patent, show_format_error=lambda error: None):
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

    def format_vendor(self, lawFirm, show_format_error=lambda error: None):
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
            ('Memo', memo),
        ]
        # Add link to patent
        try:
            patent = self.patentByLawFirmCase[lawFirmExpense['lawFirmCase'].lower()]
        except KeyError:
            show_format_error('Could not find matching patent for %s' % lawFirmExpense['lawFirmCase'])
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


class HoffmannAndBaron(QBRosetta):

    lawFirmName = 'Hoffmann & Baron'
    pattern_lawFirmCase = re.compile(r'OUR DOCKET: (.*)')
    pattern_parentheses = re.compile(r'\(.*\)')

    def load_expenses(self, csvPath):
        csvReader = csv.reader(open(csvPath))
        row = csvReader.next()
        assert row[0].startswith('LEDES1998B')
        row = csvReader.next()
        indexByKey = dict((key, index) for index, key in enumerate(row))
        lawFirmExpenseByInvoiceNumber = {}
        lawFirm = self.lawFirmByName[self.lawFirmName.lower()]
        lawFirmID = lawFirm['id']
        for row in csvReader:
            lawFirmCase = self.pattern_lawFirmCase.match(row[indexByKey['LAW_FIRM_REFERENCE_NUMBER']]).group(1)
            lawFirmCase = self.pattern_parentheses.sub('', lawFirmCase).strip()
            invoiceDate = datetime.datetime.strptime(row[indexByKey['INVOICE_DATE']], '%Y%m%d').date()
            invoiceNumber = row[indexByKey['INVOICE_NUMBER']].strip()
            invoiceAmount = float(row[indexByKey['INVOICE_AMOUNT']])
            description = row[indexByKey['DESCRIPTION_OF_EXPENSES']].strip('" ')
            if invoiceNumber not in lawFirmExpenseByInvoiceNumber:
                lawFirmExpenseByInvoiceNumber[invoiceNumber] = {
                    'lawFirmID': lawFirmID,
                    'lawFirmCase': lawFirmCase,
                    'invoiceDate': invoiceDate,
                    'invoiceNumber': invoiceNumber,
                    'invoiceAmount': invoiceAmount,
                    'description': description,
                }
        return lawFirmExpenseByInvoiceNumber.values()


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


def strip(text):
    return text.strip() if text else ''


if __name__ == '__main__':
    # inteum = Inteum(INTEUM_DSN)
    # technologies = inteum.get_technologies()
    # patents = inteum.get_patents()
    # patentTypes = inteum.get_patentTypes()
    # lawFirms = inteum.get_lawFirms()

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
        'lawFirmCase': '1038-29',
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
        'name': 'Hoffmann & Baron',
    }]

    qb = QuickBooks(applicationName=QUICKBOOKS_APPLICATION_NAME)
    qbr = HoffmannAndBaron(technologies, patents, patentTypes, lawFirms)
    lawFirmExpenses = qbr.load_expenses('a176102-parsed.csv')

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
        # show_format_error=
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
        # show_format_error=
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
        # show_format_error=
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
        # show_format_error=
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
        # show_format_error=
        summarize_candidatePacks=summarize_candidatePacks,
        summarize_mismatches=summarize_mismatches,
        summarize_newPacks=summarize_newPacks,
    ), {'IncludeLineItems': 1})
