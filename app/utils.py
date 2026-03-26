from pathlib import Path
import streamlit as st

def load_css(file_name: str):
    base_path = Path(__file__).parent
    css_path = base_path / file_name

    with open(css_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

