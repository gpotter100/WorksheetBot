import json
import os
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_community.tools import DuckDuckGoSearchResults  # requires `pip install -U ddgs`

# -------------------------------
# 1. Model + Prompt Setup
# -------------------------------
llm = ChatOpenAI(temperature=0)

# ✅ GarrettBot identity + date + scores + history
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are GarrettBot, a helpful AI assistant created by Garrett. "
               "Today’s date is {today}. Here are the current NFL scores:\n{scores}\n\n"
               "Conversation so far:\n{history}"),
    ("human", "{question}")
])

chain = prompt | llm

# -------------------------------
# 2. Persistence Helpers
# -------------------------------
chat_history_store = {}

def get_session_history(session_id: str):
    filename = f"{session_id}_history.json"
    if session_id not in chat_history_store:
        history = InMemoryChatMessageHistory()
        if os.path.exists(filename):
            with open(filename, "r") as f:
                content = f.read().strip()
                if content:
                    messages = json.loads(content)
                    # ✅ Only keep last 20 messages to avoid token overflow
                    for msg in messages[-20:]:
                        history.add_message(msg)
        chat_history_store[session_id] = history
    return chat_history_store[session_id]

def save_session_history(session_id: str):
    filename = f"{session_id}_history.json"
    history = chat_history_store[session_id]
    serialized = []
    for m in history.messages:
        if hasattr(m, "model_dump"):   # Pydantic v2 objects
            serialized.append(m.model_dump())
        elif hasattr(m, "dict"):       # Pydantic v1 objects
            serialized.append(m.dict())
        else:                          # Already a dict
            serialized.append(m)
    with open(filename, "w") as f:
        json.dump(serialized, f, indent=2)

# -------------------------------
# 2b. Helper to format scores
# -------------------------------
def format_scores(results, limit=5):
    """Turn search results into a clean bullet list, truncated to avoid overflow."""
    if not results:
        return "No live scores available."
    formatted = []
    for r in results[:limit]:  # ✅ only keep first 5 items
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        if title or snippet:
            formatted.append(f"- {title}: {snippet}")
    return "\n".join(formatted)

# -------------------------------
# 3. Wrap Chain with History
# -------------------------------
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="question",
    history_messages_key="history",
)

# -------------------------------
# 4. Interactive Loop
# -------------------------------
session_id = "abc123"
print("GarrettBot is ready — ask me anything! (type 'quit' to exit)")

search_tool = DuckDuckGoSearchResults()

while True:
    user_input = input("You: ")
    if user_input.lower() in ["quit", "exit"]:
        break

    # ✅ Inject current date dynamically
    today = datetime.now().strftime("%A, %B %d, %Y")

    # ✅ Fetch and format NFL scores
    try:
        search_results = search_tool.run("current NFL scores")
        scores = format_scores(search_results)
    except Exception as e:
        scores = f"Error fetching scores: {e}"

    response = chain_with_history.invoke(
        {"question": user_input, "today": today, "scores": scores},
        config={"configurable": {"session_id": session_id}}
    )
    print("GarrettBot:", response.content)
    save_session_history(session_id)