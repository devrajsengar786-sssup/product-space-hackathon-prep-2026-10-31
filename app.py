"""Pre-event environment check only. No competition functionality or API calls."""
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name('.env'))
st.set_page_config(page_title="Hackathon setup check", page_icon="✅")
st.title("Hackathon setup check")
st.success("Python and Streamlit are working.")
st.caption("Generic starter only. Begin competition development after kickoff.")
text = st.text_area("Type here, or test Wispr Flow dictation", "Hello, hackathon!")
if st.button("Test local interaction"):
    st.write(f"Local check passed: {len(text)} characters received.")
st.info("No AI requests are made by this app.")
st.caption("Free preparation mode: no paid services are connected. A real AI provider will be chosen after kickoff.")
st.write("API key configured:", "Yes" if os.getenv("OPENAI_API_KEY") else "No — optional for this check")
