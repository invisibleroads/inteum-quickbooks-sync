from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from parameters import INTEUM_DSN


def strip(text):
    return text.strip() if text else ''


Base = declarative_base()
engine = create_engine(INTEUM_DSN)
Base.metadata.reflect(engine)
tables = Base.metadata.tables
class Technology(Base):
    __table__ = tables['TECHNOL']
class Patent(Base):
    __table__ = tables['PATENTS']
DBSession = sessionmaker(engine)
db = DBSession()
technologies = []
for technology in db.query(Technology):
    technologies.append((
        int(technology.PRIMARYKEY),
        strip(technology.TECHID),
        strip(technology.NAME),
    ))
