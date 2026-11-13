from sqlalchemy import select
from ..services import report_service
from ..models.report import Report
from ..models.common import serialize
from .common import listing,require
def list_all(db):return listing(db,Report)
def detail(db,ident):return serialize(require(db,Report,ident))
def create(db,body):
 row,created=report_service.create(db,body)
 # 首次归档 201；重复（含并发撞唯一约束）归档返回同一份快照，200
 return serialize(row),(201 if created else 200)
def export(row,samples=False):return report_service.export(row,samples)
