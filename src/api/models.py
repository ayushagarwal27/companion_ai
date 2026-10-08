from pydantic import BaseModel, Field

class UserLLMQueryRequest(BaseModel):
    query:str = Field(..., description="user query for companion bot", min_length=10)
    session_id:str|None = Field(default=None, description="existing session id to continue a conversation; omit to start a new one")
    user_id: str | None = Field(default=None, description="existing user id for a logged-in user; omit if anonymous")