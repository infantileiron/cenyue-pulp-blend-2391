from sqlalchemy import String,Text,JSON,ForeignKey,Integer
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class FormulaReview(RecordMixin,Base):
 __tablename__="reviews"
 run_id:Mapped[str]=mapped_column(ForeignKey("runs.id"),index=True)
 action:Mapped[str]=mapped_column(Text)
 state:Mapped[str]=mapped_column(String(20),default="submitted")
 reviewer:Mapped[str]=mapped_column(String(160),default="")
 # 每次修改重提递增；批准/撤回/驳回的并发仲裁基于该版本号
 version:Mapped[int]=mapped_column(Integer,default=1)
 # 提交人（历史行可能为空）
 created_by:Mapped[str]=mapped_column(String(160),default="")
class ReviewEvent(RecordMixin,Base):
 __tablename__="review_events"
 review_id:Mapped[str]=mapped_column(ForeignKey("reviews.id"),index=True)
 action:Mapped[str]=mapped_column(String(20))
 from_state:Mapped[str]=mapped_column(String(20),default="")
 to_state:Mapped[str]=mapped_column(String(20),default="")
 actor:Mapped[str]=mapped_column(String(160),default="")
 comment:Mapped[str]=mapped_column(Text,default="")
 detail:Mapped[dict]=mapped_column(JSON,default=dict)
