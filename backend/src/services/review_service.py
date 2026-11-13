from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select,update
from ..constants.enums import ReviewState,ReviewAction
from ..models.review import FormulaReview,ReviewEvent
from ..models.run import BlendRun

def _add_event(db,row,action,from_state,to_state,actor,comment="",**detail):
 event=ReviewEvent(id=str(uuid4()),review_id=row.id,action=action,from_state=from_state or "",
  to_state=to_state or "",actor=actor or "",comment=comment or "",detail=detail)
 db.add(event);return event

def _events(db,review_id):
 return db.scalars(select(ReviewEvent).where(ReviewEvent.review_id==review_id).order_by(ReviewEvent.created_at,ReviewEvent.id)).all()

def create(db,body,user):
 run=db.get(BlendRun,body.run_id)
 if run is None or run.status!="completed":raise HTTPException(409,"仅已完成运行可提交复核")
 # MySQL 下行锁串行化同一运行的并发提审；配合在途检查防止两个待复核并存
 locked_run=db.scalar(select(BlendRun).where(BlendRun.id==body.run_id).with_for_update())
 if locked_run is not None:run=locked_run
 pending=db.scalar(select(FormulaReview).where(FormulaReview.run_id==body.run_id,FormulaReview.state==ReviewState.SUBMITTED))
 if pending is not None:raise HTTPException(409,"该运行已有待复核的配方复核，请等待处理或先撤回")
 row=FormulaReview(id=str(uuid4()),run_id=body.run_id,action=body.action,state=ReviewState.SUBMITTED,
  reviewer="",version=1,created_by=user.email)
 db.add(row);db.flush()
 _add_event(db,row,ReviewAction.SUBMIT,"",ReviewState.SUBMITTED,user.email,body.action,version=1)
 db.commit();return row

def _ensure_owner(row,user):
 """撤回/重提仅限提交人本人；管理员可代办；升级前无提交人的历史行不做限制。"""
 if user.role=="admin" or not row.created_by or row.created_by==user.email:return
 raise HTTPException(403,"仅提交人本人可撤回或重新提交该复核")

def _conflict(db,review_id,expected_version):
 """仲裁失败后读取最新行，区分“已处理”与“页面过期”，给出明确失败原因。"""
 db.rollback()
 current=db.get(FormulaReview,review_id)
 if current is None:raise HTTPException(404,"复核记录不存在")
 if current.version!=expected_version:
  raise HTTPException(409,f"页面数据已过期（页面版本{expected_version}，当前版本{current.version}），请刷新后重试")
 raise HTTPException(409,f"复核已处理（当前状态：{current.state}），该页面操作已失效，请刷新后重试")

def decide(db,row,body,user,decision):
 """批准/撤回/驳回共用同一仲裁。

 以单条条件 UPDATE 完成状态机迁移（WHERE 限定 submitted + 页面版本号）：
 MySQL 行锁与 SQLite 库锁都只会让一个事务更新成功，rowcount=0 即争抢失败，
 不依赖先查后写的读一致性，并发处理只接受一个结果。
 """
 target={
  ReviewAction.APPROVE:ReviewState.APPROVED,
  ReviewAction.WITHDRAW:ReviewState.WITHDRAWN,
  ReviewAction.REJECT:ReviewState.REJECTED,
 }[decision]
 if decision==ReviewAction.WITHDRAW:_ensure_owner(row,user)
 if decision==ReviewAction.REJECT and not body.comment.strip():
  raise HTTPException(422,"驳回必须填写驳回意见，供分析师修改重提")
 values={"state":target.value}
 if decision==ReviewAction.APPROVE:values["reviewer"]=user.email
 stmt=(update(FormulaReview)
  .where(FormulaReview.id==row.id,
         FormulaReview.state==ReviewState.SUBMITTED,
         FormulaReview.version==body.expected_version)
  .values(**values).execution_options(synchronize_session=False))
 if db.execute(stmt).rowcount!=1:
  _conflict(db,row.id,body.expected_version)
 db.refresh(row)
 _add_event(db,row,decision,ReviewState.SUBMITTED,target,user.email,body.comment,version=row.version)
 db.commit();return row

def resubmit(db,row,body,user):
 """撤回或驳回后修改重提：条件 UPDATE 保证只有 withdrawn/rejected 行可迁移，版本递增。"""
 _ensure_owner(row,user)
 from_state=row.state
 stmt=(update(FormulaReview)
  .where(FormulaReview.id==row.id,
         FormulaReview.state.in_([ReviewState.WITHDRAWN,ReviewState.REJECTED]))
  .values(action=body.action,state=ReviewState.SUBMITTED,reviewer="",
          version=FormulaReview.version+1)
  .execution_options(synchronize_session=False))
 if db.execute(stmt).rowcount!=1:
  db.rollback()
  current=db.get(FormulaReview,row.id)
  raise HTTPException(409,f"仅已撤回或已驳回的复核可修改重提（当前状态：{current.state if current else '不存在'}）")
 db.refresh(row)
 _add_event(db,row,ReviewAction.RESUBMIT,from_state,ReviewState.SUBMITTED,
  user.email,body.action,version=row.version)
 db.commit();return row

def with_history(db,row):
 from ..models.common import serialize
 data=serialize(row)
 data["events"]=[serialize(e) for e in _events(db,row.id)]
 return data
