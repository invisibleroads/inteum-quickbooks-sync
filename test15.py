import csv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from quickbooks.qbcom import QuickBooks


def get_companyID(bill):
    return 0


def get_dueDate(bill):
    return ''


def get_invoiceDate(bill):
    return ''


def get_invoiceNumber(expense):
    return ''


def get_amount(expense):
    return 0


def get_linkPack(expense):
    linkTable = ''
    linkID = 0
    return linkTable, linkID


# Connect
qb = QuickBooks('Extract financial records')
# Load
bills = qb.call('BillQueryRq', {'IncludeLineItems': 1})
# Debug
import ipdb; ipdb.set_trace()


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


# Initialize
expenses = []
# For each result,
for bill in bills:
    companyID = get_companyID(bill)
    dueDate = get_dueDate(bill)
    invoiceDate = get_invoiceDate(bill)
    for expense in bill['ExpenseLineRet']:
        invoiceNumber = get_invoiceNumber(expense)
        amount = get_amount(expense)
        linkTable, linkID = get_linkPack(expense)
        expenses.append({
            'companyID': companyID,
            'dueDate': dueDate,
            'invoiceDate': invoiceDate,
            'invoiceNumber': invoiceNumber,
            'amount': amount,
            'linkTable': linkTable,
            'linkID': linkID,
        })


csvWriter = csv.writer(open('expenses.csv', 'wb'))
for expense in expenses:
    csvWriter.writerow([
        '',
        'COMPANY',
        expense['companyID'],
        '',
        expense['invoiceDate'],
        expense['invoiceNumber'],
        '',
        '',
        '',
        expense['dueDate'],
        '',
        '',
        'Legal',
        expense['linkTable'],
        expense['linkID'],
        '',
        expense['amount'],
    ])
