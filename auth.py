from dotenv import load_dotenv
import os
from O365 import Account, FileSystemTokenBackend


class OutlookAccount:
    load_dotenv()

    # Environment variables
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    TOKEN_FILENAME = os.getenv("TOKEN_FILENAME", "o365_tokens")

    # Configure the O365 Account with FirestoreTokenBackend (or customize it)
    token_backend = None
    if TOKEN_FILENAME:
        token_backend = FileSystemTokenBackend(token_path='./tokens', token_filename=TOKEN_FILENAME)

    account = Account((CLIENT_ID, CLIENT_SECRET), token_backend=token_backend)

outlook_account = OutlookAccount().account