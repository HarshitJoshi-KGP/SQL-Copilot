"""
SQL Analytics Co-pilot — Streamlit Dashboard
Natural language → SQL → Results → Chart → Explanation → Follow-ups
"""
import os
import sys
import time
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schema_extractor import SchemaExtractor
from data.seed_db import seed as seed_db

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="SQL Co-pilot", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500&display=swap');
:root {
    --orange:#ff8c32; --green:#4ade80; --blue:#60a5fa;
    --bg:#08080e; --surface:rgba(255,255,255,0.04);
    --border:rgba(255,255,255,0.09); --text:#e0dbd2; --muted:#666;
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:var(--text);}
.stApp{background:var(--bg);}
#MainMenu,footer{visibility:hidden;}
header{visibility:hidden;}
header button,header [data-testid]{visibility:visible !important;display:flex !important;}
[data-testid="stSidebarCollapseButton"]{visibility:visible !important;}
[data-testid="stSidebarCollapseButton"] button{visibility:visible !important;display:flex !important;}
[data-testid="collapsedControl"]{visibility:visible !important;display:flex !important;}
[data-testid="collapsedControl"] button{visibility:visible !important;display:flex !important;}
.block-container{padding:1.2rem 2.5rem;}

/* Cards */
.metric-card{background:var(--surface);border:1px solid var(--border);
    border-radius:12px;padding:1rem 1.2rem;text-align:center;}
.metric-val{font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;color:var(--orange);}
.metric-lbl{font-family:'DM Mono',monospace;font-size:0.57rem;
    letter-spacing:0.16em;color:var(--muted);text-transform:uppercase;margin-top:3px;}

