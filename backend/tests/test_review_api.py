"""HTTP 层：路由、角色权限、过期页面失败与完整处理记录呈现。"""
import pytest

def _review_payload(action="HTTP 流程复核说明：覆盖提审、驳回、重提与批准的完整链路。"):
 return {"run_id":"run-test","action":action}

def test_auth_required(client,completed_run):
 assert client.post("/reviews",json=_review_payload()).status_code==401
 assert client.get("/reviews").status_code==401

def test_role_permissions(client,auth,completed_run):
 analyst=auth("analyst");admin=auth("admin");viewer=auth("viewer")
 # viewer 不能提审
 assert client.post("/reviews",json=_review_payload(),headers=viewer).status_code==403
 r=client.post("/reviews",json=_review_payload(),headers=analyst)
 assert r.status_code==201
 review_id=r.json()["id"]
 # analyst 不能批准/驳回
 assert client.post(f"/reviews/{review_id}/approve",
  json={"expected_version":1},headers=analyst).status_code==403
 assert client.post(f"/reviews/{review_id}/reject",
  json={"expected_version":1,"comment":"x"},headers=analyst).status_code==403
 # viewer 任何写操作 403
 assert client.post(f"/reviews/{review_id}/withdraw",
  json={"expected_version":1},headers=viewer).status_code==403
 # admin 不能替人撤回（撤回属于提交方写权限，但 admin 也是 write_user —— 允许管理员撤回）
 r2=client.post(f"/reviews/{review_id}/withdraw",
  json={"expected_version":1},headers=admin)
 assert r2.status_code==200 and r2.json()["state"]=="withdrawn"

def test_full_http_flow_and_stale_page(client,auth,completed_run):
 analyst=auth("analyst");admin=auth("admin");viewer=auth("viewer")
 r=client.post("/reviews",json=_review_payload(),headers=analyst)
 assert r.status_code==201
 review=r.json();rid=review["id"];assert review["version"]==1
 assert review["events"][0]["action"]=="submit"
 # 驳回不带意见 → 422
 assert client.post(f"/reviews/{rid}/reject",
  json={"expected_version":1,"comment":""},headers=admin).status_code==422
 # 正常驳回
 assert client.post(f"/reviews/{rid}/reject",
  json={"expected_version":1,"comment":"结论依据不足，请修正"},headers=admin).status_code==200
 # 过期页面：仍带 version=1 做任何决定都失败
 stale=client.post(f"/reviews/{rid}/approve",
  json={"expected_version":1},headers=admin)
 assert stale.status_code==409 and "失效" in stale.json()["detail"]
 # 非终态可重提
 r=client.post(f"/reviews/{rid}/resubmit",
  json={"action":"重提说明：已按驳回意见修正结论，长度满足校验。"},headers=analyst)
 assert r.status_code==201 and r.json()["version"]==2 and r.json()["state"]=="submitted"
 # 旧版本号批准 → 明确失败
 stale2=client.post(f"/reviews/{rid}/approve",
  json={"expected_version":1},headers=admin)
 assert stale2.status_code==409 and "过期" in stale2.json()["detail"]
 # 新版本号批准成功
 ok=client.post(f"/reviews/{rid}/approve",
  json={"expected_version":2,"comment":"同意"},headers=admin)
 assert ok.status_code==200 and ok.json()["state"]=="approved"
 # 处理记录完整
 events=client.get(f"/reviews/{rid}/events",headers=analyst).json()
 assert [e["action"] for e in events]==["submit","reject","resubmit","approve"]
 assert {e["actor"] for e in events}>={ "analyst@pulp.demo","admin@pulp.demo"}
 listing=client.get("/reviews",headers=viewer).json()
 item=next(x for x in listing if x["id"]==rid)
 assert len(item["events"])==4 and item["reviewer"]=="admin@pulp.demo"
 # 已批准后再操作 → 409
 again=client.post(f"/reviews/{rid}/withdraw",
  json={"expected_version":2},headers=analyst)
 assert again.status_code==409

def test_ownership_enforced_for_withdraw_and_resubmit(client,auth,completed_run,session):
 from src.models.user import User
 from src.utils.security import hash_password
 if session.get(User,"user-analyst2") is None:
  session.add(User(id="user-analyst2",email="analyst2@pulp.demo",role="analyst",
   password_hash=hash_password("PulpDemo2026!")));session.commit()
 analyst=auth("analyst");other=auth("analyst2")
 rid=client.post("/reviews",json=_review_payload(),headers=analyst).json()["id"]
 # 其他分析师不能撤回
 assert client.post(f"/reviews/{rid}/withdraw",
  json={"expected_version":1},headers=other).status_code==403
 # 提交人本人撤回成功
 assert client.post(f"/reviews/{rid}/withdraw",
  json={"expected_version":1},headers=analyst).status_code==200
 # 非提交人不能重提
 assert client.post(f"/reviews/{rid}/resubmit",
  json={"action":"他人尝试重提的复核说明，长度满足校验。"},headers=other).status_code==403

def test_archive_http_rules(client,auth,completed_run):
 analyst=auth("analyst");admin=auth("admin");viewer=auth("viewer")
 rid=client.post("/reviews",json=_review_payload(),headers=analyst).json()["id"]
 # 未批准不能归档
 assert client.post("/reports",json={"review_id":rid,"title":"待归档底稿"},headers=admin).status_code==409
 # analyst 不能归档
 assert client.post(f"/reviews/{rid}/approve",
  json={"expected_version":1},headers=admin).status_code==200
 assert client.post("/reports",json={"review_id":rid,"title":"待归档底稿"},headers=analyst).status_code==403
 r1=client.post("/reports",json={"review_id":rid,"title":"正式归档"},headers=admin)
 assert r1.status_code==201
 # 重复归档返回同一份（已存在，200）
 r2=client.post("/reports",json={"review_id":rid,"title":"再归档一次"},headers=admin)
 assert r2.status_code==200 and r1.json()["id"]==r2.json()["id"]
 assert r2.json()["title"]=="正式归档"
 # viewer 可下载
 rep_id=r1.json()["id"]
 assert client.get(f"/reports/{rep_id}/csv",headers=viewer).status_code==200
 assert client.get(f"/reports/{rep_id}/samples.csv",headers=viewer).status_code==200
