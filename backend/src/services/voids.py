"""Void registration and per-report judgement.

Design notes
------------
* Confirmation materialises the voided telemetry ids (`telemetry_void_items`). Later
  judgements intersect stored evidence with those ids — historical trial queries are
  never re-executed.
* A report that is published while a confirmation is in flight cannot be missed:
  both take the `void_guard` row in `concurrency.critical`. Either the confirmation
  scan sees the published report, or the publish sees the committed void.
* Reports published before per-record evidence existed cannot be judged by
  intersection. They are marked `unverified` only when their snapshot window
  overlaps the void (a pure range comparison); otherwise they stay untouched.
"""
import hashlib
from datetime import datetime
from sqlalchemy import func
from fastapi import HTTPException
from src.config.database import Session
from src.models.experiment import Experiment
from src.models.telemetry import Telemetry,TelemetryVoid,TelemetryVoidItem
from src.services import concurrency
from src.services.audit import log
from src.utils.serialization import record

_CHUNK=500

def _chunks(items):
 for i in range(0,len(items),_CHUNK):yield items[i:i+_CHUNK]

def dedupe_key(data):
 # An explicit client key survives retries of the same intent. Without one, the
 # content itself is the key, so repeating an identical registration is a no-op
 # instead of a second window.
 if data.key:return data.key
 raw=f'{data.sensor_id}|{data.start_at}|{data.end_at}|{data.reason}'
 return 'auto:'+hashlib.sha256(raw.encode()).hexdigest()[:58]

def matched_ids(session,sensor,start,end):
 return [r[0] for r in session.query(Telemetry.id).filter(Telemetry.sensor_id==sensor,Telemetry.recorded_at>=start,Telemetry.recorded_at<=end).order_by(Telemetry.id).all()]

def evidence_hits(session,ids):
 hits={}
 for chunk in _chunks(list(ids)):
  for void_id,count in session.query(TelemetryVoidItem.void_id,func.count(TelemetryVoidItem.id)).filter(TelemetryVoidItem.telemetry_id.in_(chunk)).group_by(TelemetryVoidItem.void_id).all():
   hits[int(void_id)]=hits.get(int(void_id),0)+int(count)
 return hits

def _evidence_ids(report):
 ev=report.evidence
 if isinstance(ev,dict) and isinstance(ev.get('ids'),list):return [int(x) for x in ev['ids']]
 return None

def _overlaps(snapshot,sensor,start,end):
 w=(snapshot or {}).get('workload') or {}
 if w.get('sensor_id')!=sensor:return False
 ws,we=w.get('start_at'),w.get('end_at')
 if not ws or not we:return True
 return str(ws)<end and start<str(we)

def _void_label(void):
 return f'作废 #{void.id}（sensor {void.sensor_id}，{void.start_at} → {void.end_at}）'

def _invalid_reason(label,hits):
 return f'{label} 命中本报告 {hits} 条读数；报告编号保留，结论失效，需按排除作废记录后的新试验重新判断。'[:1000]

def _unverified_reason(label):
 return f'{label} 与报告输入时段重叠，但该报告缺少逐条读数证据，无法自动判定；标记待核验，请人工核对后再引用。'[:1000]

def _scan(session,sensor,start,end,new_ids,void=None):
 """Judge published reports against `new_ids`; with `void=None` only preview."""
 out={'invalid':[],'unverified':[]}
 new_set=set(new_ids)
 for r in session.query(Experiment).filter(Experiment.status=='completed').all():
  if r.report_state=='invalid':continue
  ids=_evidence_ids(r)
  if ids is not None:
   total=len(new_set.intersection(ids))
   if total:
    if void is not None:
     r.report_state='invalid'
     r.invalid_reason=_invalid_reason(_void_label(void),total)
     r.void_ids=sorted(set((r.void_ids or [])+[void.id]))
    out['invalid'].append({'id':r.id,'name':r.name,'hits':total})
  elif _overlaps(r.snapshot,sensor,start,end):
   if void is not None and r.report_state!='unverified':
    r.report_state='unverified'
    r.invalid_reason=_unverified_reason(_void_label(void))
   out['unverified'].append({'id':r.id,'name':r.name})
 return out

def list_items():
 with Session() as s:
  return [{**record(v),'records':int(s.query(func.count(TelemetryVoidItem.id)).filter(TelemetryVoidItem.void_id==v.id).scalar() or 0)} for v in s.query(TelemetryVoid).order_by(TelemetryVoid.id.desc()).limit(100)]

