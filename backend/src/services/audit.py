from src.config.database import Session
from src.models.identity import Audit
def log(actor,action,detail='',session=None):
 # Callers that must keep the audit row atomic with their own transaction pass
 # their session; the default keeps the original standalone behaviour.
 if session is not None:session.add(Audit(actor=actor,action=action,detail=detail));return
 with Session() as s:s.add(Audit(actor=actor,action=action,detail=detail));s.commit()
