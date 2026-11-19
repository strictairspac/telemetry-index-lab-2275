from sqlalchemy import Column,Integer,String,Float,DateTime,ForeignKey,UniqueConstraint,Index,func
from src.config.database import Base
class Telemetry(Base):
 __tablename__='telemetry'
 id=Column(Integer,primary_key=True)
 sensor_id=Column(Integer,nullable=False)
 recorded_at=Column(String(30),nullable=False)
 device_type=Column(String(40),nullable=False)
 value=Column(Float,nullable=False)


class TelemetryVoid(Base):
 """A confirmed calibration decision: readings of one sensor in a time window are void.

 `dedupe_key` makes confirmation retries idempotent: a retried request returns the
 original registration instead of creating a second one.
 """
 __tablename__='telemetry_voids'
 id=Column(Integer,primary_key=True)
 sensor_id=Column(Integer,nullable=False)
 start_at=Column(String(30),nullable=False)
 end_at=Column(String(30),nullable=False)
 reason=Column(String(500),nullable=False)
 actor=Column(String(120),nullable=False)
 dedupe_key=Column(String(64),nullable=False,unique=True)
 created_at=Column(DateTime,server_default=func.now())


class TelemetryVoidItem(Base):
 """Per-record membership of a void, materialised at confirmation time.

 Storing ids (rather than re-running queries) is what lets a confirmation judge
 every historical report without re-executing them.
 """
 __tablename__='telemetry_void_items'
 __table_args__=(UniqueConstraint('void_id','telemetry_id',name='uq_void_item'),Index('ix_void_item_telemetry','telemetry_id'))
 id=Column(Integer,primary_key=True)
 void_id=Column(Integer,ForeignKey('telemetry_voids.id'),nullable=False)
 telemetry_id=Column(Integer,nullable=False)


class VoidGuard(Base):
 """Singleton row used as the serialisation point for publish vs. void.

 Both publishing a report and confirming a void take this row `FOR UPDATE`, so a
 report that is being published concurrently with a confirmation is either seen
 by the confirmation scan or judged against the new void at publish time.
 """
 __tablename__='void_guard'
 id=Column(Integer,primary_key=True)
 epoch=Column(Integer,nullable=False,default=0)
 updated_at=Column(DateTime,server_default=func.now(),onupdate=func.now())