/* SQL box */
.sql-box{background:rgba(0,0,0,0.4);border:1px solid var(--border);border-left:3px solid var(--orange);
    border-radius:10px;padding:1rem 1.2rem;font-family:'DM Mono',monospace;
    font-size:0.82rem;color:#e0dbd2;white-space:pre-wrap;margin:0.5rem 0;}

/* Explanation */
.explain-box{background:rgba(255,140,50,0.06);border:1px solid rgba(255,140,50,0.2);
    border-radius:10px;padding:1rem 1.2rem;font-size:0.9rem;line-height:1.65;}

/* Attempt badge */
.attempt-badge{font-family:'DM Mono',monospace;font-size:0.62rem;
    padding:0.2rem 0.6rem;border-radius:20px;letter-spacing:0.08em;}
.att-1{background:rgba(74,222,128,0.12);color:#4ade80;border:1px solid rgba(74,222,128,0.25);}
.att-2{background:rgba(255,200,50,0.12);color:#fcd34d;border:1px solid rgba(255,200,50,0.25);}
.att-3{background:rgba(248,113,113,0.12);color:#f87171;border:1px solid rgba(248,113,113,0.25);}

/* Followup chips */
.followup-chip{display:inline-block;background:var(--surface);border:1px solid var(--border);
    border-radius:20px;padding:0.3rem 0.8rem;font-size:0.78rem;margin:0.25rem;
    cursor:pointer;transition:all 0.2s;}
.followup-chip:hover{border-color:var(--orange);color:var(--orange);}

/* Cache badge */
.cache-hit{font-family:'DM Mono',monospace;font-size:0.58rem;color:#60a5fa;
    border:1px solid rgba(96,165,250,0.3);border-radius:20px;padding:0.15rem 0.5rem;}

h1,h2,h3{font-family:'Syne',sans-serif !important;}
.stButton>button{background:var(--orange)!important;border:none!important;
    color:#080404!important;font-family:'Syne',sans-serif!important;
    font-weight:700!important;border-radius:10px!important;height:2.8rem!important;}
.stTextInput input,.stTextArea textarea{background:var(--surface)!important;
    border-color:var(--border)!important;color:var(--text)!important;
    font-size:0.95rem!important;}
.stSelectbox>div>div{background:var(--surface)!important;border-color:var(--border)!important;}
.stFileUploader{background:var(--surface)!important;border-color:var(--border)!important;}
[data-testid="collapsedControl"]{visibility:visible !important;display:flex !important;}
[data-testid="stSidebar"]{transform:none !important;margin-left:0 !important;}
</style>
""", unsafe_allow_html=True)


# ── DB setup ───────────────────────────────────────────────────────────────────
DB_PATH = str(Path(__file__).parent.parent / "data" / "ecommerce.db")
if not Path(DB_PATH).exists():
    seed_db()

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("history", []), ("current_result", None), ("db_path", DB_PATH)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 SQL Co-pilot")

    groq_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", None)
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

    if not groq_key:
        st.error("❌ GROQ_API_KEY not found in .env or Streamlit secrets")

    # DB selector
    st.markdown("**Database**")
    db_option = st.radio("Source", ["Demo E-commerce DB", "Upload your own CSV", "Upload SQLite DB"])

    if db_option == "Upload your own CSV":
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded:
            df_upload = pd.read_csv(uploaded)
            tmp_db = "/tmp/uploaded.db"
            conn = sqlite3.connect(tmp_db)
            table_name = Path(uploaded.name).stem.replace("-","_").replace(" ","_")
            df_upload.to_sql(table_name, conn, if_exists="replace", index=False)
            conn.close()
            st.session_state.db_path = tmp_db
            st.success(f"✅ Loaded `{table_name}` ({len(df_upload)} rows)")

    elif db_option == "Upload SQLite DB":
        uploaded = st.file_uploader("Upload .db file", type=["db","sqlite","sqlite3"])
        if uploaded:
            tmp_db = f"/tmp/{uploaded.name}"
            with open(tmp_db, "wb") as f:
                f.write(uploaded.read())
            st.session_state.db_path = tmp_db
            st.success(f"✅ Loaded {uploaded.name}")

    st.markdown("---")

    # Schema viewer
    st.markdown("**Schema**")
    try:
        extractor = SchemaExtractor(st.session_state.db_path)
        tables = extractor.get_table_names()
        for t in tables:
            st.markdown(f"📋 `{t}`")
    except Exception:
        pass

    st.markdown("---")

    # History
    if st.session_state.history:
        st.markdown("**Recent Queries**")
        for h in st.session_state.history[-5:][::-1]:
            st.markdown(f"<div style='font-size:0.72rem;color:var(--muted);padding:0.3rem 0;border-bottom:1px solid var(--border)'>{h['question'][:50]}…</div>", unsafe_allow_html=True)

        if st.button("Clear History"):
            st.session_state.history = []
            st.rerun()

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown("# SQL Analytics Co-pilot")
st.markdown("<div style='color:var(--muted);margin-bottom:1.5rem;'>Ask questions in plain English. Get SQL, results, charts, and explanations.</div>", unsafe_allow_html=True)

# ── Quick question chips ──
DEMO_QUESTIONS = [
    "Which product category had the highest total revenue?",
    "Show me the top 10 customers by total spend",
    "What is the monthly revenue trend for this year?",
    "Which products have the highest average rating?",
    "How many orders were placed per city?",
    "What percentage of orders were cancelled?",
    "Show revenue breakdown by customer tier",
    "Which day of the week has the most orders?",
]

st.markdown("**Try these:**")
cols = st.columns(4)
for i, q in enumerate(DEMO_QUESTIONS):
    if cols[i % 4].button(q[:35]+"…" if len(q)>35 else q, key=f"chip_{i}",
                           use_container_width=True):
        st.session_state["question_input"] = q
        st.session_state["auto_run"] = True
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ── Input ──────────────────────────────────────────────────────────────────────
question = st.text_input(
    "Ask a question about your data",
    placeholder="e.g. Which product category had the highest revenue last quarter?",
    key="question_input"
)

run_col, _ = st.columns([2, 8])
run_btn = run_col.button("▶ Run Query", use_container_width=True)

# ── Execute ────────────────────────────────────────────────────────────────────
auto_run = st.session_state.pop("auto_run", False)
if (run_btn or auto_run) and question.strip():
    from core.copilot import SQLCopilot
    copilot = SQLCopilot(st.session_state.db_path)

    with st.spinner("Thinking..."):
        try:
            start = time.time()
            result = copilot.run(question)
            elapsed = round(time.time() - start, 2)

            st.success("SQLCopilot returned successfully.")

        except Exception as e:
            st.exception(e)
            st.stop()

    result["question"] = question
    result["elapsed"] = elapsed
    st.session_state.current_result = result
    st.session_state.history.append(result)
    st.rerun()

# ── Display results ─────────────────────────────────────────────────────────────
res = st.session_state.current_result
if res:
    st.markdown("---")

    # Header row
    h1, h2, h3 = st.columns([6, 2, 2])
    h1.markdown(f"### 💬 {res['question']}")

    att = res.get("attempts", 1)
    att_cls = f"att-{min(att, 3)}"
    att_label = f"✅ 1st try" if att == 1 else f"🔄 {att} attempts"
    h2.markdown(f'<div style="text-align:right;padding-top:0.6rem"><span class="attempt-badge {att_cls}">{att_label}</span></div>', unsafe_allow_html=True)

    if res.get("from_cache"):
        h3.markdown('<div style="text-align:right;padding-top:0.6rem"><span class="cache-hit">⚡ CACHED</span></div>', unsafe_allow_html=True)
    else:
        h3.markdown(f'<div style="text-align:right;padding-top:0.6rem;font-family:\'DM Mono\';font-size:0.58rem;color:var(--muted)">{res.get("elapsed","?")}s</div>', unsafe_allow_html=True)

    if res.get("error"):
        st.error(res["error"])
        st.markdown(f"**Last SQL attempted:**")
        st.markdown(f'<div class="sql-box">{res["sql"]}</div>', unsafe_allow_html=True)
    else:
        # ── SQL ──
        with st.expander("🔍 View Generated SQL", expanded=False):
            st.markdown(f'<div class="sql-box">{res["sql"]}</div>', unsafe_allow_html=True)
            st.button("📋 Copy SQL", key="copy_sql")

        # ── Explanation ──
        st.markdown(f'<div class="explain-box">💡 {res["explanation"]}</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Metrics ──
        m1, m2 = st.columns(2)
        m1.markdown(f"""<div class="metric-card">
            <div class="metric-val">{res['row_count']}</div>
            <div class="metric-lbl">Rows Returned</div></div>""", unsafe_allow_html=True)
        m2.markdown(f"""<div class="metric-card">
            <div class="metric-val">{len(res['columns'])}</div>
            <div class="metric-lbl">Columns</div></div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Chart + Table ──
        if res["columns"] and res["rows"]:
            df = pd.DataFrame(res["rows"], columns=res["columns"])
            chart_type = res.get("chart_type", "table")

            tab1, tab2 = st.tabs(["📊 Chart", "📋 Data Table"])

            with tab1:
                try:
                    if chart_type == "bar" and len(df.columns) >= 2:
                        x_col = df.columns[0]
                        y_col = next((c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])), df.columns[1])
                        fig = px.bar(df, x=x_col, y=y_col,
                                     color_discrete_sequence=["#ff8c32"])
                        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                          paper_bgcolor="rgba(0,0,0,0)",
                                          font=dict(color="#e0dbd2"))
                        st.plotly_chart(fig, use_container_width=True)

                    elif chart_type == "line" and len(df.columns) >= 2:
                        x_col = df.columns[0]
                        y_col = next((c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])), df.columns[1])
                        fig = px.line(df, x=x_col, y=y_col,
                                      color_discrete_sequence=["#ff8c32"],
                                      markers=True)
                        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                          paper_bgcolor="rgba(0,0,0,0)",
                                          font=dict(color="#e0dbd2"))
                        st.plotly_chart(fig, use_container_width=True)

                    elif chart_type == "pie" and len(df.columns) >= 2:
                        label_col = df.columns[0]
                        value_col = next((c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])), df.columns[1])
                        fig = px.pie(df, names=label_col, values=value_col,
                                     color_discrete_sequence=px.colors.sequential.Oranges_r)
                        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                                          font=dict(color="#e0dbd2"))
                        st.plotly_chart(fig, use_container_width=True)

                    elif chart_type == "scatter" and len(df.columns) >= 2:
                        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                        if len(num_cols) >= 2:
                            fig = px.scatter(df, x=num_cols[0], y=num_cols[1],
                                             color_discrete_sequence=["#ff8c32"])
                            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                                              paper_bgcolor="rgba(0,0,0,0)",
                                              font=dict(color="#e0dbd2"))
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.dataframe(df, use_container_width=True)
                    else:
                        st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.warning(f"Chart render issue: {e}")
                    st.dataframe(df, use_container_width=True)

            with tab2:
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False)
                st.download_button("⬇ Download CSV", csv, "results.csv", "text/csv")

        # ── Follow-up questions ──
        if res.get("followups"):
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**You might also want to ask:**")
            fq_cols = st.columns(len(res["followups"]))
            for i, fq in enumerate(res["followups"]):
                if fq_cols[i].button(fq, key=f"fq_{i}_{fq[:10]}",
                                      use_container_width=True):
                    st.session_state["prefill"] = fq
                    st.rerun()

