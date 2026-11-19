import threading
from src.config.database import Session
from src.models.experiment import Experiment
from src.models.telemetry import Telemetry,TelemetryVoid,TelemetryVoidItem
from src.services import voids
from tests.conftest import User,make_report,make_telemetry,void_input


def _report(report_id):
 with Session() as s:return s.get(Experiment,report_id)


def _rows(count=10,start=0):
 # sensor 17, minute-spaced entries on 2026-11-05
 return [{'id':i+1,'sensor_id':17,'recorded_at':f'2026-11-05T00:{i:02d}:00','device_type':'pump','value':30.0} for i in range(start,start+count)]


def test_confirmed_void_excludes_records_from_new_trial_query():
 from src.services.telemetry_query import build_query
 make_telemetry(_rows(5)+[{'id':100,'sensor_id':36,'recorded_at':'2026-11-05T00:00:00','device_type':'motor','value':1.0}])
 result=voids.confirm(void_input(start='2026-11-05T00:00:00',end='2026-11-05T00:03:00'),User)
 assert result['created'] is True
 assert result['matched_records']==4
 query,params=build_query({'sensor_id':17,'start_at':'2026-11-01T00:00:00','end_at':'2026-11-30T23:59:59','device_type':None})
 assert 'telemetry_void_items' in query
 with Session() as s:
  from sqlalchemy import text
  ids=[r[0] for r in s.execute(text(query.replace(':sensor',':sensor').replace(':start',':start').replace(':end',':end')),params)]
 assert ids==[5],ids


def test_reports_with_evidence_are_invalidated_only_when_records_hit():
 make_telemetry(_rows(6))
 hit=make_report('hit',[1,2,3])
 miss=make_report('miss',[4,5,6])
 result=voids.confirm(void_input(start='2026-11-05T00:00:00',end='2026-11-05T00:01:00'),User)
 assert [r['id'] for r in result['invalid_reports']]==[hit]
 with Session() as s:
  h=s.get(Experiment,hit);m=s.get(Experiment,miss)
  assert h.report_state=='invalid' and '命中本报告 2 条' in h.invalid_reason
  assert h.id==hit  # number preserved
  assert m.report_state is None and m.invalid_reason is None


def test_old_report_without_evidence_is_unverified_only_when_window_overlaps():
 overlap=make_report('old-overlap',None)
 with Session() as s:
  e=s.get(Experiment,overlap);e.snapshot={'workload':{'sensor_id':17,'start_at':'2026-11-03T00:00:00','end_at':'2026-11-04T00:00:00'}};s.commit()
 inday=make_report('old-inday',None)
 with Session() as s:
  e=s.get(Experiment,inday);e.snapshot={'workload':{'sensor_id':17,'start_at':'2026-11-04T00:00:00','end_at':'2026-11-06T00:00:00'}};s.commit()
 result=voids.confirm(void_input(start='2026-11-05T00:00:00',end='2026-11-05T12:00:00'),User)
 unverified={r['id'] for r in result['unverified_reports']}
 assert unverified=={inday}
 with Session() as s:
  assert s.get(Experiment,inday).report_state=='unverified'
  assert s.get(Experiment,overlap).report_state is None
  assert [i['id'] for i in result['invalid_reports']]==[]


def test_retry_with_same_key_does_not_register_twice():
 make_telemetry(_rows(4))
 data=void_input(key='calib-2026-11-05')
 first=voids.confirm(data,User)
 second=voids.confirm(void_input(key='calib-2026-11-05'),User)
 assert first['created'] is True and second['created'] is False
 assert second['message'].startswith('该作废已登记')
 with Session() as s:
  assert s.query(TelemetryVoid).count()==1
  assert s.query(TelemetryVoidItem).count()==4


def test_identical_registration_without_key_is_idempotent():
 make_telemetry(_rows(4))
 assert voids.confirm(void_input(),User)['created'] is True
 assert voids.confirm(void_input(),User)['created'] is False
 with Session() as s:assert s.query(TelemetryVoid).count()==1


