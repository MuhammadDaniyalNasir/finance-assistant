from agent import setup_vector_store, retrieve_context, answer_query
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from agent import answer_query, run_agent

from dotenv import load_dotenv
load_dotenv() 
if __name__ == "__main__":

    # ── 8. Run a query ────────────────────────────────────────────────────────
    config = {"configurable": {"thread_id": "session-1"}}
    agent = answer_query()
    response = run_agent(query = " which bank offer least markup rate for car loan and also mention the interest rates of atleast 2 banks with their details mentioned in the documents ")
from pprint import pprint
print("\n=== Agent Response ===")
pprint(response)