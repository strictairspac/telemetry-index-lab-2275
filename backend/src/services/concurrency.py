"""Serialisation point shared by void confirmation and report publishing.

Two different processes touch the same decision: the API confirms a void while the
worker may be publishing a report. A process-local lock is not enough, so both take
the singleton `void_guard` row `FOR UPDATE` inside their transaction and only commit
on leaving the section. A process-local lock is kept as well so single-process
deployments (and SQLite tests, which ignore `FOR UPDATE`) still serialise.

The guard row is created *before* the caller's transaction opens. Creating it inside
would commit mid-section and drop the row lock on MySQL.
"""
import threading
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError
from src.config.database import Session
from src.models.telemetry import VoidGuard

_PROCESS_LOCK=threading.RLock()

def ensure_guard():
 with Session() as s:
  if s.get(VoidGuard,1) is not None:return
  s.add(VoidGuard(id=1,epoch=0))
  try:s.commit()
  except IntegrityError:s.rollback()

@contextmanager
def critical(session):
 """Hold the publish/void critical section. Caller commits before leaving."""
 with _PROCESS_LOCK:
  ensure_guard()
  guard=session.get(VoidGuard,1,with_for_update=True)
  if guard is None:
   session.add(VoidGuard(id=1,epoch=0))
   session.flush()
   guard=session.get(VoidGuard,1,with_for_update=True)
  yield guard
