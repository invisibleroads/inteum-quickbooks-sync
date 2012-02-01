from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


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
            technology = {
                'id': int(technology.PRIMARYKEY),
                'case': strip(technology.TECHID),
                'title': strip(technology.NAME),
            }
            technologies.append(technology)
        return technologies

    def get_patents(self):
        class Patent(self.Base):
            __table__ = self.tables['PATENTS']
        patents = []
        for patent in self.db.query(Patent):
            patent = {
                'id': int(patent.PRIMARYKEY),
                'technologyID': int(patent.TECHNOLFK),
                'title': strip(patent.NAME),
                'lawFirmID': int(patent.LAWFIRMFK),
                'lawFirmCase': strip(patent.LEGALREFNO),
                'filingDate': patent.FILEDATE.strftime('%Y%m%d') if patent.FILEDATE.year != 1899 else '',
                'serial': strip(patent.SERIALNO),
                'statusID': int(patent.PATSTATFK),
                'typeID': int(patent.PAPPTYPEFK),
                'countryID': int(patent.COUNTRYFK),
            }
            # Skip patents with insufficient information
            if not patent['lawFirmCase'] or not patent['serial']:
                continue
            patents.append(patent)
        return patents

    def get_patentTypes(self):
        class PatentType(self.Base):
            __table__ = self.tables['PAPPTYPE']
        patentTypes = []
        for patentType in self.db.query(PatentType):
            patentType = {
                'id': int(patentType.PRIMARYKEY),
                'name': strip(patentType.NAME),
            }
            patentTypes.append(patentType)
        return patentTypes

    def get_lawFirms(self):
        class Company(self.Base):
            __table__ = self.tables['COMPANY']
        lawFirms = []
        for lawFirm in self.db.query(Company).filter_by(TYPE='L'):
            lawFirm = {
                'id': lawFirm.PRIMARYKEY,
                'name': lawFirm.NAME,
            }
            lawFirms.append(lawFirm)
        return lawFirms

    def get_countries(self):
        class Country(self.Base):
            __table__ = self.tables['COUNTRY']
        countries = []
        for country in self.db.query(Country):
            country = {
                'id': country.PRIMARYKEY,
                'name': country.NAME,
            }
            countries.append(country)
        return countries


def strip(text):
    return text.strip() if text else ''
