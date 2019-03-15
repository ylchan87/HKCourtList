import sqlalchemy

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy import Table

global session
session = None
global Session
Session = None
def init(sqlPath='sqlite:///:memory:', echo=False):
    engine = create_engine(sqlPath, echo=echo)
    Base.metadata.create_all(engine)
    global Session
    Session = sessionmaker(bind=engine)
    global session
    session = Session()
    return session

def get_session():
    return Session()

def get_or_create(cls, **kwargs):
    if not session: 
        print('db not init/connected yet')
        return None

    instance = session.query(cls).filter_by(**kwargs).first()
    if not instance:
        instance = cls(**kwargs)
        session.add(instance)
        session.flush([instance])
    return instance

def get_or_create_zh_or_en(cls, name_zh, name_en, shorten_names = False):
    if not session: 
        print('db not init/connected yet')
        return None

    if name_zh:
        instance = session.query(cls).filter_by(name_zh=name_zh).first()
        if instance:
            if name_en:
                if (not instance.name_en) or (shorten_names and (2<len(name_en)<len(instance.name_en))):
                    instance.name_en=name_en
                    session.add(instance)
                    session.flush([instance])
            return instance

    if name_en:
        instance = session.query(cls).filter_by(name_en=name_en).first()
        if instance:
            if name_zh:
                if (not instance.name_zh) or (shorten_names and (1<len(name_zh)<len(instance.name_zh))):
                    instance.name_zh=name_zh
                    session.add(instance)
                    session.flush([instance])
            return instance

    instance = cls(name_zh=name_zh, name_en=name_en)
    session.add(instance)
    session.flush([instance])
    return instance

# association table for many to many relationships
events_judges = Table('events_judges', Base.metadata,
    Column('event_id', ForeignKey('events.id'), primary_key=True),
    Column('judge_id', ForeignKey('judges.id'), primary_key=True)
)

events_cases = Table('events_cases', Base.metadata,
    Column('event_id', ForeignKey('events.id'), primary_key=True),
    Column('case_id', ForeignKey('cases.id'), primary_key=True)
)

