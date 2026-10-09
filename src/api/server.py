from fastapi import FastAPI, Depends
from src.api.models import UserLLMQueryRequest
from src.api.dependency import get_graph
from src.config.settings import settings
from langchain.messages import HumanMessage
from langgraph.checkpoint.redis import RedisSaver
from langgraph.store.postgres import PostgresStore
from contextlib import asynccontextmanager
import uvicorn
import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Running database setup...")
    with RedisSaver.from_conn_string(settings.redis_url) as checkpointer, \
         PostgresStore.from_conn_string(settings.database_url) as store:
        checkpointer.setup()
        store.setup()
    print("Database setup complete!")
    
    yield 


app = FastAPI(title="Companion AI", lifespan=lifespan)



@app.post('/chat')
async def companion(userLLMQueryRequest:UserLLMQueryRequest, graph = Depends(get_graph)):
    session_id = userLLMQueryRequest.session_id or str(uuid.uuid4())
    configurable = {"thread_id": session_id}
    if userLLMQueryRequest.user_id:
        configurable["user_id"] = userLLMQueryRequest.user_id
    message = HumanMessage(userLLMQueryRequest.query)

    response = graph.invoke({"messages":[message]}, config={"configurable": configurable})
    return {"session_id":session_id,"user_id": userLLMQueryRequest.user_id, "response":response["messages"][-1].content}



if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host='127.0.0.1', reload=True, port=8001)