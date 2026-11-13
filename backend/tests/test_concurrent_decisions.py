"""并发争抢：批准/撤回/驳回同时到达只接受一个结果，其余明确失败。

生产端仲裁由单条条件 UPDATE 完成（WHERE 限定 submitted + 版本号）：
无论 MySQL 行锁还是 SQLite 库锁，都只有一个事务能更新成功，rowcount=0 即 409。
"""
import threading
import pytest
from fastapi import HTTPException
from src.config.database import Session
from src.models.review import FormulaReview
from src.schemas.review import ReviewCreate,ReviewDecision,ReviewResubmit
from src.services import review_service

ACTION="并发争抢用复核说明，长度满足校验要求。"

class _U:
 def __init__(self,email):
  self.email=email
  self.role="admin" if email.startswith("admin@") else "analyst"

def _make_review(session,run_id,email):
 return review_service.create(session,ReviewCreate(run_id=run_id,action=ACTION),_U(email))

@pytest.mark.parametrize("winner,losers",[
 ("approve",("withdraw","reject")),
 ("withdraw",("approve","reject")),
 ("reject",("approve","withdraw")),
])
def test_concurrent_decisions_single_winner(session,completed_run,users,winner,losers):
 review_id=_make_review(session,completed_run,users["analyst"]).id
 session.close()
 barrier=threading.Barrier(len((winner,)+losers))
 outcomes={}
 def worker(decision,actor):
  comment="驳回必须给出具体修改意见。" if decision=="reject" else ""
  barrier.wait()
  try:
   with Session() as db:
    row=db.get(FormulaReview,review_id)
    review_service.decide(db,row,ReviewDecision(expected_version=1,comment=comment),_U(actor),decision)
   outcomes[decision]=("ok",None)
  except HTTPException as e:
   outcomes[decision]=("conflict",e.status_code)
  except Exception as e: # pragma: no cover - 争抢只允许 409，不允许其它异常
   outcomes[decision]=("error",repr(e))
 threads=[threading.Thread(target=worker,
  args=(winner,users["admin"] if winner!="withdraw" else users["analyst"]))]
 for d in losers:
  actor=users["analyst"] if d=="withdraw" else users["admin"]
  threads.append(threading.Thread(target=worker,args=(d,actor)))
 for t in threads:t.start()
 for t in threads:t.join(timeout=60)
 assert set(outcomes)=={winner,*losers}
 # 三个争抢只有一个成功，其余全部明确 409；先抢到锁者胜出（不预设线程顺序）
 ok=[d for d,v in outcomes.items() if v[0]=="ok"]
 conflicts=[d for d,v in outcomes.items() if v==("conflict",409)]
 assert len(ok)==1 and len(conflicts)==2,outcomes
 winning=ok[0]
 # 终态唯一，处理事件只记录成功的那一次
 with Session() as db:
  row=db.get(FormulaReview,review_id)
  assert row.state!="submitted"
  events=review_service._events(db,review_id)
  process_events=[e for e in events if e.action in ("approve","withdraw","reject")]
  assert len(process_events)==1 and process_events[0].action==winning

def test_stale_version_after_resubmit_is_rejected(session,completed_run,users):
 """旧页面拿着旧版本号在重提后操作，必须明确失败。"""
 row=_make_review(session,completed_run,users["analyst"])
 review_service.decide(session,row,ReviewDecision(expected_version=1,comment="需要修改"),
  _U(users["admin"]),"reject")
 review_service.resubmit(session,row,ReviewResubmit(action=ACTION+"重提"),_U(users["analyst"]))
 with pytest.raises(HTTPException) as exc:
  review_service.decide(session,row,ReviewDecision(expected_version=1),_U(users["admin"]),"approve")
 assert exc.value.status_code==409 and "过期" in exc.value.detail
