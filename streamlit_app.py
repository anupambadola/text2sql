import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8001")

st.set_page_config(page_title="QueryGuard", page_icon="Q", layout="wide")
st.title("QueryGuard")
st.caption("Ask your analytics database a question. Every query is checked before it runs.")

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Try a question")
    examples = [
        "How many heads of the departments are older than 56?",
        "List the creation year, name and budget of each department.",
        "What are the names of the states where at least 3 heads were born?",
    ]
    selected = st.selectbox("Examples", examples)
    question = st.text_area("Natural-language question", value=selected, height=100)
    run = st.button("Run query", type="primary", use_container_width=True)
    st.divider()
    st.subheader("Guardrails")
    st.caption(f"API: {API_URL}")
    st.write("SELECT-only execution")
    st.write("Automatic row limit")
    st.write("Confidence and validation signals")

if run:
    with st.spinner("Generating, checking, and executing..."):
        try:
            response = requests.post(f"{API_URL}/v1/query", json={"question": question}, timeout=180)
        except requests.RequestException as exc:
            if isinstance(exc, requests.Timeout):
                st.error(f"The query timed out after 180 seconds. The API or model is still processing the request.")
            else:
                st.error(f"The API is unavailable at {API_URL}. Start Uvicorn with app.main:app. Details: {exc}")
        else:
            if response.ok:
                result = response.json()
                st.session_state.history.insert(0, result)
            else:
                st.error(f"API error ({response.status_code}): {response.text}")

if st.session_state.history:
    result = st.session_state.history[0]
    if result["blocked"]:
        st.error("Query blocked by guardrails")
    else:
        left, right = st.columns([2, 1])
        with left:
            st.subheader("Answer")
            st.dataframe(pd.DataFrame(result["rows"]), use_container_width=True, hide_index=True)
            st.caption(f"{result['row_count']} rows | {result['execution_ms']} ms")
        with right:
            st.metric("Confidence", f"{result['confidence']:.0%}")
            st.caption(f"SQL source: {result.get('provider', 'unknown')} | RAG examples used as context: {result.get('retrieved_examples', 0)}")
            st.subheader("Signal breakdown")
            for name, value in result["confidence_breakdown"].items():
                st.progress(value, text=f"{name.replace('_', ' ').title()}: {value:.0%}")
        st.subheader("Generated SQL")
        st.code(result["sql"], language="sql")
        st.info(result["explanation"])
        st.subheader("Was this SQL correct?")
        corrected_sql = st.text_area(
            "Correct SQL (optional)",
            value=result["sql"],
            key=f"corrected-sql-{result['query_id']}",
            height=140,
        )
        if st.button("Save corrected SQL to RAG", key=f"save-correction-{result['query_id']}", use_container_width=True):
            try:
                feedback_response = requests.post(
                    f"{API_URL}/v1/feedback",
                    json={"query_id": result["query_id"], "correct": False, "corrected_sql": corrected_sql, "question": result["question"], "original_sql": result["sql"]},
                    timeout=30,
                )
                print(f"Feedback response: {feedback_response.status_code} {feedback_response.text}")
                if feedback_response.ok:
                    feedback_result = feedback_response.json()
                    if feedback_result.get("correction_saved"):
                        st.success(feedback_result.get("message", "Corrected SQL saved to RAG."))
                    else:
                        st.error(feedback_result.get("message", "Corrected SQL was not saved."))
                else:
                    st.error(f"API error ({feedback_response.status_code}): {feedback_response.text}")
            except requests.RequestException as exc:
                print(f"Feedback request failed: {exc}")
                st.error(f"Could not submit correction to {API_URL}: {exc}")
        feedback_left, feedback_right = st.columns(2)
        with feedback_left:
            if st.button("Thumbs up", key=f"feedback-up-{result['query_id']}", use_container_width=True):
                feedback_response = requests.post(f"{API_URL}/v1/feedback", json={"query_id": result["query_id"], "correct": True, "question": result["question"], "original_sql": result["sql"]}, timeout=10)
                if feedback_response.ok:
                    st.success("Thanks, this SQL was marked correct.")
                else:
                    st.error(feedback_response.text)
        with feedback_right:
            if st.button("Thumbs down", key=f"feedback-down-{result['query_id']}", use_container_width=True):
                feedback_response = requests.post(f"{API_URL}/v1/feedback", json={"query_id": result["query_id"], "correct": False, "question": result["question"], "original_sql": result["sql"]}, timeout=10)
                if feedback_response.ok:
                    feedback_result = feedback_response.json()
                    st.warning(feedback_result.get("message", "Original SQL was marked incorrect. Edit it and use Save corrected SQL to RAG if needed."))
                else:
                    st.error(f"API error ({feedback_response.status_code}): {feedback_response.text}")
        for warning in result["guardrail_warnings"]:
            st.warning(warning)
        for note in result["validation_notes"]:
            st.caption(note)
else:
    st.info("Enter a question in the sidebar to see a guarded SQL result.")
