
import sys
from datetime import datetime
 
from dotenv import load_dotenv
 
from gemini_client import TIME_LIMIT_SECONDS, GeminiTimeLimitError, ask_gemini, make_client
 
load_dotenv()               # reads GEMINI_API_KEY from .env
 
MODEL =  "gemini-3.5-flash-lite"  # free-tier model
 
client = make_client()
 
# Read the prompt from a file, e.g.  python main.py prompt2.txt
if len(sys.argv) < 2:
    sys.exit("Please give a prompt file, e.g.  python main.py prompt1.txt")
prompt_file = sys.argv[1]
with open(prompt_file, encoding="utf-8") as f:
    prompt = f.read()
 
try:
    response = ask_gemini(client, MODEL, prompt)
except GeminiTimeLimitError:
    sys.exit(f"Gemini didn't answer within {TIME_LIMIT_SECONDS} seconds (retries included). Try again in a moment.")
# any other error (503 with no time left, 429 quota, bad key) is shown normally
 
answer = response.output_text
 
print(answer)
 
# Save the prompt and answer to results.md
with open("results.md", "a", encoding="utf-8") as f:
    f.write(f"\n\n## {prompt_file} ({datetime.now():%Y-%m-%d %H:%M})\n")
    f.write(f"**Model:** {MODEL}\n\n**Prompt:**\n\n```\n{prompt}\n```\n\n**Response:**\n\n{answer}\n")