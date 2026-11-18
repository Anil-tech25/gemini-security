"""Security review agent built with Google ADK.

Run with:  python agent.py
Gemini uses list_files and read_file to look through sample_app/,
then writes a short security report.
"""
import asyncio
import os

from dotenv import load_dotenv
from google.adk.agents import Agent, RunConfig
from google.adk.runners import InMemoryRunner

from tools import list_files, read_file

load_dotenv()  # reads GEMINI_API_KEY from .env
os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))  # ADK looks for this name

MODEL = "gemini-3.5-flash-lite"  # free-tier model
MAX_LLM_CALLS = 8  # the most times we call Gemini, so the loop can't run forever

INSTRUCTION = """You review Python code for security problems.
Use list_files to see the files, then read_file to read them.
When code calls a function from another file, read that file too before you decide.
Only report problems you can see in the code. For each one, give the file name,
line number, the evidence and a fix.
End with three short parts: Findings, Files checked, and Limitations."""

agent = Agent(
    name="security_reviewer",
    model=MODEL,
    instruction=INSTRUCTION,
    tools=[list_files, read_file],
)


async def main():
    async with InMemoryRunner(agent=agent) as runner:
        await runner.run_debug(
            "Review sample_app for security problems. Start with app.py.",
            verbose=True,  # prints each tool request and result
            run_config=RunConfig(max_llm_calls=MAX_LLM_CALLS),
        )


if __name__ == "__main__":
    asyncio.run(main())