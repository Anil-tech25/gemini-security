"""Gemini Code Review Lab - a small web interface for the Gemini experiments.

Run with:  streamlit run app.py
"""
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai

load_dotenv()  # reads GEMINI_API_KEY from .env

MODEL = "gemini-3.8-flash"  # free-tier model
SAVED_FILE = Path("saved_reviews.json")

# Synthetic example code. It is only sent to Gemini as text, never executed.
SAMPLES = {
    "01 · A user lookup": '''import sqlite3

def get_user(username):
    conn = sqlite3.connect("users.db")
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    return conn.execute(query).fetchall()
''',
    "02 · The same lookup, fixed": '''import sqlite3
from contextlib import closing

def get_user(username):
    with closing(sqlite3.connect("users.db")) as conn:
        query = "SELECT * FROM users WHERE name = ?"
        return conn.execute(query, (username,)).fetchall()
''',
    "03 · A ping helper": '''import subprocess

def ping(host):
    # host comes from a web form
    result = subprocess.run("ping -c 1 " + host, shell=True,
                            capture_output=True, text=True)
    return result.stdout
''',
    "04 · A file download": '''import os
from flask import Flask, request, send_file

app = Flask(__name__)
BASE_DIR = "/srv/files"

@app.route("/download")
def download():
    name = request.args.get("file")
    return send_file(os.path.join(BASE_DIR, name))
''',
}

DEFAULT_QUESTION = "What security problems does this code have, and how should they be fixed?"


def build_prompt(code, context, question):
    parts = [
        "You are reviewing code for security problems. The code is text only; do not assume it has been run.",
    ]
    if context.strip():
        parts.append(f"What the reviewer knows about this code:\n{context.strip()}")
    parts.append(f"Code:\n```\n{code}\n```")
    parts.append(f"Question: {question.strip() or DEFAULT_QUESTION}")
    return "\n\n".join(parts)


def load_saved():
    try:
        return json.loads(SAVED_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_review(sample, review):
    saved = load_saved()
    saved[sample] = review
    SAVED_FILE.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")


st.set_page_config(page_title="Gemini Code Review Lab", layout="wide")
st.title("Gemini Code Review Lab")
st.caption(f"Model: {MODEL}. Pick some code, give the reviewer context, ask a question, and check the answer.")

# ---------- 01 / Experiment ----------
st.header("01 / Experiment")
sample = st.radio("Choose a starting point", list(SAMPLES), horizontal=True)

code = st.text_area(
    "Source code (editable, never executed)",
    value=SAMPLES[sample],
    height=240,
    key=f"code_{sample}",
)
context = st.text_area(
    "What does the reviewer know?",
    placeholder="e.g. This runs in a public web app. 'username' comes straight from a login form.",
    key=f"context_{sample}",
)
question = st.text_input("Review question", value=DEFAULT_QUESTION, key=f"question_{sample}")
st.caption("Try a different question or context, then compare the answers.")

st.warning("A live review sends these fields to Google. Use synthetic, non-sensitive code.")

col1, col2 = st.columns(2)
run_review = col1.button("Review with Gemini", type="primary", use_container_width=True)
load_demo = col2.button("Load saved demo", use_container_width=True)

if run_review:
    prompt = build_prompt(code, context, question)
    try:
        with st.spinner("Asking Gemini..."):
            client = genai.Client()
            response = client.interactions.create(model=MODEL, input=prompt)
            answer = response.output_text
        review = {
            "time": f"{datetime.now():%Y-%m-%d %H:%M}",
            "model": MODEL,
            "context": context,
            "question": question,
            "prompt": prompt,
            "answer": answer,
        }
        save_review(sample, review)
        st.session_state.result = {**review, "source": "live"}
    except Exception as e:  # e.g. 503 high demand, 429 quota, bad key
        st.error(
            f"The Gemini call failed: {e}\n\n"
            "If it says high demand (503) or quota (429), wait a bit and try again, "
            "or click 'Load saved demo'."
        )

if load_demo:
    saved = load_saved().get(sample)
    if saved:
        st.session_state.result = {**saved, "source": "saved"}
    else:
        st.info("No saved review for this example yet. Run a live review once and it will be saved.")

# ---------- 02 / Evidence ----------
st.header("02 / Evidence")
result = st.session_state.get("result")
if result:
    label = "Live review" if result["source"] == "live" else f"Saved review from {result['time']}"
    st.subheader(f"The model's review ({label})")
    st.caption(f"Model: {result['model']}  |  Question: {result['question']}")
    if result.get("context"):
        st.caption(f"Context given: {result['context']}")
    st.markdown(result["answer"])
    with st.expander("Show the exact prompt that was sent"):
        st.code(result["prompt"])
    st.info("Now check it: what did Gemini get right, what did it miss, and what did it claim without evidence?")
else:
    st.write("Run a review or load a saved demo to see Gemini's answer here.")
