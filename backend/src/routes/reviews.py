from fastapi import APIRouter,Depends
from ..config.database import get_db
from ..utils.auth import current,write_user,admin
from ..schemas.review import ReviewCreate,ReviewDecision,ReviewResubmit
from ..controllers import review_controller as controller
router=APIRouter(prefix="/reviews",tags=["reviews"])
@router.get("")
def listing(db=Depends(get_db),user=Depends(current)):return controller.list_all(db)
@router.get("/{ident}")
def detail(ident:str,db=Depends(get_db),user=Depends(current)):return controller.detail(db,ident)
@router.get("/{ident}/events")
def events(ident:str,db=Depends(get_db),user=Depends(current)):return controller.events(db,ident)
@router.post("",status_code=201)
def create(body:ReviewCreate,db=Depends(get_db),user=Depends(write_user)):return controller.create(db,body,user)
@router.post("/{ident}/approve")
def approve_review(ident:str,body:ReviewDecision,db=Depends(get_db),user=Depends(admin)):
 return controller.approve(db,ident,body,user)
@router.post("/{ident}/withdraw")
def withdraw_review(ident:str,body:ReviewDecision,db=Depends(get_db),user=Depends(write_user)):
 return controller.withdraw(db,ident,body,user)
@router.post("/{ident}/reject")
def reject_review(ident:str,body:ReviewDecision,db=Depends(get_db),user=Depends(admin)):
 return controller.reject(db,ident,body,user)
@router.post("/{ident}/resubmit",status_code=201)
def resubmit_review(ident:str,body:ReviewResubmit,db=Depends(get_db),user=Depends(write_user)):
 return controller.resubmit(db,ident,body,user)
