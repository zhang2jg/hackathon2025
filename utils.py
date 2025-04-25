import easyocr
from pdf2image import convert_from_path
from openai import OpenAI
import numpy as np


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