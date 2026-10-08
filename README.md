# gemini-security

First Gemini API experiment: testing how well an LLM reviews cybersecurity examples, such as insecure code, Windows security events and known vulnerabilities. For each experiment I wrote down what I expected, ran the prompt, and then checked what Gemini got right, what it missed, and what it claimed without evidence.

## Model

`gemini-3.8-flash` (free tier), called with the `google-genai` Python SDK.

## Setup (Windows)

```
git clone https://github.com/Anil-tech25/gemini-security.git
cd gemini-security
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a file named `.env` in the project folder containing your key:

```
GEMINI_API_KEY=your_key_here
```

Get a key from [Google AI Studio](https://aistudio.google.com/apikey). `.env` is listed in `.gitignore`, so the key is never committed.

## How to run

Pass a prompt file to the script:

```
python main.py prompt1.txt
```

The script reads the prompt from the file, sends it to Gemini, prints the response, and appends the model, prompt and response to `results.md`. Each run makes one API call, so run each prompt only once to save free-tier quota.

## Experiments

| # | Prompt file | Topic |
|---|---|---|
| 1 | `prompt1.txt` | Code review of a Python function with SQL injection |
| 2 | `prompt2.txt` | Windows Event ID 4625 (failed logon) |
| 3 | `prompt3.txt` | CVE-2021-44228 (Log4Shell) |

Full prompts, responses, expectations and assessments are in [results.md](results.md).

## Key findings

- **Experiment 1 (claim I checked):** Gemini correctly found the SQL injection and suggested parameterized queries. But it claimed that `with sqlite3.connect(...)` closes the connection. The Python sqlite3 documentation shows the context manager only commits or rolls back the transaction. So Gemini's "fixed" code still leaks the connection it warned about. The correct fix is `contextlib.closing()` or `conn.close()`.
- **Experiment 2:** The overall SOC guidance was good, but it said external RDP attacks appear as Logon Type 10. With Network Level Authentication, failed RDP logons usually appear as Type 3, so a rule based on this answer would miss attacks. It also left out related events such as 4740, 4771 and 4776.
- **Experiment 3:** The main facts (RCE, JNDI lookups, CVSS 10.0) were correct, but the patch history was simplified, and some claims (like "first observed in Minecraft") had no sources.

## Reflection

Gemini was mostly correct on the main security issues, but it sometimes sounded confident about details that were wrong, like saying `with sqlite3.connect()` closes the connection. I learned that I should always check its claims against official documentation before trusting them. I also ran into real problems, such as 503 "high demand" errors and forgetting to pass a prompt file, which showed me that working with an LLM API needs error handling.

## AI assistance

I used Claude (an AI assistant) to help troubleshoot Git and command-line errors, and to help draft and fact-check the assessments in `results.md` and parts of this README. My professor approved using Claude for this assignment. I reviewed and checked everything before submitting.
