import redis
from fastapi import HTTPException
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models.workload import Workload
from src.models.candidate import Candidate
from src.models.experiment import Experiment
from src.utils.serialization import record
queue=redis.Redis.from_url(REDIS_URL)
# Listing keeps the verdict and the result shown on the report page, but drops the
# per-record evidence (it can hold thousands of ids). Detail/export carry it all.
def _brief(row):
 data=record(row)
 data.pop('evidence',None)
 result=data.get('result')
 if isinstance(result,dict):
  result=dict(result);result.pop('evidence_ids',None);data['result']=result
 return data
def list_items():
 with Session() as s:return [_brief(r) for r in s.query(Experiment).order_by(Experiment.id.desc()).limit(100).all()]
def detail(item_id):
 with Session() as s:
  row=s.get(Experiment,item_id)
  if not row:raise HTTPException(404,'未找到试验')
  return record(row)
def create(data):
 with Session() as s:
  c=s.get(Candidate,data.candidate_id)
  if not c:raise HTTPException(404,'未找到候选')
  w=s.get(Workload,c.workload_id)
  row=Experiment(name=data.name,candidate_id=c.id,workload_id=w.id,status='queued',snapshot={'workload':record(w),'candidate':record(c)})
  s.add(row);s.commit();s.refresh(row);result=record(row)
 try:queue.rpush('index-trials',result['id'])
 except redis.RedisError:
  with Session() as s:r=s.get(Experiment,result['id']);r.status='failed';r.error='队列不可用，请创建新试验';s.commit()
  raise HTTPException(503,'队列不可用，请稍后重新执行')
 return result
