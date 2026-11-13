import csv,io
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from ..models.review import FormulaReview
from ..models.run import BlendRun
from ..models.report import Report

def _snapshot(review,run):
 # 归档只固化当次已批准结论：版本、批准人、意见与当时运行结果，后续修改不影响本快照
 return {
  "result":run.result,
  "action":review.action,
  "reviewer":review.reviewer,
  "review_version":review.version,
  "review_state":review.state,
  "run_id":review.run_id,
  "review_id":review.id,
 }

def create(db,body):
 """归档；返回 (报告行, 是否本次新建)。并发重复归档由唯一约束兜底，统一返回同一份。"""
 review=db.scalar(select(FormulaReview).where(FormulaReview.id==body.review_id))
 if review is None:raise HTTPException(404,"复核记录不存在")
 if review.state!="approved":raise HTTPException(409,"报告须关联当次已批准的配方复核")
 # 唯一复核重复归档：返回同一份，不覆盖、不新建
 existing=db.scalar(select(Report).where(Report.review_id==review.id))
 if existing:return existing,False
 run=db.get(BlendRun,review.run_id)
 row=Report(id=str(uuid4()),review_id=review.id,title=body.title,snapshot=_snapshot(review,run))
 db.add(row)
 try:db.commit()
 except IntegrityError:
  # 并发归档撞上 review_id 唯一约束：回滚后返回先提交的同一份快照，不算本次新建
  db.rollback()
  again=db.scalar(select(Report).where(Report.review_id==review.id))
  if again:return again,False
  raise
 return row,True

def export(row,samples=False):
 result=row.snapshot["result"];lp=result["lp"];robust=result["robustness"];out=io.StringIO();writer=csv.writer(out)
 if samples:
  keys=["index","strength","whiteness","recycled","cost","compliant"];writer.writerow(keys+["quality_comparison_tolerance"])
  for sample in robust["samples"]:writer.writerow([sample[k] for k in keys]+[robust["comparison_tolerance"]])
 else:
  writer.writerow(["material_id","name","share","unit_cost_CNY_per_tonne","nominal_blend_cost","simulation_passed","simulation_n","simulation_rate","cost_p05","cost_p50","cost_p95","quality_comparison_tolerance"])
  for share in lp["shares"]:writer.writerow([share["material_id"],share["name"],share["share"],share["unit_cost"],lp["nominal_cost"],robust["passed"],robust["n_samples"],robust["compliance_rate"],robust["cost_p05"],robust["cost_p50"],robust["cost_p95"],robust["comparison_tolerance"]])
 return "﻿"+out.getvalue()
