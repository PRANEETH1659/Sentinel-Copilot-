from fastapi import FastAPI
from pydantic import BaseModel

from .agent import ask_agent
from .rag import answer_question

app = FastAPI(title="SentinelCopilot", version="0.2.0")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """Phase 1: always runs one fixed hybrid search, then answers."""
    return answer_question(req.question)


@app.post("/ask-agent", response_model=AskResponse)
def ask_agent_endpoint(req: AskRequest):
    """Phase 2: the model decides which tool(s) to use - knowledge base,
    logs, or both - possibly looping through more than one, before it
    answers."""
    return ask_agent(req.question)