def preview(data):
 with Session() as s:
  ids=matched_ids(s,data.sensor_id,data.start_at,data.end_at)
  result=_scan(s,data.sensor_id,data.start_at,data.end_at,new_ids=ids)
  existing=[record(v) for v in s.query(TelemetryVoid).filter(TelemetryVoid.sensor_id==data.sensor_id,TelemetryVoid.start_at<data.end_at,data.start_at<TelemetryVoid.end_at).order_by(TelemetryVoid.id).all()]
  return {'sensor_id':data.sensor_id,'start_at':data.start_at,'end_at':data.end_at,'reason':data.reason,'matched_records':len(ids),'sample_ids':ids[:20],'invalid_reports':result['invalid'],'unverified_reports':result['unverified'],'overlapping_voids':existing}

def confirm(data,user):
 key=dedupe_key(data)
 with Session() as s:
  with concurrency.critical(s) as guard:
   existing=s.query(TelemetryVoid).filter_by(dedupe_key=key).first()
   if existing:
    return {'void':record(existing),'created':False,'matched_records':int(s.query(func.count(TelemetryVoidItem.id)).filter(TelemetryVoidItem.void_id==existing.id).scalar() or 0),'invalid_reports':[],'unverified_reports':[],'message':'该作废已登记，本次为重试，未重复登记'}
   ids=matched_ids(s,data.sensor_id,data.start_at,data.end_at)
   void=TelemetryVoid(sensor_id=data.sensor_id,start_at=data.start_at,end_at=data.end_at,reason=data.reason,actor=user.email,dedupe_key=key)
   s.add(void);s.flush()
   # flush, not commit: the guard row must stay locked until the whole judgement
   # (items, epoch bump, report scan, audit) is committed as one unit.
   for chunk in _chunks(ids):s.bulk_insert_mappings(TelemetryVoidItem,[{'void_id':void.id,'telemetry_id':i} for i in chunk])
   guard.epoch=(guard.epoch or 0)+1
   affected=_scan(s,data.sensor_id,data.start_at,data.end_at,new_ids=ids,void=void)
   log(user.email,'void.confirm',f'void={void.id} sensor={data.sensor_id} window={data.start_at}..{data.end_at} records={len(ids)} invalid={len(affected["invalid"])} unverified={len(affected["unverified"])}',session=s)
   s.commit();s.refresh(void)
   return {'void':record(void),'created':True,'matched_records':len(ids),'invalid_reports':affected['invalid'],'unverified_reports':affected['unverified'],'message':f'已作废 {len(ids)} 条读数；后续新试验自动排除，已发布报告已按逐条证据复核'}

def _publish_locked(session,experiment_id,result):
 """Write the report while the caller already holds the critical section."""
 r=session.get(Experiment,experiment_id)
 if not r:raise HTTPException(404,'未找到试验')
 # Publishing is one transaction, so a report that already exists was published
 # before; re-entry (e.g. a retried worker message) must not overwrite its verdict.
 if r.result is not None:return r
 ids=sorted(int(x) for x in (result.get('evidence_ids') or []))
 hits=evidence_hits(session,ids) if ids else {}
 r.result=result;r.status='completed';r.error=None
 r.evidence={'ids':ids,'count':len(ids),'checksum':result.get('checksum')}
 r.published_at=datetime.utcnow()
 if hits:
  void_ids=sorted(hits)
  r.report_state='invalid';r.void_ids=void_ids
  labels=[]
  for vid in void_ids:
   v=session.get(TelemetryVoid,vid)
   labels.append(f'{_void_label(v)} 命中 {hits[vid]} 条' if v else f'作废 #{vid} 命中 {hits[vid]} 条')
  r.invalid_reason=('发布时已存在作废记录：'+'；'.join(labels)+'。报告编号保留，结论失效。')[:1000]
 else:
  r.report_state='valid';r.invalid_reason=None;r.void_ids=[]
 return r

def publish(session,experiment_id,result):
 """Publish a finished trial atomically with the void judgement. Idempotent."""
 with concurrency.critical(session) as guard:
  r=_publish_locked(session,experiment_id,result)
  r.void_epoch=int(guard.epoch or 0)
  session.commit();session.refresh(r)
  return record(r)
