import os
os.environ.setdefault('DATABASE_URL','sqlite:////tmp/index-trial-void-tests.db')
os.environ.setdefault('JWT_SECRET','test-secret')
os.environ.setdefault('REDIS_URL','redis://localhost:6379/15')

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import pytest
from src.config.database import Base,engine,Session
from src.models import identity,workload,candidate,experiment,telemetry  # noqa: F401


@pytest.fixture(autouse=True)
def clean_db():
 # Non-pooled connections: an unclosed transaction (e.g. one still holding the
 # void_guard FOR UPDATE row) would otherwise block DROP TABLE on MySQL.
 engine.dispose()
 Base.metadata.drop_all(engine)
 Base.metadata.create_all(engine)
 engine.dispose()
 yield
 engine.dispose()


def make_telemetry(rows):
 with Session() as s:
  s.bulk_insert_mappings(telemetry.Telemetry,rows)
  s.commit()


def make_report(name,evidence_ids,result=True,status='completed'):
 with Session() as s:
  w=workload.Workload(name=f'w-{name}',sensor_id=17,start_at='2026-11-01T00:00:00',end_at='2026-11-30T23:59:59',device_type=None,description='')
  s.add(w);s.flush()
  c=candidate.Candidate(name=f'c-{name}',workload_id=w.id,columns=['sensor_id','recorded_at'],note='')
  s.add(c);s.flush()
  e=experiment.Experiment(name=name,workload_id=w.id,candidate_id=c.id,status=status,snapshot={'workload':{'sensor_id':17,'start_at':'2026-11-01T00:00:00','end_at':'2026-11-30T23:59:59'},'candidate':{'columns':['sensor_id','recorded_at']}})
  if result:e.result={'checksum':'x','evidence_ids':evidence_ids}
  if evidence_ids is not None:e.evidence={'ids':evidence_ids,'count':len(evidence_ids),'checksum':'x'}
  s.add(e);s.commit();s.refresh(e)
  return e.id


class User:
 email='operator@index.local'


def void_input(sensor=17,start='2026-11-05T00:00:00',end='2026-11-06T00:00:00',reason='校准发现读数漂移',key=None):
 from src.schemas.business import VoidInput
 return VoidInput(sensor_id=sensor,start_at=start,end_at=end,reason=reason,key=key)
