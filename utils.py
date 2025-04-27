import easyocr
from pdf2image import convert_from_path
from openai import OpenAI
import numpy as np
from pydantic import BaseModel
from datetime import datetime
from auth import outlook_account


class CalendarEvent(BaseModel):
    subject: str
    body: str
    start_date: str = None
    end_date: str = None
    remind_before_minutes: int = 30


def create_calendar_event(event: CalendarEvent) -> str:
    """
    Create a calendar event.
    """
    # Access the calendar
    schedule = outlook_account.schedule()
    calendar = schedule.get_default_calendar()

    # Create a new event
    new_event = calendar.new_event()
    new_event.subject = event.subject
    new_event.body = event.body
    new_event.remind_before_minutes = event.remind_before_minutes
    new_event.start = datetime.fromisoformat(event.start_date)
    if event.end_date:
        new_event.end = datetime.fromisoformat(event.end_date)

    # Save the event
    new_event_saved = new_event.save()
    if new_event_saved:
        return f"Event created successfully. Subject: {event.subject}"
    else:
        return f"Event failed to create. Subject: {event.subject}"


# def create_calendar_event(
#     subject: str,
#     start_date: str,
#     end_date: str,
#     description: str
# ) -> str:
#     """
#     Create a calendar event.
#     """
#     return f"""
# Subject: '{subject}'
# Start_date: {start_date}
# End_date: {end_date}
# Description: {description}
# """

def ocr_pdf(pdf_path, lang_list=['en']):
    # Convert PDF pages to images
    pages = convert_from_path(pdf_path)

    reader = easyocr.Reader(lang_list)
    full_text = ""

    for i, page in enumerate(pages):
        # PIL Image to numpy array
        image = page
        result = reader.readtext(np.array(image), detail=0, paragraph=True)
        page_text = "\n".join(result)
        full_text += f"--- Page {i + 1} ---\n{page_text}\n\n"
    return full_text


def run_llm(text, token=None):
    endpoint = "https://models.inference.ai.azure.com"
    model_name = "gpt-4.1"

    client = OpenAI(
        base_url=endpoint,
        api_key=token,
    )

    prompt_template = """
    Please summarize the school letter and provide a list of important points. In addition, extract all 
    upcoming events as a list of dictionaries with the following keys:
    - subject: subject of the event
    - start_date: the start datetime of the event, e.g. "2025-04-22T09:00:00"
    - end_date: the end datetime of the event, e.g. "2025-04-22T09:00:00". If none, use start_date + 1 hour.
    - description: details of the event.
    Default to use 2025 as the year for all events if not specified.
    Body of school letter is as follows:
    {}
    """

    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant who helps students and parents understand the school letter.",
            },
            {
                "role": "user",
                "content": prompt_template.format(text),
            }
        ],
        temperature=0.3,
        top_p=1.0,
        max_tokens=2000,
        model=model_name
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    import sys
    import numpy as np

    if len(sys.argv) != 2:
        print("Usage: python extract_pdf_text.py yourfile.pdf")
        sys.exit(1)

    pdf_file = sys.argv[1]
    text = ocr_pdf(pdf_file)
    print(text)