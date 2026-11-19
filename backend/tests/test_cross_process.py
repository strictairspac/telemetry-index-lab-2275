"""Cross-process checks: the guarantee rests on a MySQL row lock, not a thread lock.

These are skipped on SQLite, where `FOR UPDATE` is a no-op and the in-process lock
would hide a missing database lock.
"""
import multiprocessing
import os
import time
import pytest
from sqlalchemy import text
from src.config.database import engine,Session
from src.models.experiment import Experiment
from src.models.telemetry import TelemetryVoid,TelemetryVoidItem
from src.services import voids
from tests.conftest import User,make_report,make_telemetry,void_input

pytestmark=pytest.mark.skipif(engine.dialect.name!='mysql',reason='needs MySQL row locks')


def _other_connection_holds_guard_then_commits(sensor,start,end):
 """Child process: take the guard, register a void, hold it briefly, commit."""
 from src.config.database import Session as S
 from src.models.telemetry import TelemetryVoid as V,TelemetryVoidItem as I
 from src.services import concurrency
 with S() as s:
  with concurrency.critical(s):
   v=V(sensor_id=sensor,start_at=start,end_at=end,reason='cross-process calibration',actor='other',dedupe_key='cross-'+os.urandom(4).hex())
   s.add(v);s.flush()
   s.add(I(void_id=v.id,telemetry_id=1));s.add(I(void_id=v.id,telemetry_id=2))
   time.sleep(1.5)
   s.commit()


def test_publish_blocks_on_void_confirmation_and_cannot_escape():
 """While another process holds the guard, publishing must wait, then judge."""
 make_telemetry([{'id':i,'sensor_id':17,'recorded_at':f'2026-11-05T00:0{i}:00','device_type':'pump','value':1.0} for i in range(1,6)])
 rid=make_report('cross',None,result=False)
 with Session() as s:
  s.get(Experiment,rid).status='running';s.commit()
 ctx=multiprocessing.get_context('spawn')
 p=ctx.Process(target=_other_connection_holds_guard_then_commits,args=(17,'2026-11-05T00:00:00','2026-11-05T00:01:00'))
 p.start()
 time.sleep(0.4)
 started=time.monotonic()
 with Session() as s:
  result=voids.publish(s,rid,{'checksum':'c','evidence_ids':[1,2,3]})
 elapsed=time.monotonic()-started
 p.join(10)
 assert p.exitcode==0
 assert elapsed>1.0,elapsed  # blocked on the guard row, did not slip through
 assert result['report_state']=='invalid'  # saw the void that committed meanwhile
 assert result['void_ids']


def _publish_child(rid,ids,ready,hold=1.5):
 """Child: write a report under the guard, signal, then commit after `hold`."""
 from src.config.database import Session as S
 from src.services import voids as v,concurrency
 with S() as s:
  with concurrency.critical(s):
   v._publish_locked(s,rid,{'checksum':'c','evidence_ids':ids})
   s.flush()
   # Uncommitted: the guard row stays locked, so a confirmation cannot proceed.
   # Once we commit, the confirmation sees the report and must still judge it.
   ready.set()
   time.sleep(hold)
   s.commit()


def test_confirmation_waits_for_inflight_publish_then_invalidates_it():
 """Publish wins the guard first; the confirmation must still judge the report."""
 make_telemetry([{'id':i,'sensor_id':17,'recorded_at':f'2026-11-05T00:0{i}:00','device_type':'pump','value':1.0} for i in range(1,6)])
 rid=make_report('inflight',None,result=False)
 with Session() as s:
  s.get(Experiment,rid).status='running';s.commit()
 ctx=multiprocessing.get_context('spawn')
 ready=ctx.Event()
 p=ctx.Process(target=_publish_child,args=(rid,[1,2,3],ready))
 p.start()
 assert ready.wait(10),'publish child never entered its critical section'
 result=voids.confirm(void_input(start='2026-11-05T00:00:00',end='2026-11-05T00:01:00'),User)
 p.join(10)
 assert p.exitcode==0
 assert rid in [r['id'] for r in result['invalid_reports']]
 with Session() as s:assert s.get(Experiment,rid).report_state=='invalid'


def test_two_processes_confirming_same_key_register_once():
 from src.config.database import Session as S
 make_telemetry([{'id':i,'sensor_id':17,'recorded_at':f'2026-11-05T00:0{i}:00','device_type':'pump','value':1.0} for i in range(1,4)])
 ctx=multiprocessing.get_context('spawn')
 procs=[ctx.Process(target=_confirm_same_key) for _ in range(2)]
 for p in procs:p.start()
 for p in procs:p.join(10)
 assert all(p.exitcode==0 for p in procs),[p.exitcode for p in procs]
 with S() as s:
  assert s.query(TelemetryVoid).count()==1
  assert s.query(TelemetryVoidItem).count()==2  # 00:01 and 00:02 are inside the window


def _confirm_same_key():
 from src.config.database import Session as S
 from src.schemas.business import VoidInput
 from src.services import voids as v
 data=VoidInput(sensor_id=17,start_at='2026-11-05T00:00:00',end_at='2026-11-05T00:02:00',reason='same intent',key='cross-shared-key')
 with S() as s:
  r=v.confirm(data,User)
  assert r['created'] in (True,False)
