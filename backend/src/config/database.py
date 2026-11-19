from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config.settings import DATABASE_URL
# READ COMMITTED keeps every statement inside the publish/void critical sections
# looking at the latest committed rows. The guard row itself is taken FOR UPDATE.
_engine_options={} if DATABASE_URL.startswith('sqlite') else {'isolation_level':'READ COMMITTED'}
# SQLite (tests/local) needs cross-thread access for the publish/void critical
# sections; MySQL is the only production driver and ignores these options.
_connect_args={'check_same_thread':False,'timeout':30} if DATABASE_URL.startswith('sqlite') else {}
engine=create_engine(DATABASE_URL,pool_pre_ping=True,connect_args=_connect_args,**_engine_options)
Session=sessionmaker(bind=engine)
Base=declarative_base()
