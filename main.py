import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from O365 import Account, FileSystemTokenBackend
from dotenv import load_dotenv
from datetime import datetime

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load environment variables from .env file
load_dotenv()

# Environment variables
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
TOKEN_FILENAME = os.getenv("TOKEN_FILENAME", "o365_tokens")
SCOPES = ['Mail.Read', 'Calendars.ReadWrite']  # Adjust the scopes as per your needs

# Initialize FastAPI
app = FastAPI()

# Configure the O365 Account with FirestoreTokenBackend (or customize it)
token_backend = None
if TOKEN_FILENAME:
    token_backend = FileSystemTokenBackend(token_path='./tokens', token_filename=TOKEN_FILENAME)

account = Account((CLIENT_ID, CLIENT_SECRET), token_backend=token_backend)

@app.get("/")
async def index():
    return {"message": "Welcome! Visit /auth to authenticate with Microsoft 365"}

@app.get("/auth")
async def auth():
    """
    Step 1: Redirect user to the Microsoft OAuth authorization URL.
    """
    if not account.is_authenticated:  # Check if already authenticated
        auth_url, state = account.con.get_authorization_url(
            requested_scopes=SCOPES, redirect_uri=REDIRECT_URI
        )
        print(f"auth url: {auth_url}")
        app.state.auth_url = auth_url
        return RedirectResponse(auth_url)
    return {"message": "Already authenticated"}

@app.get("/auth/callback")
async def auth_callback(request: Request):
    """
    Step 2: Handle the callback from Microsoft OAuth and store the token.
    """
    # Extract the authorization response URL
    query_params = dict(request.query_params)
    print(f"query_params: {query_params}")
    if "code" not in query_params:
        raise HTTPException(status_code=400, detail="Code not found in query parameters")

    # Complete the authentication process by exchanging code for a token
    auth_url = str(request.url)
    print(f"auth_url: {auth_url}; type: {type(auth_url)}")
    # auth_url = getattr(app.state, "auth_url", None)
    if not auth_url:
        raise HTTPException(status_code=400, detail="Authorization URL not found")

    # Exchange the auth code for an access token
    result = account.con.request_token(
        authorization_url=auth_url,  # Pass the previously stored `auth_url`
        grant_type="authorization_code",
        code=query_params["code"],
        redirect_uri=REDIRECT_URI
    )

    if result:
        return RedirectResponse("http://localhost:8000/me")
    else:
        raise HTTPException(status_code=400, detail="Authentication failed")


@app.get("/me")
async def get_user_info():
    """Fetch and display user information."""
    if not account.is_authenticated:
        return RedirectResponse("/")  # Redirect to home if not authenticated

    # Fetch the user's profile
    me = account.connection.get("/me")  # Microsoft Graph `/me` endpoint
    if me.status_code == 200:
        user_info = me.json()
        return {
            "name": user_info.get("displayName"),
            "email": user_info.get("mail"),
            "jobTitle": user_info.get("jobTitle"),
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to fetch user information")

@app.get("/mail")
async def get_mail():
    """
    Example endpoint: Retrieve the user's mailbox messages.
    Requires the 'Mail.Read' permission scope.
    """
    if not account.is_authenticated:
        return RedirectResponse("/")  # Redirect to home if not authenticated

        # Access the mailbox
    mailbox = account.mailbox()

    # Fetch the first 10 messages in the inbox
    inbox = mailbox.inbox_folder()
    messages = inbox.get_messages(limit=2, download_attachments=False)  # Limit to 2

    # Parse and return the email data
    email_data = []
    for message in messages:
        email_data.append({
            "subject": message.subject,
            "sender": message.sender.address,
            "received": message.received.strftime("%Y-%m-%d %H:%M:%S"),
            "body": message.body
        })

    return {"emails": email_data}

@app.get("/calendar")
async def get_calendar():
    """
    Retrieve the user's calendar events.
    Requires the 'Calendars.ReadWrite' permission scope.
    """
    if not account.is_authenticated:
        return RedirectResponse("/")  # Redirect to home if not authenticated

    # Access the calendar
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()

    # Fetch events (e.g., for the next 7 days)
    query = calendar.new_query("start").greater_equal("2023-01-01T00:00:00Z")  # Adjust the date range as needed
    events = calendar.get_events(query=query, limit=10)  # Limit to 10 events

    # Parse and return the event data
    event_data = []
    for event in events:
        event_data.append({
            "subject": event.subject,
            "start": event.start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": event.end.strftime("%Y-%m-%d %H:%M:%S"),
            "location": event.location["displayName"] if event.location else "N/A",
            "organizer": event.organizer.address,
        })

    return {"events": event_data}

@app.post("/calendar/create")
async def create_event():
    """
    Create a new calendar event with the title 'hello world' on '2025-04-22'.
    Requires the 'Calendars.ReadWrite' permission scope.
    """
    if not account.is_authenticated:
        return RedirectResponse("/")  # Redirect to home if not authenticated

    # Access the calendar
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()

    # Create a new event
    new_event = calendar.new_event()
    new_event.subject = "hello world"
    new_event.start = datetime.fromisoformat("2025-04-22T09:00:00")  # Start time (adjust as needed)
    new_event.end = datetime.fromisoformat("2025-04-22T10:00:00")    # End time (adjust as needed)

    # Save the event
    if new_event.save():
        return {"message": "Event created successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to create event")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)