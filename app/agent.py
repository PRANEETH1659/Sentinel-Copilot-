# THIS FILE IS THE PHASE-2 "BRAIN LOOP".
#
# Phase 1 (app/rag.py, answer_question) always does exactly ONE fixed step:
# search Elasticsearch, then answer. This file replaces that fixed step with
# a small loop: the model THINKS (decides which tool, if any, fits the
# question), then ACTS (the chosen tool actually runs), then goes back to
# THINK with the new information - looping until the model is ready to give
# a final answer instead of calling another tool.
#
#   think -----(picked a tool)-----> act
#     ^                               |
#     |                               |
#     +-------------------------------+
#     |
#   (no tool needed / has enough info)
#     |
#     v
#    END

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from . import config
from .tools import search_knowledge_base, search_logs

TOOLS = [search_knowledge_base, search_logs]

SYSTEM_PROMPT = SystemMessage(
    content="""You are a security operations assistant. You have two tools:
- search_knowledge_base: written runbooks, policies, and past incident reports.
- search_logs: recent/live system activity.

Use whichever tool(s) fit the question - you may use more than one if the
question needs it. Answer using ONLY what the tools return. If the tools
don't contain the answer, say so clearly instead of guessing. Mention which
source each fact came from."""
)

# bind_tools() is what turns a plain chat model into one that can see the
# tool descriptions above and choose between them (or choose none).
model = ChatOllama(model=config.CHAT_MODEL, base_url=config.OLLAMA_URL).bind_tools(
    TOOLS
)


def think(state: MessagesState):
    """Look at the conversation so far (original question + any tool
    results already gathered) and decide: call a tool, or answer now."""
    messages = [SYSTEM_PROMPT] + state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}


def did_model_pick_a_tool(state: MessagesState) -> str:
    """The fork in the loop: did the last 'think' step ask for a tool?"""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_chosen"
    return "no_tool"


graph = StateGraph(MessagesState)
graph.add_node("think", think)
graph.add_node("act", ToolNode(TOOLS))  # ToolNode runs whichever tool(s) the model asked for

graph.set_entry_point("think")
graph.add_conditional_edges(
    "think",
    did_model_pick_a_tool,
    {"tool_chosen": "act", "no_tool": END},
)
graph.add_edge("act", "think")  # after acting, always go back and think again

agent = graph.compile()


def ask_agent(question: str) -> dict:
    """Same shape as Phase 1's answer_question() - {"answer": ..., "sources":
    [...]} - so main.py and anyone calling the API don't need to change how
    they read the response."""
    result = agent.invoke({"messages": [("user", question)]})
    final_message = result["messages"][-1]

    # Walk the conversation and pull out which source(s) each tool that
    # actually fired used, so we can still report sources like Phase 1 did -
    # this needs a branch per tool, since each one reports its source
    # differently.
    sources = set()
    for msg in result["messages"]:
        tool_name = getattr(msg, "name", None)

        if tool_name == "search_knowledge_base":
            for line in msg.content.splitlines():
                if line.startswith("[Source: "):
                    sources.add(line[len("[Source: ") : -1])

        elif tool_name == "search_logs":
            if not msg.content.startswith("No log entries found"):
                sources.add("sample_logs/mock_logs.json")

    return {"answer": final_message.content, "sources": sorted(sources)}
