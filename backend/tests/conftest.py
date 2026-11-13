import os
import tempfile

_tmp=tempfile.mkdtemp(prefix="pulp-test-")
os.environ.setdefault("DATABASE_URL",f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("REDIS_URL","redis://localhost:6379/0")
os.environ.setdefault("SEED_DEMO","false")
os.environ.setdefault("JWT_SECRET","test-secret")

import pytest
from fastapi.testclient import TestClient

from src.config.database import initialize,Session
from src.main import app
from src.models.user import User
from src.models.dataset import PulpDataset
from src.models.spec import QualitySpec
from src.models.scenario import BlendScenario
from src.models.run import BlendRun
from src.utils.security import hash_password

# 争抢仲裁由条件 UPDATE 保证（见 review_service.decide），SQLite 的 WAL/busy_timeout
# 已在 src.config.database 引擎层配置，并发写事务排队，先提交者唯一胜出。

PASSWORD="PulpDemo2026!"

def _sample_result():
 return {
  "dataset_name":"测试原浆","spec_name":"测试窗口","scenario_name":"测试情景",
  "spec":{},
  "lp":{"feasible":True,"nominal_cost":3210.5,"shares":[
   {"material_id":"P01","name":"北杉针叶浆","share":0.6,"unit_cost":5200,"min_share":0.0,"max_share":0.65},
   {"material_id":"P02","name":"南桉阔叶浆","share":0.4,"unit_cost":3900,"min_share":0.0,"max_share":0.7}],
   "qualities":[],"reason":""},
  "robustness":{"passed":398,"n_samples":400,"compliance_rate":0.995,
   "cost_p05":3150.0,"cost_p50":3210.5,"cost_p95":3280.0,"seed":20261112,
   "dimension_count":6,"perturb_cost":True,"comparison_tolerance":1e-7,
   "assumption":"线性混合模拟假设","samples":[
    {"index":1,"strength":72.1,"whiteness":81.2,"recycled":0.26,"cost":3205.0,"compliant":True},
    {"index":2,"strength":69.8,"whiteness":81.0,"recycled":0.25,"cost":3222.0,"compliant":False}]},
  "materials":[],"cost_unit":"CNY/tonne",
  "property_units":{"strength":"模拟强度指数","whiteness":"%","recycled":"fraction"}}

@pytest.fixture(scope="session",autouse=True)
def _schema():
 initialize()

@pytest.fixture(autouse=True)
def _clean_tables():
 """每个用例独立业务数据：清空除用户外的全部表（固定 ID 夹具可重复建数）。"""
 from src import models
 yield
 with Session() as db:
  for cls in (models.ReviewEvent,models.Report,models.FormulaReview,models.BlendRun,
   models.BlendScenario,models.QualitySpec,models.PulpDataset,models.Audit):
   db.query(cls).delete()
  db.commit()

@pytest.fixture()
def client():
 with TestClient(app) as c:
  yield c

@pytest.fixture()
def session():
 with Session() as db:
  yield db

@pytest.fixture()
def users(session):
 out={}
 for role in ("admin","analyst","viewer"):
  email=f"{role}@pulp.demo"
  row=session.get(User,f"user-{role}")
  if row is None:
   row=User(id=f"user-{role}",email=email,role=role,password_hash=hash_password(PASSWORD))
   session.add(row)
  out[role]=email
 session.commit()
 return out

@pytest.fixture()
def completed_run(session,users):
 row=session.get(BlendRun,"run-test")
 if row is None:
  session.add(PulpDataset(id="ds-test",name="测试原浆",materials=[],description=""))
  session.add(QualitySpec(id="spec-test",name="测试窗口",strength_min=70,strength_max=100,
   whiteness_min=80,whiteness_max=100,recycled_min=.25,recycled_max=1,description=""))
  session.add(BlendScenario(id="sc-test",name="测试情景",dataset_id="ds-test",
   spec_id="spec-test",n_samples=400,seed=20261112,perturb_cost=True))
  row=BlendRun(id="run-test",scenario_id="sc-test",status="completed",
   result=_sample_result(),error="")
  session.add(row);session.commit()
 return row.id

@pytest.fixture()
def auth(client):
 def _login(role):
  r=client.post("/auth/login",json={"email":f"{role}@pulp.demo","password":PASSWORD})
  assert r.status_code==200,r.text
  return {"Authorization":f"Bearer {r.json()['token']}"}
 return _login
