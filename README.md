# gemini-security

First Gemini API experiment: testing how well an LLM reviews cybersecurity examples, such as insecure code, Windows security events and known vulnerabilities. For each experiment I wrote down what I expected, ran the prompt, and then checked what Gemini got right, what it missed, and what it claimed without evidence.

## Model

`gemini-3.8-flash` (free tier), called with the `google-genai` Python SDK.

## Requirements

- **Python 3.12 or newer** (the pinned `numpy` version in `requirements.txt` needs it). Check with `python --version` (Windows) or `python3 --version` (Linux/macOS).
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).

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

## Setup (Linux / macOS)

```bash
git clone https://github.com/Anil-tech25/gemini-security.git
cd gemini-security
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Ubuntu/Debian, if `venv` is missing, install it first with `sudo apt install python3-venv`.

Create the `.env` file with your key:

```bash
echo "GEMINI_API_KEY=your_key_here" > .env
```

On every system, `.env` is listed in `.gitignore`, so the key is never committed. Activate the virtual environment again (`venv\Scripts\activate` on Windows, `source venv/bin/activate` on Linux/macOS) each time you open a new terminal.

## How to run

Pass a prompt file to the script (use `python3` instead of `python` on Linux/macOS if needed):

```
python main.py prompt1.txt
```

The script reads the prompt from the file, sends it to Gemini, prints the response, and appends the model, prompt and response to `results.md`. Each run makes one API call, so run each prompt only once to save free-tier quota.

To use the web interface instead:

```
streamlit run app.py
```

The app opens at http://localhost:8501. Stop it with `Ctrl+C`.

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