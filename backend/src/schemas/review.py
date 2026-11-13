from pydantic import BaseModel,Field
class ReviewCreate(BaseModel):
 run_id:str
 action:str=Field(min_length=8,max_length=3000)
class ReviewResubmit(BaseModel):
 action:str=Field(min_length=8,max_length=3000)
class ReviewDecision(BaseModel):
 # 前端页面持有的版本号；过期页面（版本已变）明确失败
 expected_version:int=Field(ge=1)
 comment:str=Field(default="",max_length=3000)