# ── Eval benchmark section ─────────────────────────────────────────────────────
with st.expander("🧪 Run Evaluation Benchmark (30 queries)"):
    st.markdown("""
    This runs a 30-query benchmark across 3 difficulty levels and measures:
    - **Execution accuracy** — did the SQL run without error?
    - **Self-correction rate** — how often did the retry loop save a failed query?
    """)

    BENCHMARK = {
        "easy": [
            "How many customers are there in total?",
            "What is the average product price?",
            "How many orders have status 'completed'?",
            "List all product categories",
            "What is the total number of reviews?",
            "How many customers are in the gold tier?",
            "What is the most expensive product?",
            "How many products are in the Electronics category?",
            "What is the total revenue from all completed orders?",
            "How many orders were placed in total?",
        ],
        "medium": [
            "Which city has the most customers?",
            "What is the average order value by customer tier?",
            "Which product category has the most orders?",
            "Show the top 5 products by total quantity sold",
            "What percentage of orders were cancelled?",
            "Which customers placed more than 5 orders?",
            "What is the average rating per product category?",
            "How many new customers signed up each month this year?",
            "What is the revenue contribution of each category?",
            "Which tier has the highest average order value?",
        ],
        "hard": [
            "What is the 3-month rolling average revenue?",
            "Which customers have bought from more than 3 different categories?",
            "Find products that have never been ordered",
            "What is the repeat purchase rate by customer tier?",
            "Show the revenue rank of each product within its category",
            "Which customers spent more than the average customer spend?",
            "What is the day-of-week revenue breakdown?",
            "Find the top customer in each city by total spend",
            "What is the correlation between product price and average rating?",
            "Show cumulative revenue over time",
        ],
    }

    if st.button("▶ Start Benchmark") and groq_key:
        from core.copilot import SQLCopilot
        copilot = SQLCopilot(st.session_state.db_path)

        results_data = []
        total = sum(len(v) for v in BENCHMARK.values())
        bar = st.progress(0)
        status_txt = st.empty()
        done = 0

        for difficulty, questions in BENCHMARK.items():
            for q in questions:
                status_txt.markdown(f"Running: *{q[:60]}…*")
                r = copilot.run(q)
                results_data.append({
                    "difficulty": difficulty,
                    "question": q,
                    "success": r["error"] is None,
                    "attempts": r["attempts"],
                    "rows": r["row_count"],
                })
                done += 1
                bar.progress(done / total)

        status_txt.empty()
        df_bench = pd.DataFrame(results_data)

        # Summary
        total_q    = len(df_bench)
        successful = df_bench["success"].sum()
        exec_acc   = successful / total_q * 100
        multi_att  = df_bench[df_bench["attempts"] > 1]
        rescue_rate = (multi_att["success"].sum() / max(len(multi_att), 1)) * 100

        b1, b2, b3 = st.columns(3)
        b1.metric("Execution Accuracy", f"{exec_acc:.1f}%")
        b2.metric("Self-correction Rescue Rate", f"{rescue_rate:.1f}%")
        b3.metric("Avg Attempts", f"{df_bench['attempts'].mean():.2f}")

        # Per-difficulty breakdown
        st.dataframe(
            df_bench.groupby("difficulty").agg(
                accuracy=("success", "mean"),
                avg_attempts=("attempts", "mean"),
                total=("success", "count")
            ).round(3),
            use_container_width=True
        )
        st.dataframe(df_bench, use_container_width=True)

    elif not groq_key:
        st.info("Add your Groq API key in the sidebar to run the benchmark.")
