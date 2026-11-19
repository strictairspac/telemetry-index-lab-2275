from fastapi import APIRouter,Depends
from src.middlewares.auth import current,writer
from src.schemas.business import VoidInput
from src.services import voids
router=APIRouter()
@router.get('/voids')
def listing(u=Depends(current)):return voids.list_items()
@router.post('/voids/preview')
def preview(data:VoidInput,u=Depends(current)):return voids.preview(data)
@router.post('/voids')
def confirm(data:VoidInput,u=Depends(writer)):return voids.confirm(data,u)
