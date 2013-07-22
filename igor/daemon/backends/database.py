from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Sequence, Boolean, ForeignKey

Base = declarative_base()


class EnvList(Base):
    """This table will store the host information
       e.g.: hardware information, host-name, ip address etc.
    """
    __tablename__ = "env_list"
    uid         = Column(Integer, Sequence('host_id_seq'), primary_key=True)
    host        = Column(String)
    cpu_mode    = Column(String)
    memory_size = Column(String)
    disk_size   = Column(String)
    nic         = Column(String)
    isVM        = Column(Boolean)
    testsuite   = Column(String)
    profile     = Column(String)
    additional_kargs    = Column(String)
    child       = relationship('Results')

    def __init__(self, aList):
        for k, v in aList:
            self.__setattr__(k, v)


class Results(Base):
    """
    """
    __tablename__ = "results"
    row_id      = Column(Integer, Sequence('row_id_seq'), primary_key=True)
    session_id  = Column(String)
    created_at  = Column(String)
    testcase    = Column(String)
    is_success  = Column(String)
    is_passed   = Column(String)
    is_abort    = Column(String)
    is_skipped  = Column(String)
    note        = Column(String)
    runtime     = Column(String)
    log         = Column(Text)
    annotations = Column(Text)
    env_id      = Column(Integer, ForeignKey('env_list.uid'))

    def __init__(self, aList):
        for k, v in aList:
            self.__setattr__(k, v)


def _check_database_type(conn_url):
    """
    :param conn_url<str>: database_type:///user:pass@location
    :rtype : str
    """
    db_type = conn_url.split(":")[0]
    if db_type == 'sqlite':
        return conn_url
    elif db_type == 'postgresql':
        #TODO check database connection
        return conn_url
    elif db_type == 'mysql':
        #TODO check database connection
        return conn_url
    else:
        raise RuntimeError('Unknown database schema: %s' % db_type)


def init_db(conn_url):
    conn_url = _check_database_type(conn_url)
    engine = create_engine(conn_url, convert_unicode=True)
    db_session = scoped_session(sessionmaker(autocommit=False,
                                             autoflush=False,
                                             bind=engine))
    Base.metadata.create_all(bind=engine)
    return db_session

if __name__ == '__main__':
    pass