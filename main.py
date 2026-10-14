import sys
from datetime import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv()               # reads GEMINI_API_KEY from .env
client = genai.Client()

MODEL = "gemini-3.8-flash"  # free-tier model

# Read the prompt from a file, e.g.  python main.py prompt2.txt
prompt_file = sys.argv[1]
with open(prompt_file, encoding="utf-8") as f:
    prompt = f.read()

response = client.interactions.create(model=MODEL, input=prompt)
answer = response.output_text

print(answer)

# Save the prompt and answer to results.md
with open("results.md", "a", encoding="utf-8") as f:
    f.write(f"\n\n## {prompt_file} ({datetime.now():%Y-%m-%d %H:%M})\n")
    f.write(f"**Model:** {MODEL}\n\n**Prompt:** {prompt}\n\n**Response:**\n\n{answer}\n")