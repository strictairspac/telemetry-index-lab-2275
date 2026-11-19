from sqlalchemy import Column,Integer,String,JSON,DateTime,func,ForeignKey
from src.config.database import Base
class Experiment(Base):
 __tablename__='experiments'
 id=Column(Integer,primary_key=True)
 name=Column(String(120),unique=True,nullable=False)
 workload_id=Column(Integer,ForeignKey('workloads.id'),nullable=False)
 candidate_id=Column(Integer,ForeignKey('candidates.id'),nullable=False)
 status=Column(String(20),default='queued',nullable=False)
 result=Column(JSON,nullable=True)
 error=Column(String(1000),nullable=True)
 snapshot=Column(JSON,nullable=False)
 # Per-record evidence captured when the report is published. A NULL value means
 # the report predates evidence capture and cannot be re-judged without manual work.
 evidence=Column(JSON,nullable=True)
 # valid | invalid | unverified; NULL until a report exists.
 report_state=Column(String(20),nullable=True)
 invalid_reason=Column(String(1000),nullable=True)
 void_ids=Column(JSON,nullable=True)
 void_epoch=Column(Integer,nullable=True)
 published_at=Column(DateTime,nullable=True)
 created_at=Column(DateTime,server_default=func.now())
