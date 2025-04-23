import os
from fastapi import FastAPI, Request, File, UploadFile, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from O365 import Account, FileSystemTokenBackend
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import shutil
import os

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
        return RedirectResponse(request.url_for('get_user_info'))
    else:
        raise HTTPException(status_code=400, detail="Authentication failed")


@app.get("/me")
async def get_user_info():
    """Fetch and display user information."""
    if not account.is_authenticated:
        return RedirectResponse("/")  # Redirect to home if not authenticated

    # Fetch the user's profile
    me = account.connection.get("https://graph.microsoft.com/v1.0/me")  # Microsoft Graph `/me` endpoint
    if me.status_code == 200:
        user_info = me.json()
        return {
            "id": user_info.get("id"),
            "name": user_info.get("displayName"),
            "email": user_info.get("mail"),
            "jobTitle": user_info.get("jobTitle"),
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to fetch user information")

@app.get("/emails")
def get_emails():
    """
    Fetch email messages from the authenticated user's inbox and download attachments.
    """
    if not account.is_authenticated:
        return {"message": "User is not authenticated. Please login via /auth/login."}

    try:
        mailbox = account.mailbox()
        query = mailbox.new_query().order_by("receivedDateTime", ascending=False)
        messages = mailbox.inbox_folder().get_messages(query=query, limit=1)  # Get the latest 10 emails

        emails = []
        download_path = Path("attachments")  # Directory to save attachments
        download_path.mkdir(exist_ok=True)  # Create folder if it doesn't exist

        for message in messages:
            email_data = {
                "subject": message.subject,
                "sender": message.sender.address if message.sender else None,
                "received": message.received.strftime('%Y-%m-%d %H:%M:%S') if message.received else None,
                "has_attachments": message.has_attachments,
                "attachments_saved": [],
            }

            # Check if the email has attachments
            if message.has_attachments:
                attachments = message.attachments

                for attachment in attachments:
                    if attachment.is_file:  # Handle file attachments only
                        file_path = download_path / attachment.name
                        attachment.save_as(file_path)
                        email_data["attachments_saved"].append(str(file_path))

            emails.append(email_data)

        return {"emails": emails}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails or download attachments: {str(e)}")


@app.post("/upload-pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    # for testing, use curl -X POST "http://127.0.0.1:8000/upload-pdf/" -F "file=@example.pdf"
    # Check if the uploaded file is a PDF
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Specify the path to save the uploaded file
    uploaded_pdfs_path = Path("uploaded_pdfs")
    uploaded_pdfs_path.mkdir(exist_ok=True)
    file_path = os.path.join(uploaded_pdfs_path, file.filename)

    # Save the file to the local file system
    with open(file_path, "wb") as out_file:
        # Write the file in chunks to avoid memory issues with large files
        while content := await file.read(1024):  # Use async read
            out_file.write(content)

    return {"message": f"File '{file.filename}' uploaded successfully!", "path": file_path}

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