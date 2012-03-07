import re
import csv
import datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from quickbooks.qbcom import QuickBooks


errors = set()


def get_companyID(bill):
    companyName = normalize_companyName(bill['VendorRef']['FullName'])
    try:
        companyID = companyIDByName[normalize_companyName(companyName)]
    except KeyError:
        errors.add('Could not match companyName=%s' % companyName)
        companyID = 0
    return companyID


def get_dueDate(bill):
    return datetime.datetime.strptime(bill['DueDate'], '%Y-%m-%d')


def get_invoiceDate(bill):
    return datetime.datetime.strptime(bill['TxnDate'], '%Y-%m-%d')


def get_invoiceNumber(expense):
    return re.search('#\s*([^ ]*)', expense['Memo']).group(1)


def get_amount(expense):
    return expense['Amount']


def get_linkPack(expense):
    text = expense['CustomerRef']['FullName']
    lawFirmReference = re.search('Firm ID: ([^(]*)', text)


    linkTable = ''
    linkID = 0
    return linkTable, linkID


# Connect
qb = QuickBooks('Extract financial records')
# Load
bills = qb.call('BillQueryRq', {'IncludeLineItems': 1})


sqlalchemyURL = 'mssql+pyodbc://inteumCSdb'
Base = declarative_base()
engine = create_engine(sqlalchemyURL)
Base.metadata.reflect(engine)
tables = Base.metadata.tables
class Company(Base):
    __table__ = tables['COMPANY']
class Patent(Base):
    __table__ = tables['PATENTS']
class Technology(Base):
    __table__ = tables['TECHNOL']
class Payable(Base):
    __table__ = tables['PAYABLE']
class PayableDetail(Base):
    __table__ = tables['PAYBLDTL']
DBSession = sessionmaker(engine)
db = DBSession()


def normalize_companyName(companyName):
    # Remove non-alphanumeric characters
    companyName = re.sub('[^a-zA-Z0-9_ ]', '', companyName)
    # Compact whitespace
    companyName = re.sub('\s+', ' ', companyName)
    # Return
    return companyName.lower()


# Load dictionaries
companyIDByName = dict((normalize_companyName(x.NAME), x.PRIMARYKEY) for x in db.query(Company).filter_by(TYPE='L'))


# import ipdb; ipdb.set_trace()


# Initialize
expenses = []
# For each result,
for bill in bills:
    companyID = get_companyID(bill)
    # dueDate = get_dueDate(bill)
    # invoiceDate = get_invoiceDate(bill)
    # expenses = bill['ExpenseLineRet']
    # if isinstance(expenses, dict):
        # expenses = [expenses]
    # for expense in expenses:
        # invoiceNumber = get_invoiceNumber(expense)
        # amount = get_amount(expense)
        # linkTable, linkID = get_linkPack(expense)
        # expenses.append({
            # 'companyID': companyID,
            # 'dueDate': dueDate,
            # 'invoiceDate': invoiceDate,
            # 'invoiceNumber': invoiceNumber,
            # 'amount': amount,
            # 'linkTable': linkTable,
            # 'linkID': linkID,
        # })


for error in sorted(errors):
    print error


def save_expenses(expenses):
    csvWriter = csv.writer(open('expenses.csv', 'wb'))
    for expense in expenses:
        csvWriter.writerow([
            '',
            'COMPANY',
            expense['companyID'],
            '',
            expense['invoiceDate'].strftime('%m/%d/%Y'),
            expense['invoiceNumber'],
            '',
            '',
            '',
            expense['dueDate'].strftime('%m/%d/%Y'),
            '',
            '',
            'Legal',
            expense['linkTable'],
            expense['linkID'],
            '',
            expense['amount'],
        ])
