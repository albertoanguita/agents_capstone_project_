import asyncio
import logging
import os

from google.adk import Runner
from google.adk.apps import App, ResumabilityConfig
from google.adk.plugins import LoggingPlugin
from google.adk.sessions import InMemorySessionService
from google.genai import types

import agents

APP_NAME = "app"  # Application
USER_ID = "user"  # User
SESSION = "session"  # Session

MODEL_NAME = "gemini-2.5-flash-lite"

# QUERY = """whole eggs,https://www.carrefour.es/huevos-m-campero-t-m-bandeja-6-uds/267570/es/4.59,6,4.59
# egg whites,https://www.carrefour.es/claras-de-huevo-liquidas-ecologico-mon-gelat-500-ml/115787/es/3.5,2,3.5
# spinach,https://www.mercadona.es/es/v/0,5,5"""
QUERY = "I am a 47 year old male, 1,85 meters tall and weigh 72 kg. I want to gain muscle without gaining any fat."

with open('GOOGLE_API_KEY') as f: GOOGLE_API_KEY = f.read()

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"


# Configure logging with DEBUG log level.
logging.basicConfig(
    filename="logger.log",
    level=logging.DEBUG,
    format="%(filename)s:%(lineno)s %(levelname)s:%(message)s",
)


def check_for_approval(events):
    """Check if events contain an approval request.

    Returns:
        dict with approval details or None
    """
    event = events[-1] # get the latest event
    if event.content and event.content.parts:
        for part in event.content.parts:
            if (part.function_call and part.function_call.name == "adk_request_confirmation"
            ):
                return {
                    "approval_id": part.function_call.id,
                    "invocation_id": event.invocation_id,
                }
    return None


def create_approval_response(approval_info, approved):
    """Create approval response message."""
    confirmation_response = types.FunctionResponse(
        id=approval_info["approval_id"],
        name="adk_request_confirmation",
        response={"confirmed": approved},
    )
    return types.Content(
        role="user", parts=[types.Part(function_response=confirmation_response)]
    )


def print_agent_response(events):
    """Print agent's text responses from events."""
    event = events[-1]
    # for event in events:
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.text:
                print(f"Agent > {part.text}")



async def run_app(runner_instance: Runner, session_service: InMemorySessionService, query: str):
    print("running shopper...")
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION)
    events = []
    query_content = types.Content(role="user", parts=[types.Part(text=query)])
    # -----------------------------------------------------------------------------------------------
    # -----------------------------------------------------------------------------------------------
    # STEP 1: Send initial request to the Agent. If num_containers > 5, the Agent returns the special `adk_request_confirmation` event
    async for event in runner_instance.run_async(
            user_id=USER_ID, session_id=SESSION, new_message=query_content
    ):
        events.append(event)
        approval_info = check_for_approval(events)

        if approval_info:
            print(f"⏸️  Pausing for approval...")
            user_input = input("Press Y/y for approving the order, else to reject\n")
            approved = True if user_input.upper() == "Y" else False
            print(f"User has approved: {approved}")

            # PATH A: Resume the agent by calling run_async() again with the approval decision
            async for event in runner_instance.run_async(
                    user_id=USER_ID,
                    session_id=SESSION,
                    new_message=create_approval_response(approval_info, approved),  # Send human decision here
                    invocation_id=approval_info["invocation_id"],  # Critical: same invocation_id tells ADK to RESUME
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            print(f"Agent > {part.text}")
        else:
            # PATH B: If the `adk_request_confirmation` is not present - no approval needed - order completed immediately.
            print_agent_response(events)


async def main():
    coordinator_agent = agents.get_coordinator_agent(MODEL_NAME)

    session_service = InMemorySessionService()  # for testing purposes. Switch to vertex to go in production

    meal_designer_app = App(
        name=APP_NAME,
        root_agent=coordinator_agent,
        resumability_config=ResumabilityConfig(is_resumable=True),
        plugins=[
            LoggingPlugin()
        ]
    )
    runner = Runner(
        app=meal_designer_app,
        session_service=session_service,
    )

    await run_app(runner, session_service, QUERY)


asyncio.run(main())
