import asyncio
import os

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search
from google.genai import types

# todo to file
GOOGLE_API_KEY = 'AIzaSyDy5NUexIC9ddB9_S_fpwMChWkaGoGRND4'


os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

print("✅ ADK components imported successfully.")



root_agent = Agent(
    name="helpful_assistant",
    model="gemini-2.5-flash-lite",
    description="A simple agent that can answer general questions.",
    instruction="You are a helpful assistant. Use Google Search for current info or if unsure.",
    tools=[google_search],
)

print("✅ Root Agent defined.")



runner = InMemoryRunner(agent=root_agent)

print("✅ Runner created.")

async def fun():
    print("Hello")
    await runner.run_debug("What is Agent Development Kit from Google? What languages is the SDK available in?")
    print("World")



asyncio.run(fun())


print("END")