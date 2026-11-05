"""Call Gemini with one time limit that covers every attempt, retries included.
 
Used by both main.py and app.py.
"""
import time
 
import httpx
from google import genai
 
TIME_LIMIT_SECONDS = 120      # the longest the user waits in total, retries included
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}  # quota and "high demand" style errors
FIRST_RETRY_DELAY_SECONDS = 1  # doubles after each retry: 1, 2, 4, ...
MIN_ATTEMPT_SECONDS = 10      # don't start a new attempt with less time than this left
 
 
class GeminiTimeLimitError(Exception):
    """Gemini didn't answer within TIME_LIMIT_SECONDS."""
 
 
def make_client(**client_options):
    """A Gemini client with the SDK's automatic retries turned off.
 
    By default the SDK retries client.interactions calls up to 3 times and
    gives each attempt the full timeout, so the user could wait several times
    longer than the limit. ask_gemini() does the retrying instead, so it can
    stop at TIME_LIMIT_SECONDS.
 
    The documented switch, HttpRetryOptions(attempts=1), still allows one retry
    for interactions in google-genai 2.28.0 (and attempts=0 is changed to 1),
    so this turns retries off on the interactions config directly.
 
    client_options are passed to genai.Client (the test uses this to plug in a fake Gemini).
    """
    client = genai.Client(**client_options)
    config = client.interactions.sdk_configuration
    if not hasattr(config, "retry_config"):
        raise RuntimeError("google-genai changed how retries are set; update make_client()")
    config.retry_config = None  # None = no automatic retries
    return client
 
 
def ask_gemini(client, model, prompt):
    """Send the prompt, retrying 429/5xx errors until TIME_LIMIT_SECONDS runs out.
 
    Raises GeminiTimeLimitError if no answer arrives in time. Any other error
    (bad key, a 503 with no time left to retry, ...) is raised as it is.
    """
    deadline = time.monotonic() + TIME_LIMIT_SECONDS
    delay = FIRST_RETRY_DELAY_SECONDS
    while True:
        time_left = deadline - time.monotonic()
        try:
            # Each attempt only gets the time that is left, not a fresh 120 seconds.
            return client.interactions.create(model=model, input=prompt, timeout=time_left)
        except Exception as error:
            if is_timeout(error):
                raise GeminiTimeLimitError() from error
            if getattr(error, "status_code", None) not in RETRY_STATUS_CODES:
                raise
            time_left = deadline - time.monotonic()
            if time_left - delay < MIN_ATTEMPT_SECONDS:
                raise  # not enough time for another try: show the real error
            time.sleep(delay)
            delay *= 2
 
 
def is_timeout(error):
    """True if this error, or an error that caused it, was a timeout.
 
    The SDK wraps the httpx timeout in its own APITimeoutError, which isn't
    exported publicly, so this checks the error and what caused it.
    """
    while error is not None:
        if isinstance(error, httpx.TimeoutException) or "Timeout" in type(error).__name__:
            return True
        error = error.__cause__ or error.__context__
    return False