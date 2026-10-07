from fastapi import FastAPI, Depends
from src.api.models import UserLLMQueryRequest
from src.api.dependency import get_graph
from langchain.messages import HumanMessage
import uvicorn
import uuid

app = FastAPI(title="Companion AI")

@app.post('/chat')
async def companion(userLLMQueryRequest:UserLLMQueryRequest, graph = Depends(get_graph)):
    session_id = userLLMQueryRequest.session_id or str(uuid.uuid4())
    config = {"configurable":{"thread_id":session_id}}
    message = HumanMessage(userLLMQueryRequest.query)
    response = graph.invoke({"messages":[message]}, config=config)
    return {"session_id":session_id, "response":response["messages"][-1].content}


if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host='127.0.0.1', reload=True, port=8001)