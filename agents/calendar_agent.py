from autogen import ConversableAgent, ChatResult
from utils import create_calendar_event


def read_llm_response(filename: str) -> str:
    """
    Read the response from a file.
    """
    with open(filename, 'r') as file:
        return file.read()


def call_calendar_agent(llm_response_file: str, config_list: list) -> ChatResult:
    llm_response = read_llm_response(llm_response_file)

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

    # start the conversation
    chat_result = user_proxy.initiate_chat(assistant,
                                           message="Please create calendar events for all upcoming events found in below document.\n"
                                                   "######### Document START #########\n"
                                                   f"{llm_response}")
    return chat_result