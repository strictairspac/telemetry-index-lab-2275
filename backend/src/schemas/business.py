from pydantic import BaseModel,Field,model_validator
from datetime import datetime
from src.constants.enums import COLUMNS
class Login(BaseModel):
 email:str;password:str
class WorkloadInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 sensor_id:int=Field(ge=1,le=1000)
 start_at:str='2026-11-01T00:00:00'
 end_at:str='2026-11-30T23:59:59'
 device_type:str|None=None
 description:str=Field(default='',max_length=500)
 @model_validator(mode='after')
 def valid_dates(self):
  a=datetime.fromisoformat(self.start_at);b=datetime.fromisoformat(self.end_at)
  if a>=b:raise ValueError('结束时间必须晚于开始时间')
  if self.device_type not in (None,'pump','motor','valve'):raise ValueError('设备类型无效')
  self.start_at=a.isoformat(timespec='seconds');self.end_at=b.isoformat(timespec='seconds')
  return self
class CandidateInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 workload_id:int
 columns:list[str]=Field(min_length=1,max_length=4)
 note:str=Field(default='',max_length=500)
 @model_validator(mode='after')
 def columns_valid(self):
  if len(set(self.columns))!=len(self.columns) or any(x not in COLUMNS for x in self.columns):raise ValueError('索引列必须唯一且来自白名单')
  return self
class ExperimentInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 candidate_id:int
class VoidInput(BaseModel):
 sensor_id:int=Field(ge=1,le=1000)
 start_at:str
 end_at:str
 reason:str=Field(min_length=2,max_length=500)
 # Client-generated idempotency key. Re-sending the same key after an interrupted
 # confirmation returns the original registration instead of creating another one.
 key:str|None=Field(default=None,max_length=64)
 @model_validator(mode='after')
 def valid_window(self):
  a=datetime.fromisoformat(self.start_at);b=datetime.fromisoformat(self.end_at)
  if a>=b:raise ValueError('结束时间必须晚于开始时间')
  self.start_at=a.isoformat(timespec='seconds');self.end_at=b.isoformat(timespec='seconds')
  return self
