"""Streamlit Dashboard for Mini AI Business Intelligence Assistant."""
import os
import sys
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go


st.markdown("""
    <style>
        .stDeployButton,
        [data-testid="stAppDeployButton"],
        [data-testid="stAppDeployButton"] button {
            display: none !important;
            visibility: hidden !important;
        }
    </style>
""", unsafe_allow_html=True)
# Add parent directory to path to enable standalone fallback if needed
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.config import settings
from app.llm_service import process_business_question
from app.database import get_db_connection

# Page configuration
st.set_page_config(
    page_title="Mini AI BI Assistant",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-left: 5px solid #2b5c8f;
        padding: 15px;
        border-radius: 6px;
        margin-bottom: 12px;
    }
    .query-box {
        background-color: #272822;
        color: #f8f8f2;
        padding: 12px;
        border-radius: 6px;
        font-family: monospace;
    }
    .badge-llm {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: bold;
    }
    .badge-fallback {
        background-color: #fff3e0;
        color: #e65100;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Backend API Helper
# -------------------------------------------------------------
API_URL = f"http://{settings.API_HOST}:{settings.API_PORT}"

def check_backend_health():
    try:
        resp = requests.get(f"{API_URL}/health", timeout=2)
        if resp.status_code == 200:
            return True, resp.json()
    except Exception:
        pass
    return False, None

def ask_backend(question: str):
    """Query the backend API, or fall back to in-process service if API is offline."""
    try:
        resp = requests.post(
            f"{API_URL}/ask",
            json={"question": question},
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"status": "error", "answer": f"API Error ({resp.status_code}): {resp.text}"}
    except requests.exceptions.ConnectionError:
        # Graceful fallback: run query directly via in-process service
        res = process_business_question(question)
        res["source"] += " (Direct in-process fallback)"
        return res
    except Exception as e:
        return {"status": "error", "answer": f"Request failed: {str(e)}"}

## -------------------------------------------------------------
# Sidebar: System Status
# -------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ System Status")
    is_online, health_data = check_backend_health()

    if is_online:
        st.success("🟢 Backend: Connected")
        st.caption(
            f"📊 Sales Records: {health_data.get('total_sales_records', 0)}"
        )
    else:
        st.warning("🟡 Backend Offline")
        st.caption("Using the available fallback processing mode.")

    st.divider()

# -------------------------------------------------------------
# Header
# -------------------------------------------------------------
st.title("💼 Mini AI Business Intelligence Assistant")
st.markdown(
    "Ask business questions in natural language and get answers "
    "supported by sales data and SQL queries."
)
# -------------------------------------------------------------
# Question Input Form
# -------------------------------------------------------------
question_input = st.text_input(
    "Enter your business question:",
    placeholder="e.g., What is the total revenue?",
    key="user_question_input"
)

submit_btn = st.button("Ask Assistant 🚀", type="primary")

# Execute query if user pressed button or selected chip
active_question = question_input.strip() if submit_btn else None

if active_question:
    with st.spinner("Analyzing sales data and verifying query..."):
        result = ask_backend(active_question)
    st.divider()
    
    # 1. Answer Card
    status_type = result.get("status", "success")
    answer_text = result.get("answer", "")
    source_label = result.get("source", "Unknown")
    confidence = result.get("confidence", 0.0)
    intent = result.get("intent", "UNKNOWN")
    chart_type = result.get("chart_type")
    figures = result.get("figures", {})
    table_data = result.get("supporting_table", [])
    sql_query = result.get("sql_query", "")
    
    if status_type == "success":
        st.subheader("📊 Business Intelligence Insight")
        
        # Display Narrative Answer
        st.info(f"**Insight:** {answer_text}")
        
        # Display Visualizations based on chart type
        if chart_type == "metric":
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total Net Revenue", f"₹{figures.get('total_revenue', 0):,.2f}")
            m_col2.metric("Completed Orders", f"{figures.get('completed_transactions', 0)}")
            m_col3.metric("Units Sold", f"{figures.get('total_units_sold', 0):,}")
            m_col4.metric("Avg Order Value (AOV)", f"₹{figures.get('average_order_value', 0):,.2f}")
            
        elif chart_type == "bar" and intent == "HIGHEST_REVENUE_PRODUCT":
            df_chart = pd.DataFrame(table_data)
            fig = px.bar(
                df_chart,
                x="product",
                y="revenue",
                color="category",
                text="revenue",
                title="Revenue by Product",
                labels={"revenue": "Net Revenue (₹)", "product": "Product"},
                template="plotly_white"
            )
            fig.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)
            
        elif chart_type == "bar" and intent == "HIGHEST_SALES_REGION":
            df_chart = pd.DataFrame(table_data)
            fig = px.bar(
                df_chart,
                x="region",
                y="revenue",
                color="region",
                text="revenue",
                title="Total Revenue by Geographic Region",
                labels={"revenue": "Net Revenue (₹)", "region": "Region"},
                template="plotly_white"
            )
            fig.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
        elif chart_type == "line" and intent == "MONTHLY_REVENUE_TREND":
            df_chart = pd.DataFrame(table_data)
            fig = px.line(
                df_chart,
                x="month",
                y="revenue",
                markers=True,
                title="Monthly Revenue Trend (2026-01 to 2026-06)",
                labels={"revenue": "Net Revenue (₹)", "month": "Month"},
                template="plotly_white"
            )
            fig.update_traces(line=dict(width=3, color='#1f77b4'), marker=dict(size=9))
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)
            
        elif chart_type == "comparison":
            c_col1, c_col2, c_col3 = st.columns(3)
            c_col1.metric(f"Month: {figures.get('month1')}", f"₹{figures.get('revenue1', 0):,.2f}")
            c_col2.metric(f"Month: {figures.get('month2')}", f"₹{figures.get('revenue2', 0):,.2f}")
            diff = figures.get('absolute_change', 0)
            pct = figures.get('percentage_change', 0)
            c_col3.metric(
                "Change",
                f"₹{abs(diff):,.2f}",
                delta=f"{pct:+.2f}%"
            )
            
        # Supporting Figures Table
        if table_data:
            with st.expander("📑 View Supporting Data Table", expanded=False):
                st.dataframe(pd.DataFrame(table_data), use_container_width=True)
                
        # Verified SQL Query Card
        with st.expander("🔍 Executed Read-Only SQL Query", expanded=True):
            st.code(sql_query, language="sql")
            st.caption("🔒 Validated against destructive operations (Read-Only SQLite connection).")
            
    else:
        st.warning("⚠️ Unsupported or Ambiguous Question")
        st.write(answer_text)
        st.caption(f"Source: {source_label}")
