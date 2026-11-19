"""Idempotent schema upgrade for deployments that already have an `experiments` table.

There is no Alembic in this project; `Base.metadata.create_all` creates the new void
tables but never adds columns to an existing table. This adds only the columns that
are missing, so it is safe to run on every startup.
"""
import logging
from sqlalchemy import inspect,text
from src.config.database import Base,engine
from src.models import identity,workload,candidate,experiment,telemetry  # noqa: F401  (register metadata)

# column -> (mysql ddl, sqlite ddl)
_COLUMNS={
 'evidence':('JSON','JSON'),
 'report_state':('VARCHAR(20)','VARCHAR(20)'),
 'invalid_reason':('VARCHAR(1000)','VARCHAR(1000)'),
 'void_ids':('JSON','JSON'),
 'void_epoch':('INT','INT'),
 'published_at':('DATETIME','DATETIME'),
}

def ensure_schema():
 Base.metadata.create_all(engine)
 inspector=inspect(engine)
 if 'experiments' not in inspector.get_table_names():return
 existing={c['name'] for c in inspector.get_columns('experiments')}
 dialect=engine.dialect.name
 with engine.begin() as conn:
  for name,(mysql_ddl,sqlite_ddl) in _COLUMNS.items():
   if name in existing:continue
   ddl=sqlite_ddl if dialect=='sqlite' else mysql_ddl
   conn.execute(text(f'ALTER TABLE experiments ADD COLUMN {name} {ddl}'))
   logging.info('schema: added experiments.%s',name)
