from O365 import Account
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Environment variables
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
credentials = (CLIENT_ID, CLIENT_SECRET)

account = Account(credentials)
if account.authenticate(scopes=['basic', 'message_all']):
   print('Authenticated!')

mailbox = account.mailbox()
query = mailbox.new_query().order_by("receivedDateTime", ascending=False)
messages = mailbox.inbox_folder().get_messages(query=query, limit=1)

for message in messages:
   print(f"dir(message) = {dir(message)}")
