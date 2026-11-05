"""Test: Gemini says 503 first, then never answers. How long does the user wait?
 
Uses a fake Gemini, so no internet or API key is needed.
Run with:  python test_timeout.py
"""
import time
 
import httpx
from google.genai import types
 
import gemini_client
from gemini_client import GeminiTimeLimitError, ask_gemini, make_client
 
LIMIT = 10  # seconds, short so the test is quick (the app uses 120)
gemini_client.TIME_LIMIT_SECONDS = LIMIT
gemini_client.MIN_ATTEMPT_SECONDS = 2
attempts = 0
 
 
def fake_gemini(request):
    global attempts
    attempts += 1
    if attempts == 1:
        print("attempt 1: 503 high demand")
        return httpx.Response(503, json={"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})
    # Wait as long as this attempt is allowed to wait, then time out
    wait = request.extensions.get("timeout", {}).get("read") or LIMIT
    print(f"attempt {attempts}: no answer, timing out after {wait:.1f} s")
    time.sleep(wait)
    raise httpx.ReadTimeout("timed out", request=request)
 
 
client = make_client(
    api_key="fake-key",
    http_options=types.HttpOptions(httpx_client=httpx.Client(transport=httpx.MockTransport(fake_gemini))),
)
 
start = time.monotonic()
try:
    ask_gemini(client, "gemini-3.8-flash", "hi")
except GeminiTimeLimitError:
    print("timeout message shown")
waited = time.monotonic() - start
 
print(f"user waited {waited:.1f} seconds (limit {LIMIT}), attempts: {attempts}")
print("PASS" if waited <= LIMIT + 1 and attempts == 2 else "FAIL")
 