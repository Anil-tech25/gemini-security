import sys
from datetime import datetime

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()               # reads GEMINI_API_KEY from .env

MODEL = "gemini-3.8-flash"  # free-tier model
TIMEOUT_SECONDS = 120       # stop waiting for Gemini after this long

client = genai.Client(
    http_options=types.HttpOptions(timeout=int(TIMEOUT_SECONDS * 1000))  # in milliseconds
)


def is_timeout(error):
    """True if this error, or an error that caused it, was a timeout."""
    while error is not None:
        if isinstance(error, httpx.TimeoutException) or "Timeout" in type(error).__name__:
            return True
        error = error.__cause__ or error.__context__
    return False


# Read the prompt from a file, e.g.  python main.py prompt2.txt
prompt_file = sys.argv[1]
with open(prompt_file, encoding="utf-8") as f:
    prompt = f.read()

try:
    response = client.interactions.create(model=MODEL, input=prompt)
except Exception as e:
    if is_timeout(e):
        sys.exit(f"Gemini didn't answer within {TIMEOUT_SECONDS} seconds. Try again in a moment.")
    raise  # any other error is shown normally

answer = response.output_text

print(answer)

# Save the prompt and answer to results.md
with open("results.md", "a", encoding="utf-8") as f:
    f.write(f"\n\n## {prompt_file} ({datetime.now():%Y-%m-%d %H:%M})\n")
    f.write(f"**Model:** {MODEL}\n\n**Prompt:** {prompt}\n\n**Response:**\n\n{answer}\n")