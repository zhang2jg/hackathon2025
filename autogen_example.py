import autogen
#
# llm_config = {"config_list": [{
#     "model": "gpt-3.5-turbo"
# }]}

llm_config_local = {"config_list": [{
    "model": "gpt-4o",
    "api_key": "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",
    "base_url": "https://models.inference.ai.azure.com"
}]}

bob = autogen.AssistantAgent(
    name="Bob",
    system_message=""""
      You love telling jokes. After Alice feedback improve the joke. 
      Say 'TERMINATE' when you have improved the joke.
    """,
    llm_config=llm_config_local
)

alice = autogen.AssistantAgent(
    name="Alice",
    system_message="Criticise the joke.",
    llm_config=llm_config_local
)

def termination_message(msg):
    return "TERMINATE" in str(msg.get("content", ""))

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    code_execution_config={"use_docker": False},
    is_termination_msg=termination_message,
    human_input_mode="NEVER"
)

groupchat = autogen.GroupChat(
    agents=[bob, alice, user_proxy],
    speaker_selection_method="round_robin",
    messages=[]
)

manager = autogen.GroupChatManager(
    groupchat=groupchat,
    code_execution_config={"use_docker": False},
    llm_config=llm_config_local,
    is_termination_msg=termination_message
)

user_proxy.initiate_chat(
    manager,
    message="Tell a joke"
)