"""The one SELECT used by trials, with voided readings excluded.

Kept separate from the MySQL-specific runner so the exclusion clause can be
exercised without a live MySQL (the SQL is portable and also runs on SQLite).
"""
def build_query(w):
 params={'sensor':w['sensor_id'],'start':w['start_at'],'end':w['end_at']}
 query='SELECT id,sensor_id,recorded_at,device_type,value FROM telemetry WHERE sensor_id=:sensor AND recorded_at>=:start AND recorded_at<=:end'
 if w.get('device_type'):
  query+=' AND device_type=:device'
  params['device']=w['device_type']
 query+=' AND NOT EXISTS (SELECT 1 FROM telemetry_void_items v WHERE v.telemetry_id=telemetry.id)'
 query+=' ORDER BY id'
 return query,params