events_tags = Table('events_tags', Base.metadata,
    Column('event_id', ForeignKey('events.id'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id'), primary_key=True)
)

events_lawyers = Table('events_lawyers', Base.metadata,
    Column('event_id', ForeignKey('events.id'), primary_key=True),
    Column('lawyer_id', ForeignKey('lawyers.id'), primary_key=True)
)

events_lawyers_atk = Table('events_lawyers_atk', Base.metadata,
    Column('event_id', ForeignKey('events.id'), primary_key=True),
    Column('lawyer_id', ForeignKey('lawyers.id'), primary_key=True)
)

events_lawyers_def = Table('events_lawyers_def', Base.metadata,
    Column('event_id', ForeignKey('events.id'), primary_key=True),
    Column('lawyer_id', ForeignKey('lawyers.id'), primary_key=True)
)

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    category = Column(String)
    court = Column(String)

    judges = relationship("Judge", 
                          secondary=events_judges,
                          back_populates='events',
                          lazy="dynamic",
                          )

    datetime = Column(DateTime(), nullable=True)

    #sometimes a event can have 2 cases
    cases = relationship("Case", 
                          secondary=events_cases,
                          back_populates='events',
                          lazy="dynamic",
                          )

    parties = Column(String)
    parties_atk = Column(String)
    parties_def = Column(String)

    tags = relationship("Tag", 
                          secondary=events_tags,
                          back_populates='events',
                          lazy="dynamic",
                          )

    lawyers = relationship("Lawyer", 
                          secondary=events_lawyers,
                          back_populates='events',
                          lazy="dynamic",
                          )

    lawyers_atk = relationship("Lawyer", 
                          secondary=events_lawyers_atk,
                          back_populates='events_atk',
                          lazy="dynamic",
                          )
    
    lawyers_def = relationship("Lawyer", 
                          secondary=events_lawyers_def,
                          back_populates='events_def',
                          lazy="dynamic",
                          )

    @classmethod
    def get_or_create(cls, **kwargs):
        return get_or_create(cls, **kwargs)

    def __repr__(self):
        return "<Event(category='%s', datetime='%s')>" % (
                            self.category, self.datetime)
    
    def fullDesc(self):
        print("category   :", self.category    )
        print("court      :", self.court       )
        print("judges     :", self.judges.all())
        print("datetime   :", self.datetime    )
        print("cases      :", self.cases.all() )
        print("parties    :", self.parties     )
        print("parties_atk:", self.parties_atk )
        print("parties_def:", self.parties_def )
        print("tags       :", self.tags.all()  )
        print("lawyers    :", self.lawyers.all()    )
        print("lawyers_atk:", self.lawyers_atk.all())
        print("lawyers_def:", self.lawyers_def.all())

class Judge(Base):
    __tablename__ = 'judges'
    id = Column(Integer, primary_key=True)
    name_zh = Column(String, unique=False)
    name_en = Column(String, unique=False)

    events = relationship("Event", 
                          secondary=events_judges,
                          back_populates='judges',
                          lazy="dynamic",
                          )

    @classmethod
    def get_or_create(cls, **kwargs):
        return get_or_create(cls, **kwargs)
    
    @classmethod
    def get_or_create_zh_or_en(cls, name_zh, name_en):
        return get_or_create_zh_or_en(cls, name_zh, name_en)

    def __repr__(self):
        return "<Judge(name_zh='%s', name_en='%s')>" % (
                            self.name_zh, self.name_en)

class Case(Base):
    __tablename__ = 'cases'
    id = Column(Integer, primary_key=True)
    caseNo = Column(String, unique=True)
    description = Column(String)
    events = relationship("Event", 
                          secondary=events_cases,
                          back_populates='cases',
                          lazy="dynamic",
                          )

    @classmethod
    def get_or_create(cls, **kwargs):
        return get_or_create(cls, **kwargs)
    
    def __repr__(self):
        return "<Case(caseNo='%s', description='%s')>" % (
                            self.caseNo, self.description)

class Tag(Base):
    """
    This correspond to 'Offence' 'Offence/Nature' and 'Hearing' column
    """
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    name_zh = Column(String, unique=False)
    name_en = Column(String, unique=False)

    events = relationship("Event", 
                          secondary=events_tags,
                          back_populates='tags',
                          lazy="dynamic",
                          )

    @classmethod
    def get_or_create(cls, **kwargs):
        return get_or_create(cls, **kwargs)
    
    @classmethod
    def get_or_create_zh_or_en(cls, name_zh, name_en):
        return get_or_create_zh_or_en(cls, name_zh, name_en, shorten_names=True)

    def __repr__(self):
        return "<Tag(name_zh='%s', name_en='%s')>" % (
                            self.name_zh, self.name_en)

class Lawyer(Base):
    __tablename__ = 'lawyers'
    id = Column(Integer, primary_key=True)
    name_zh = Column(String, unique=False) # '孖士打律師行' = 'Mayer Brown' also 'Mayer Brown JSM'...
    name_en = Column(String, unique=False)
    
    events = relationship("Event", 
                          secondary=events_lawyers,
                          back_populates='lawyers',
                          lazy="dynamic",
                          )

    events_atk = relationship("Event", 
                          secondary=events_lawyers_atk,
                          back_populates='lawyers_atk',
                          lazy="dynamic",
                          )
    
    events_def = relationship("Event", 
                          secondary=events_lawyers_def,
                          back_populates='lawyers_def',
                          lazy="dynamic",
                          )

    @classmethod
    def get_or_create(cls, **kwargs):
        return get_or_create(cls, **kwargs)
    
    @classmethod
    def get_or_create_zh_or_en(cls, name_zh, name_en):
        return get_or_create_zh_or_en(cls, name_zh, name_en)

    def __repr__(self):
        return "<Lawyer(name_zh='%s', name_en='%s')>" % (
                            self.name_zh, self.name_en)


if __name__=="__main__":
    from sqlalchemy.exc import SQLAlchemyError
    from datetime import datetime

    session = init(echo=True)
    
    c = Case.get_or_create( caseNo = "DCCJ 886/2014 [1/1]",
                            description = "民事訴訟")

    j1 = Judge.get_or_create(name_en="J1_EN", name_zh="J1_ZH")
    
    l1 = Lawyer.get_or_create(name_en="L1_EN", name_zh="L1_ZH")
    l2 = Lawyer.get_or_create(name_en="L2_EN", name_zh="L2_ZH")
    l3 = Lawyer.get_or_create(name_en="L2_EN", name_zh="L2_ZH")

    t1 = Tag.get_or_create(name_en="Summons(For striking out Statement of Claim)", 
                           name_zh="傳票(剔除 申索陳述書)")
    e = Event()
    e.court = "No12"
    e.category = "ABCD"
    e.judges = [j1]
    e.datetime = datetime.strptime("201901011220", "%Y%m%d%H%M")
    e.cases = [c]
    e.parties = "p1p2p3p4"
    e.parties_atk = "p1"
    e.parties_def = "p2"
    e.tags = [t1] 
    e.lawyers = [l1,l2]
    e.lawyers_atk = [l1]
    e.lawyers_def = [l3]

    try:
        session.add(e)
        session.commit()
    except SQLAlchemyError as e:
        print (e)
        session.rollback()