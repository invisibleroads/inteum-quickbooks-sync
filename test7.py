from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


class Inteum(object):

    def __init__(self, dsn):
        engine = create_engine(dsn)
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
                'patentStatusID': int(patent.PATSTATFK),
                'patentTypeID': int(patent.PAPPTYPEFK),
                'countryID': int(patent.COUNTRYFK),
            })
        return patents


def strip(text):
    return text.strip() if text else ''
