from pydantic import BaseModel, Field

class UserLLMQueryRequest(BaseModel):
    query:str = Field(..., description="user query for companion bot", min_length=10)