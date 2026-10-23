"""Convenience runner script for the Streamlit dashboard."""
import sys
from streamlit.web import cli as stcli

if __name__ == "__main__":
    sys.argv = ["streamlit", "run", "frontend/dashboard.py"]
    sys.exit(stcli.main())
