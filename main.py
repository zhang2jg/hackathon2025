import os
from fastapi import FastAPI, Request, File, UploadFile, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from O365 import Account, FileSystemTokenBackend
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import re
import os
import subprocess
from pathlib import Path

from agents.calendar_agent import call_calendar_agent
from utils import ocr_pdf, run_llm, CalendarEvent, create_calendar_event
from agents import calendar_agent
from auth import outlook_account

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Load environment variables from .env file
load_dotenv()

# Environment variables
# CLIENT_ID = os.getenv("CLIENT_ID")
# CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
# TOKEN_FILENAME = os.getenv("TOKEN_FILENAME", "o365_tokens")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SCOPES = ['Mail.Read', 'Calendars.ReadWrite']  # Adjust the scopes as per your needs
wkhtmltopdf_path = "/mnt/c/tmp/wkhtmltopdf/bin/wkhtmltopdf.exe"

# Initialize FastAPI
app = FastAPI()

# # Configure the O365 Account with FirestoreTokenBackend (or customize it)
# token_backend = None
# if TOKEN_FILENAME:
#     token_backend = FileSystemTokenBackend(token_path='./tokens', token_filename=TOKEN_FILENAME)
#
# account = Account((CLIENT_ID, CLIENT_SECRET), token_backend=token_backend)

account = outlook_account

def run_powershell_command(command):
    """Executes a PowerShell command and returns the output."""
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return process.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
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
async def get_emails():
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
        download_path = Path("emails")  # Directory to save attachments
        download_path.mkdir(exist_ok=True)  # Create folder if it doesn't exist

        for message in messages:
            # print(f"dir(message) = {dir(message)}")
            email_data = {
                "subject": message.subject,
                "sender": message.sender.address if message.sender else None,
                "received": message.received.strftime('%Y-%m-%d %H:%M:%S') if message.received else None,
                "body_preview": message.body_preview,
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

            # Save the email body to a html file
            html_file_path = os.path.join(download_path,
                                   re.sub(r'[^0-9a-zA-Z]+','_', message.subject).strip('_') + '.html')
            with open(html_file_path, "wb") as out_file:
                out_file.write(message.body.encode('utf-8'))

            # Convert the HTML file to PDF
            pdf_file_path = html_file_path.split(".html")[0] + '.pdf'
            if not Path(pdf_file_path).exists():
                command = [wkhtmltopdf_path, html_file_path, pdf_file_path]
                print(f"subprocess command: {command}")
                output = run_powershell_command(command)
                print(f"subprocess output: {output}")
            else:
                print(f"PDF file already exists: {pdf_file_path}. Skipping conversion.")

            # Run ocr to extract text from the pdf
            txt_file_path = html_file_path.split(".html")[0] + '.txt'
            if not Path(txt_file_path).exists():
                print("OCR in progress....")
                ocr_text = ocr_pdf(pdf_file_path)
                with open(txt_file_path, "w") as out_file:
                    out_file.write(ocr_text)
                print("OCR completed.")
            else:
                ocr_text = None
                print(f"Text file already exists: {txt_file_path}. Skipping OCR.")

            # Run the LLM to extract events
            llm_response_file_path = html_file_path.split(".html")[0] + '_llm.txt'
            if not Path(llm_response_file_path).exists():
                print("Running LLM to summarize letter and extract events....")
                if ocr_text is None:
                    with open(txt_file_path, "r") as in_file:
                        ocr_text = in_file.read()
                llm_response = run_llm(ocr_text, token=GITHUB_TOKEN)
                print(f"llm_response: {llm_response}")
                with open(llm_response_file_path, "w") as out_file:
                    out_file.write(llm_response)

            # Create calendar events and send self an email for summary.
            chat_result = call_calendar_agent(llm_response_file_path, config_list=[{"model": "gpt-4o",
                                                            "api_key": GITHUB_TOKEN,
                                                            "base_url": "https://models.inference.ai.azure.com"}])

        return f'Calendar events created for Subject: {email_data['subject']}.\n Summary:\n{chat_result.summary}'
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
async def create_event(event: CalendarEvent):
    """
    Create a new calendar event with the title 'hello world' on '2025-04-22'.
    Requires the 'Calendars.ReadWrite' permission scope.
    """
    if not account.is_authenticated:
        return RedirectResponse("/")  # Redirect to home if not authenticated

    # Create a new event
    msg = create_calendar_event(event=event)
    if 'failed' in msg:
        raise HTTPException(status_code=400, detail="Failed to create calendar event")
    return {"message": msg}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)