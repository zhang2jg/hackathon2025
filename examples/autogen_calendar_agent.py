from autogen import ConversableAgent
from dotenv import load_dotenv
from datetime import datetime
import os


load_dotenv(dotenv_path="../.env")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

config_list = [{"model": "gpt-4o",
                "api_key": GITHUB_TOKEN,
                "base_url": "https://models.inference.ai.azure.com"}]

def read_llm_response(filename: str) -> str:
    """
    Read the response from a file.
    """
    with open(filename, 'r') as file:
        return file.read()

def create_calendar_event(
    subject: str,
    start_date: str,
    end_date: str,
    description: str
) -> str:
    """
    Create a calendar event.
    """
    return f"""
Subject: '{subject}'
Start_date: {start_date}
End_date: {end_date}
Description: {description}
"""


# Let's first define the assistant agent that suggests tool calls.
assistant = ConversableAgent(
    name="Assistant",
    system_message="You are a helpful AI assistant. "
    "You can help with parsing out all upcoming events from the provided text. "
    "Then create calendar events for each of them. "
    "Return 'TERMINATE' when the task is done.",
    llm_config={"config_list": config_list},
)

# The user proxy agent is used for interacting with the assistant agent
# and executes tool calls.
user_proxy = ConversableAgent(
    name="User",
    llm_config=False,
    is_termination_msg=lambda msg: msg.get("content") is not None and "TERMINATE" in msg["content"],
    human_input_mode="NEVER",
)

# Register the tool signature with the assistant agent.
assistant.register_for_llm(name="create_calendar_event", description="Create calendar event")(create_calendar_event)

# Register the tool function with the user proxy agent.
user_proxy.register_for_execution(name="create_calendar_event")(create_calendar_event)


if __name__ == "__main__":
    llm_doc = read_llm_response("../emails/Fwd_Mrs_Judge_s_Second_Grade_llm.txt")
    chat_result = user_proxy.initiate_chat(assistant,
                                           message="Please create calendar events for all upcoming events found in below document.\n"
                                                   "######### Document START #########\n"
                                                   f"{llm_doc}")
    print(chat_result)
    print(chat_result.cost)


