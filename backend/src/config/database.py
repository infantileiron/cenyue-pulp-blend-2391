from sqlalchemy import create_engine,inspect,text,event
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from .settings import DATABASE_URL
class Base(DeclarativeBase): pass
engine=create_engine(DATABASE_URL,pool_pre_ping=True)
if engine.dialect.name=="sqlite":
 # 本地/测试用 SQLite：写锁等待与 WAL，让并发写事务排队而不是立即报 locked
 @event.listens_for(engine,"connect")
 def _sqlite_pragmas(dbapi_conn,_):
  cur=dbapi_conn.cursor()
  cur.execute("PRAGMA busy_timeout=30000")
  cur.execute("PRAGMA journal_mode=WAL")
  cur.close()
Session=sessionmaker(bind=engine,expire_on_commit=False)
def get_db():
 with Session() as db: yield db
def initialize():
 from .. import models
 Base.metadata.create_all(engine)
 upgrade_schema()
def upgrade_schema():
 """幂等补齐存量库：新列与新表只增不改不删，保留历史复核与旧归档。"""
 inspector=inspect(engine)
 tables=set(inspector.get_table_names())
 with engine.begin() as conn:
  if "reviews" in tables:
   columns={c["name"] for c in inspector.get_columns("reviews")}
   if "version" not in columns:
    conn.execute(text("ALTER TABLE reviews ADD COLUMN version INT NOT NULL DEFAULT 1"))
   if "created_by" not in columns:
    conn.execute(text("ALTER TABLE reviews ADD COLUMN created_by VARCHAR(160) NOT NULL DEFAULT ''"))
   indexes={i["name"] for i in inspector.get_indexes("reviews")}
   if "ix_reviews_run_id" not in indexes:
    conn.execute(text("CREATE INDEX ix_reviews_run_id ON reviews (run_id)"))
  # create_all 通常已建 review_events；此处兜底处理极旧元数据的库
  if "review_events" not in tables:
   conn.execute(text(
    "CREATE TABLE IF NOT EXISTS review_events ("
    "id VARCHAR(36) NOT NULL PRIMARY KEY,"
    "created_at DATETIME NOT NULL,"
    "review_id VARCHAR(36) NOT NULL,"
    "action VARCHAR(20) NOT NULL,"
    "from_state VARCHAR(20) NOT NULL DEFAULT '',"
    "to_state VARCHAR(20) NOT NULL DEFAULT '',"
    "actor VARCHAR(160) NOT NULL DEFAULT '',"
    "comment TEXT NOT NULL,"
    "detail JSON NOT NULL"
    ")"))
   conn.execute(text("CREATE INDEX ix_review_events_review_id ON review_events (review_id)"))
