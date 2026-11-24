"""Shared storage engine: local SQLite by default, managed PostgreSQL when DATABASE_URL is configured."""
import os
from pathlib import Path
import streamlit as st
from sqlalchemy import create_engine

@st.cache_resource
def get_engine():
    url = ""
    try:
        url = st.secrets.get("DATABASE_URL", "") or ""
    except Exception:
        pass
    url = url or os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url:
        return create_engine(url, pool_pre_ping=True, pool_recycle=300)
    Path("data").mkdir(parents=True, exist_ok=True)
    return create_engine("sqlite:///data/nba_edge.db", connect_args={"check_same_thread":False}, pool_pre_ping=True)