def test_historical_reports_are_not_requeried():
 """Confirmation intersects stored evidence; it never rebuilds trial results."""
 make_telemetry(_rows(5))
 hit=make_report('hit',[1,2])
 voids.confirm(void_input(start='2026-11-05T00:00:00',end='2026-11-05T00:01:00'),User)
 with Session() as s:
  e=s.get(Experiment,hit)
  assert e.result=={'checksum':'x','evidence_ids':[1,2]}  # untouched
  assert e.evidence['ids']==[1,2]
  assert e.report_state=='invalid'


def test_publish_sees_existing_void_even_without_confirmation_scan():
 make_telemetry(_rows(3))
 voids.confirm(void_input(start='2026-11-05T00:00:00',end='2026-11-05T00:02:00'),User)  # 3 rows
 rid=make_report('late',None,result=False)
 with Session() as s:
  e=s.get(Experiment,rid);e.status='running';s.commit()
 result={'checksum':'y','evidence_ids':[1,2,3]}
 with Session() as s:published=voids.publish(s,rid,result)
 assert published['report_state']=='invalid'
 assert '发布时已存在作废记录' in published['invalid_reason']
 assert published['void_ids']==[1]


def test_publish_twice_is_idempotent():
 rid=make_report('retry',None,result=False)
 with Session() as s:
  e=s.get(Experiment,rid);e.status='running';s.commit()
 with Session() as s:first=voids.publish(s,rid,{'checksum':'y','evidence_ids':[9]})
 with Session() as s:second=voids.publish(s,rid,{'checksum':'z','evidence_ids':[9]})
 assert first['report_state']=='valid' and second['report_state']=='valid'
 assert second['result']['checksum']=='y'


def test_void_colliding_with_publish_hit_and_miss_get_different_verdicts():
 """Two reports in the same window: one read voided rows, one did not.

 The publish and the confirmation run concurrently. Whichever wins the guard row,
 the hit report must end invalid and the miss report must end valid — a report
 published concurrently with a confirmation cannot escape judgement.
 """
 make_telemetry(_rows(10))
 hit=make_report('hit',None,result=False)
 miss=make_report('miss',None,result=False)
 with Session() as s:
  s.get(Experiment,hit).status='running'
  s.get(Experiment,miss).status='running'
  s.commit()
 barrier=threading.Barrier(3)
 errors=[]
 def publish(rid,ids):
  try:
   with Session() as s:
    barrier.wait()
    voids.publish(s,rid,{'checksum':str(rid),'evidence_ids':ids})
  except Exception as exc:errors.append(exc)
 def confirm():
  try:
   barrier.wait()
   voids.confirm(void_input(start='2026-11-05T00:00:00',end='2026-11-05T00:01:00'),User)
  except Exception as exc:errors.append(exc)
 threads=[threading.Thread(target=publish,args=(hit,[1,2,3])),threading.Thread(target=publish,args=(miss,[7,8,9])),threading.Thread(target=confirm)]
 for t in threads:t.start()
 for t in threads:t.join()
 assert not errors,errors
 with Session() as s:
  h=s.get(Experiment,hit);m=s.get(Experiment,miss)
  assert h.report_state=='invalid',h.report_state
  assert m.report_state=='valid',m.report_state
  assert h.result['evidence_ids']==[1,2,3] and m.result['evidence_ids']==[7,8,9]


def test_preview_writes_nothing():
 make_telemetry(_rows(5))
 rid=make_report('hit',[1,2])
 preview=voids.preview(void_input(start='2026-11-05T00:00:00',end='2026-11-05T00:01:00'))
 assert preview['matched_records']==2
 assert [r['id'] for r in preview['invalid_reports']]==[rid]
 with Session() as s:
  assert s.query(TelemetryVoid).count()==0
  assert s.get(Experiment,rid).report_state is None
