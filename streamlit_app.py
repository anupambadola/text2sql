import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

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
    st.write("SELECT-only execution")
    st.write("Automatic row limit")
    st.write("Confidence and validation signals")

if run:
    with st.spinner("Generating, checking, and executing..."):
        response = requests.post(f"{API_URL}/v1/query", json={"question": question}, timeout=30)
    if response.ok:
        result = response.json()
        st.session_state.history.insert(0, result)
    else:
        st.error(response.text)

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
            st.caption(f"Provider: {result.get('provider', 'fallback')} | Retrieved examples: {result.get('retrieved_examples', 0)}")
            st.subheader("Signal breakdown")
            for name, value in result["confidence_breakdown"].items():
                st.progress(value, text=f"{name.replace('_', ' ').title()}: {value:.0%}")
        st.subheader("Generated SQL")
        st.code(result["sql"], language="sql")
        st.info(result["explanation"])
        for warning in result["guardrail_warnings"]:
            st.warning(warning)
        for note in result["validation_notes"]:
            st.caption(note)
else:
    st.info("Enter a question in the sidebar to see a guarded SQL result.")
