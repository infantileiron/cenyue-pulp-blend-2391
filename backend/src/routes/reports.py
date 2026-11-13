from fastapi import APIRouter,Depends
from fastapi.responses import Response,JSONResponse
from ..config.database import get_db
from ..utils.auth import current,admin
from ..schemas.report import ReportCreate
from ..controllers import report_controller as controller,common
from ..models.report import Report
from ..services.report_service import export
router=APIRouter(prefix="/reports",tags=["reports"])
@router.get("")
def listing(db=Depends(get_db),user=Depends(current)):return controller.list_all(db)
@router.get("/{ident}")
def detail(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail(db,ident)
@router.post("")
def create(body:ReportCreate,db=Depends(get_db),user=Depends(admin)):
 payload,status_code=controller.create(db,body)
 # 首次归档 201；重复归档返回同一份快照，200 表示未新建
 return JSONResponse(payload,status_code=status_code)
@router.get("/{ident}/csv")
def recipe(ident:str,db=Depends(get_db),user=Depends(current)):
 return Response(export(common.require(db,Report,ident)),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=pulp-formula.csv"})
@router.get("/{ident}/samples.csv")
def samples(ident:str,db=Depends(get_db),user=Depends(current)):
 return Response(export(common.require(db,Report,ident),samples=True),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=pulp-lhs-samples.csv"})
