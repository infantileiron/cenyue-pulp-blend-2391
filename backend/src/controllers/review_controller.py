from sqlalchemy import select
from ..services import review_service
from ..models.review import FormulaReview,ReviewEvent
from ..models.common import serialize
from .common import require
def list_all(db):
 rows=db.scalars(select(FormulaReview).order_by(FormulaReview.created_at.desc()).limit(200)).all()
 return [review_service.with_history(db,row) for row in rows]
def detail(db,ident):return review_service.with_history(db,require(db,FormulaReview,ident))
def create(db,body,user):
 row=review_service.create(db,body,user)
 return review_service.with_history(db,row)
def approve(db,ident,body,user):
 row=review_service.decide(db,require(db,FormulaReview,ident),body,user,"approve")
 return review_service.with_history(db,row)
def withdraw(db,ident,body,user):
 row=review_service.decide(db,require(db,FormulaReview,ident),body,user,"withdraw")
 return review_service.with_history(db,row)
def reject(db,ident,body,user):
 row=review_service.decide(db,require(db,FormulaReview,ident),body,user,"reject")
 return review_service.with_history(db,row)
def resubmit(db,ident,body,user):
 row=review_service.resubmit(db,require(db,FormulaReview,ident),body,user)
 return review_service.with_history(db,row)
def events(db,ident):
 require(db,FormulaReview,ident)
 rows=db.scalars(select(ReviewEvent).where(ReviewEvent.review_id==ident).order_by(ReviewEvent.created_at,ReviewEvent.id)).all()
 return [serialize(row) for row in rows]
