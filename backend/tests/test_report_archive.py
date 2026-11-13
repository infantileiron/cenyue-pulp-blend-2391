"""归档规则：只引用当次已批准结论；重复归档同一份；已归档不随后续修改变化；旧快照兼容。"""
import threading
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from src.config.database import Session
from src.models.review import FormulaReview
from src.models.report import Report
from src.models.run import BlendRun
from src.schemas.review import ReviewCreate,ReviewDecision,ReviewResubmit
from src.schemas.report import ReportCreate
from src.services import review_service,report_service

ACTION_A="第一版复核说明，用于第一次批准与归档。"
ACTION_B="重提后的复核说明，内容与第一版明显不同。"

class _U:
 def __init__(self,email):
  self.email=email
  self.role="admin" if email.startswith("admin@") else "analyst"

def _review(session,run_id,email,action=ACTION_A):
 return review_service.create(session,ReviewCreate(run_id=run_id,action=action),_U(email))

def _approve(session,row,email,version,comment="同意"):
 return review_service.decide(session,row,ReviewDecision(expected_version=version,comment=comment),
  _U(email),"approve")

def test_archive_requires_approved_review(session,completed_run,users):
 row=_review(session,completed_run,users["analyst"])
 with pytest.raises(HTTPException) as exc:
  report_service.create(session,ReportCreate(review_id=row.id,title="底稿"))
 assert exc.value.status_code==409
 # 驳回后同样不能归档
 review_service.decide(session,row,ReviewDecision(expected_version=1,comment="依据不足"),
  _U(users["admin"]),"reject")
 with pytest.raises(HTTPException) as exc:
  report_service.create(session,ReportCreate(review_id=row.id,title="底稿"))
 assert exc.value.status_code==409

def test_duplicate_archive_returns_same_report(session,completed_run,users):
 row=_approve(session,_review(session,completed_run,users["analyst"]),users["admin"],1)
 first,created1=report_service.create(session,ReportCreate(review_id=row.id,title="第一次归档"))
 second,created2=report_service.create(session,ReportCreate(review_id=row.id,title="重复归档换标题"))
 assert first.id==second.id and second.title=="第一次归档"
 assert created1 is True and created2 is False
 assert len(session.scalars(select(Report).where(Report.review_id==row.id)).all())==1

def test_concurrent_archive_single_row(session,completed_run,users):
 row=_approve(session,_review(session,completed_run,users["analyst"]),users["admin"],1)
 review_id=row.id;session.close()
 results=[];flags=[];barrier=threading.Barrier(3)
 def worker():
  with Session() as db:
   barrier.wait()
   # 唯一约束 + 先查后建兜底：并发归档只允许一份，其余返回同一行且标记未新建
   rep,created=report_service.create(db,ReportCreate(review_id=review_id,title="并发归档"))
   results.append(rep.id);flags.append(created)
 threads=[threading.Thread(target=worker) for _ in range(3)]
 for t in threads:t.start()
 for t in threads:t.join(timeout=60)
 assert len(results)==3 and len(set(results))==1
 assert flags.count(True)==1 and flags.count(False)==2
 with Session() as db:
  assert len(db.scalars(select(Report).where(Report.review_id==review_id)).all())==1

def test_archived_snapshot_frozen_across_resubmit(session,completed_run,users):
 """归档只固化当次批准结论；后续撤回→重提→再批准产生新复核，旧归档内容不变。"""
 first=_approve(session,_review(session,completed_run,users["analyst"]),users["admin"],1)
 report,_=report_service.create(session,ReportCreate(review_id=first.id,title="首版归档"))
 snapshot_action=report.snapshot["action"];snapshot_version=report.snapshot["review_version"]
 # 已批准复核不允许撤回/驳回，归档引用稳定
 with pytest.raises(HTTPException):
  review_service.decide(session,first,ReviewDecision(expected_version=1),_U(users["analyst"]),"withdraw")
 # 同一运行的后续复核轮次（新行）独立批准归档，互不覆盖
 second=review_service.create(session,
  ReviewCreate(run_id=completed_run,action=ACTION_B),_U(users["analyst"]))
 second=review_service.decide(session,second,ReviewDecision(expected_version=1,comment="同意二版"),
  _U(users["admin"]),"approve")
 report_two,_=report_service.create(session,ReportCreate(review_id=second.id,title="二版归档"))
 # 旧归档快照保持首版内容
 again=session.get(Report,report.id)
 assert again.snapshot["action"]==snapshot_action
 assert again.snapshot["review_version"]==snapshot_version==1
 assert report_two.id!=report.id
 assert report_two.snapshot["action"]==ACTION_B and report_two.snapshot["review_version"]==1

def test_snapshot_immutable_when_run_result_changes(session,completed_run,users):
 row=_approve(session,_review(session,completed_run,users["analyst"]),users["admin"],1)
 report,_=report_service.create(session,ReportCreate(review_id=row.id,title="快照冻结"))
 frozen_cost=report.snapshot["result"]["lp"]["nominal_cost"]
 run=session.get(BlendRun,completed_run)
 run.result={**run.result,"lp":{**run.result["lp"],"nominal_cost":9999.0}}
 session.commit()
 refreshed=session.get(Report,report.id)
 assert refreshed.snapshot["result"]["lp"]["nominal_cost"]==frozen_cost!=9999.0

def test_legacy_snapshot_without_new_fields_still_exports(session,completed_run,users):
 """旧版归档快照只有 result/action/reviewer 三个键，导出与页面读取必须兼容。"""
 row=_approve(session,_review(session,completed_run,users["analyst"]),users["admin"],1)
 run=session.get(BlendRun,completed_run)
 legacy=Report(id="report-legacy",review_id=row.id,title="历史旧归档",
  snapshot={"result":run.result,"action":row.action,"reviewer":users["admin"]})
 session.add(legacy);session.commit()
 csv_text=report_service.export(legacy)
 assert "material_id" in csv_text and "北杉针叶浆" in csv_text
 samples=report_service.export(legacy,samples=True)
 assert "quality_comparison_tolerance" in samples
 loaded=session.get(Report,"report-legacy")
 assert loaded.snapshot["action"]==row.action
 # 新字段缺失时导出不依赖它们
 assert "review_version" not in loaded.snapshot
