"""复核全流程：提审 → 撤回/驳回 → 修改重提 → 批准，意见与操作者全程留痕。"""
import pytest
from fastapi import HTTPException
from src.config.database import Session
from src.models.review import FormulaReview
from src.schemas.review import ReviewCreate,ReviewDecision,ReviewResubmit
from src.services import review_service

ACTION_1="初版复核说明：名义配方与LHS通过率核查，结论待确认。"
ACTION_2="重提复核说明：已修正结论边界，扰动假设表述更新。"
ACTION_3="二次重提：补充活跃约束余量说明。"

class _U:
 def __init__(self,email,role=None):
  self.email=email
  self.role=role or ("admin" if email.startswith("admin@") else "analyst")

def _create(db,run_id,email,action=ACTION_1):
 return review_service.create(db,ReviewCreate(run_id=run_id,action=action),_U(email))

def test_full_reject_resubmit_approve_flow(session,completed_run,users):
 admin,analyst=users["admin"],users["analyst"]
 row=_create(session,completed_run,analyst)
 assert row.state=="submitted" and row.version==1 and row.created_by==analyst

 # 管理员驳回（必须带意见）
 with pytest.raises(HTTPException) as exc:
  review_service.decide(session,row,ReviewDecision(expected_version=1,comment=""),_U(admin),"reject")
 assert exc.value.status_code==422
 rejected=review_service.decide(session,row,
  ReviewDecision(expected_version=1,comment="驳回意见：结论依据不足，请修正重提。"),_U(admin),"reject")
 assert rejected.state=="rejected" and rejected.reviewer==""

 # 非 submitted 状态不能再批准：过期操作明确失败
 with pytest.raises(HTTPException) as exc:
  review_service.decide(session,row,ReviewDecision(expected_version=1),_U(admin),"approve")
 assert exc.value.status_code==409

 # 分析师修改重提，版本递增，历史保留
 row2=review_service.resubmit(session,row,ReviewResubmit(action=ACTION_2),_U(analyst))
 assert row2.id==row.id and row2.version==2 and row2.state=="submitted" and row2.action==ACTION_2

 # 版本不匹配的过期页面操作明确失败
 with pytest.raises(HTTPException) as exc:
  review_service.decide(session,row2,ReviewDecision(expected_version=1),_U(admin),"approve")
 assert exc.value.status_code==409 and "过期" in exc.value.detail

 approved=review_service.decide(session,row2,ReviewDecision(expected_version=2,comment="同意。"),_U(admin),"approve")
 assert approved.state=="approved" and approved.reviewer==admin

 # 每次意见与操作者完整保留
 events=review_service._events(session,row.id)
 assert [e.action for e in events]==["submit","reject","resubmit","approve"]
 assert events[0].actor==analyst and events[1].actor==admin
 assert "结论依据不足" in events[1].comment
 assert events[2].action=="resubmit" and events[2].detail["version"]==2
 assert [e.to_state for e in events]==["submitted","rejected","submitted","approved"]

def test_withdraw_then_resubmit_flow(session,completed_run,users):
 analyst=users["analyst"]
 row=_create(session,completed_run,analyst)
 withdrawn=review_service.decide(session,row,
  ReviewDecision(expected_version=1,comment="自查发现结论需修订"),_U(analyst),"withdraw")
 assert withdrawn.state=="withdrawn"
 # 已撤回不能直接批准
 with pytest.raises(HTTPException) as exc:
  review_service.decide(session,row,ReviewDecision(expected_version=1),_U(users["admin"]),"approve")
 assert exc.value.status_code==409
 row2=review_service.resubmit(session,row,ReviewResubmit(action=ACTION_3),_U(analyst))
 assert row2.version==2 and row2.state=="submitted"
 events=review_service._events(session,row.id)
 assert [e.action for e in events]==["submit","withdraw","resubmit"]
 assert events[1].actor==analyst

def test_duplicate_submission_blocked(session,completed_run,users):
 analyst=users["analyst"]
 first=_create(session,completed_run,analyst)
 with pytest.raises(HTTPException) as exc:
  _create(session,completed_run,analyst)
 assert exc.value.status_code==409
 # 撤回后允许重新提交一条新复核
 review_service.decide(session,first,ReviewDecision(expected_version=1),_U(analyst),"withdraw")
 new_row=_create(session,completed_run,analyst,ACTION_2)
 assert new_row.id!=first.id and new_row.version==1

def test_only_completed_run_can_submit(session,users):
 from src.models.run import BlendRun
 run=BlendRun(id="run-bad",scenario_id="sc-test",status="infeasible",result={},error="")
 session.add(run);session.commit()
 with pytest.raises(HTTPException) as exc:
  _create(session,"run-bad",users["analyst"])
 assert exc.value.status_code==409

def test_resubmit_requires_withdrawn_or_rejected(session,completed_run,users):
 row=_create(session,completed_run,users["analyst"])
 with pytest.raises(HTTPException) as exc:
  review_service.resubmit(session,row,ReviewResubmit(action=ACTION_2),_U(users["analyst"]))
 assert exc.value.status_code==409

def test_history_payload_shape(session,completed_run,users):
 row=_create(session,completed_run,users["analyst"])
 payload=review_service.with_history(session,row)
 assert payload["version"]==1 and payload["created_by"]==users["analyst"]
 assert len(payload["events"])==1 and payload["events"][0]["action"]=="submit"

def test_withdraw_and_resubmit_owner_only(session,completed_run,users):
 from src.models.user import User
 from src.utils.security import hash_password
 other=session.get(User,"user-analyst2")
 if other is None:
  other=User(id="user-analyst2",email="analyst2@pulp.demo",role="analyst",
   password_hash=hash_password("x"))
  session.add(other);session.commit()
 row=_create(session,completed_run,users["analyst"])
 # 其他分析师不能撤回
 with pytest.raises(HTTPException) as exc:
  review_service.decide(session,row,ReviewDecision(expected_version=1),_U(other.email),"withdraw")
 assert exc.value.status_code==403
 # 管理员可以代办撤回
 review_service.decide(session,row,ReviewDecision(expected_version=1),_U(users["admin"]),"withdraw")
 # 非提交人不能重提
 with pytest.raises(HTTPException) as exc:
  review_service.resubmit(session,row,ReviewResubmit(action=ACTION_2),_U(other.email))
 assert exc.value.status_code==403
 # 提交人本人可以重提
 again=review_service.resubmit(session,row,ReviewResubmit(action=ACTION_2),_U(users["analyst"]))
 assert again.state=="submitted" and again.version==2

def test_legacy_unowned_review_still_operable(session,completed_run,users):
 """升级前创建的在途复核没有 created_by，不能因归属缺失导致流程卡死。"""
 from src.models.review import FormulaReview
 row=_create(session,completed_run,users["analyst"])
 row.created_by="";session.commit()
 review_service.decide(session,row,ReviewDecision(expected_version=1),
  _U(users["analyst"]),"withdraw")
 assert row.state=="withdrawn"
