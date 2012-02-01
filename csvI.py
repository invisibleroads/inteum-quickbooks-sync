import re
import csv
import datetime

from quickbooksR import QBRosetta


class HoffmannAndBaron(QBRosetta):

    lawFirmName = 'Hoffmann & Baron'
    pattern_lawFirmCase = re.compile(r'OUR DOCKET: (.*)')
    pattern_parentheses = re.compile(r'\(.*\)')

    def load_expenses(self, csvPath):
        csvReader = csv.reader(open(csvPath))
        lawFirmExpenseByInvoiceNumber = {}
        lawFirm = self.lawFirmByName[self.lawFirmName.lower()]
        lawFirmID = lawFirm['id']
        for row in csvReader:
            if not row:
                continue
            if row[0].startswith('LEDES1998B'):
                continue
            if '\t' in row[0]:
                row = row[0].split('\t')
            if 'INVOICE_AMOUNT' in row:
                indexByKey = dict((key.strip(), index) for index, key in enumerate(row))
                continue
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
            elif len(description) > len(lawFirmExpenseByInvoiceNumber[invoiceNumber]['description']):
                # Store the longer description
                lawFirmExpenseByInvoiceNumber[invoiceNumber]['description'] = description
        return lawFirmExpenseByInvoiceNumber.values()


modules = [
    HoffmannAndBaron,
]
