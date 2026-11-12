# Test: Gemini says "busy" (503) first, then never answers.
# We check the user doesn't wait longer than the time limit.
# Uses a fake Gemini, so no internet or API key is needed.

import time
import httpx
from google.genai import types

import gemini_client
from gemini_client import GeminiTimeLimitError, ask_gemini, make_client

# Use a short 10-second limit so the test is quick (the real app uses 120)
LIMIT = 10
gemini_client.TIME_LIMIT_SECONDS = LIMIT
gemini_client.MIN_ATTEMPT_SECONDS = 2

attempts = 0  # counts how many times Gemini was called


# Fake Gemini: 1st call says "busy", 2nd call never answers
def fake_gemini(request):
    global attempts
    attempts += 1

    if attempts == 1:
        print("attempt 1: 503 high demand")
        return httpx.Response(503, json={"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})

    wait = request.extensions.get("timeout", {}).get("read") or LIMIT
    print(f"attempt {attempts}: no answer, timing out after {wait:.1f} s")
    time.sleep(wait)
    raise httpx.ReadTimeout("timed out", request=request)


# Connect our code to the fake Gemini
fake_http = httpx.Client(transport=httpx.MockTransport(fake_gemini))
client = make_client(api_key="fake-key", http_options=types.HttpOptions(httpx_client=fake_http))

# Run the test and time it
start = time.monotonic()
timed_out = False

try:
    ask_gemini(client, "gemini-3.8-flash", "hi")
except GeminiTimeLimitError:
    timed_out = True
    print("timeout message shown")

waited = time.monotonic() - start
print(f"user waited {waited:.1f} seconds (limit {LIMIT}), attempts: {attempts}")

# Check the results (the test stops with an error if any check fails)
assert timed_out, "The timeout error did not happen"
assert waited <= LIMIT + 1, "The user waited too long"
assert attempts == 2, "Gemini should be called exactly 2 times"

print("PASS")