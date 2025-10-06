#!/usr/bin/env python3
"""
PatchPro Trace Viewer

Streamlit app for viewing and analyzing patch generation traces.
Visualizes LLM interactions, failures, and performance metrics.

Usage:
    streamlit run trace_viewer.py

Or with custom trace directory:
    streamlit run trace_viewer.py -- --trace-dir /path/to/traces
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

import streamlit as st


# Constants
DEFAULT_TRACE_DIR = Path.cwd() / ".patchpro" / "traces"


def get_trace_dir() -> Path:
    """Get trace directory from command line or use default."""
    # Parse command line args (Streamlit passes them after --)
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR)
    
    try:
        args = parser.parse_args()
        return args.trace_dir
    except SystemExit:
        # Fallback if arg parsing fails
        return DEFAULT_TRACE_DIR


def load_trace_db(trace_dir: Path) -> Optional[sqlite3.Connection]:
    """Load traces.db from directory."""
    db_path = trace_dir / "traces.db"
    
    if not db_path.exists():
        return None
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Return dict-like rows
    return conn


def load_trace_json(trace_dir: Path, trace_id: str) -> Optional[Dict[str, Any]]:
    """Load full trace JSON for a specific trace_id."""
    json_file = trace_dir / f"{trace_id}.json"
    
    if not json_file.exists():
        return None
    
    with open(json_file) as f:
        return json.load(f)


def query_traces(
    conn: sqlite3.Connection,
    rule_id: Optional[str] = None,
    status: Optional[str] = None,
    strategy: Optional[str] = None,
    search_text: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Query traces from SQLite with filters."""
    cursor = conn.cursor()
    
    # Build query
    query = "SELECT * FROM traces WHERE 1=1"
    params = []
    
    if rule_id and rule_id != "All":
        query += " AND rule_id = ?"
        params.append(rule_id)
    
    if status and status != "All":
        query += " AND final_status = ?"
        params.append(status)
    
    if strategy and strategy != "All":
        query += " AND strategy = ?"
        params.append(strategy)
    
    if search_text:
        query += " AND (finding_message LIKE ? OR file_path LIKE ?)"
        search_pattern = f"%{search_text}%"
        params.append(search_pattern)
        params.append(search_pattern)
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    return [dict(row) for row in rows]


def get_summary_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Get summary statistics from all traces."""
    cursor = conn.cursor()
    
    # Total traces
    cursor.execute("SELECT COUNT(*) FROM traces")
    total = cursor.fetchone()[0]
    
    if total == 0:
        return {
            "total_traces": 0,
            "successful_traces": 0,
            "success_rate": 0,
            "avg_cost_usd": 0,
            "avg_latency_ms": 0,
        }
    
    # Success rate
    cursor.execute("SELECT COUNT(*) FROM traces WHERE validation_passed = 1")
    successes = cursor.fetchone()[0]
    
    # Average cost
    cursor.execute("SELECT AVG(cost_usd) FROM traces")
    avg_cost = cursor.fetchone()[0] or 0
    
    # Average latency
    cursor.execute("SELECT AVG(latency_ms) FROM traces")
    avg_latency = cursor.fetchone()[0] or 0
    
    # Total cost
    cursor.execute("SELECT SUM(cost_usd) FROM traces")
    total_cost = cursor.fetchone()[0] or 0
    
    # Average retries
    cursor.execute("SELECT AVG(retry_attempt) FROM traces")
    avg_retries = cursor.fetchone()[0] or 1
    
    return {
        "total_traces": total,
        "successful_traces": successes,
        "failed_traces": total - successes,
        "success_rate": successes / total if total > 0 else 0,
        "avg_cost_usd": avg_cost,
        "total_cost_usd": total_cost,
        "avg_latency_ms": avg_latency,
        "avg_retry_attempt": avg_retries,
    }


def get_filter_options(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    """Get unique values for filter dropdowns."""
    cursor = conn.cursor()
    
    # Unique rule IDs
    cursor.execute("SELECT DISTINCT rule_id FROM traces ORDER BY rule_id")
    rule_ids = ["All"] + [row[0] for row in cursor.fetchall()]
    
    # Unique statuses
    cursor.execute("SELECT DISTINCT final_status FROM traces ORDER BY final_status")
    statuses = ["All"] + [row[0] for row in cursor.fetchall()]
    
    # Unique strategies
    cursor.execute("SELECT DISTINCT strategy FROM traces ORDER BY strategy")
    strategies = ["All"] + [row[0] for row in cursor.fetchall()]
    
    return {
        "rule_ids": rule_ids,
        "statuses": statuses,
        "strategies": strategies,
    }


def render_summary_metrics(stats: Dict[str, Any]):
    """Render summary metrics at top of page."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Traces", stats["total_traces"])
        st.metric("Avg Retry", f"{stats['avg_retry_attempt']:.1f}")
    
    with col2:
        st.metric("Success Rate", f"{stats['success_rate']:.1%}")
        st.metric("Successful", stats["successful_traces"])
    
    with col3:
        st.metric("Avg Cost", f"${stats['avg_cost_usd']:.4f}")
        st.metric("Total Cost", f"${stats['total_cost_usd']:.3f}")
    
    with col4:
        st.metric("Avg Latency", f"{stats['avg_latency_ms']:.0f}ms")
        st.metric("Failed", stats["failed_traces"])


def render_trace_card(trace: Dict[str, Any], trace_dir: Path):
    """Render a single trace as an expandable card."""
    # Status badge
    if trace["validation_passed"]:
        status_color = "🟢"
        status_text = "SUCCESS"
    else:
        status_color = "🔴"
        status_text = trace["final_status"].upper()
    
    # Header line
    header = f"{status_color} **{trace['rule_id']}** - `{Path(trace['file_path']).name}:{trace['line_number']}` - Attempt {trace['retry_attempt']}"
    
    with st.expander(header):
        # Metadata
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**Strategy:**", trace["strategy"])
            st.write("**Model:**", trace["model"])
            st.write("**File Type:**", trace["file_type"])
        
        with col2:
            st.write("**Complexity:**", trace["finding_complexity"])
            st.write("**Category:**", trace["rule_category"])
            st.write("**Tokens:**", trace["tokens_used"])
        
        with col3:
            st.write("**Cost:**", f"${trace['cost_usd']:.4f}")
            st.write("**Latency:**", f"{trace['latency_ms']}ms")
            st.write("**Status:**", status_text)
        
        st.divider()
        
        # Load full trace JSON for detailed info
        full_trace = load_trace_json(trace_dir, trace["trace_id"])
        
        if full_trace:
            # Finding message
            st.write("**Finding:**")
            st.info(full_trace["finding_message"])
            
            # Prompt (collapsed by default)
            with st.expander("📝 View Prompt"):
                st.text_area(
                    "System Prompt",
                    value=full_trace["system_prompt"],
                    height=150,
                    key=f"sys_{trace['trace_id']}"
                )
                st.text_area(
                    "User Prompt",
                    value=full_trace["prompt"],
                    height=300,
                    key=f"prompt_{trace['trace_id']}"
                )
            
            # LLM Response
            with st.expander("🤖 View LLM Response"):
                st.text_area(
                    "Response",
                    value=full_trace["llm_response"],
                    height=300,
                    key=f"resp_{trace['trace_id']}"
                )
            
            # Generated Patch
            if full_trace["patch_generated"]:
                with st.expander("🔧 View Generated Patch"):
                    st.code(full_trace["patch_generated"], language="diff")
            else:
                st.warning("⚠️ No patch generated")
            
            # Validation Errors
            if full_trace["validation_errors"]:
                st.write("**Validation Errors:**")
                for error in full_trace["validation_errors"]:
                    st.error(error)
            
            # Previous Errors (if retry)
            if full_trace["previous_errors"]:
                with st.expander("🔄 Previous Attempt Errors"):
                    for i, error in enumerate(full_trace["previous_errors"], 1):
                        st.write(f"**Error {i}:**")
                        st.code(error)
            
            # Actions
            st.divider()
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📋 Copy Trace ID", key=f"copy_{trace['trace_id']}"):
                    st.code(trace['trace_id'])
            
            with col2:
                if st.button("💾 Save as Good Example", key=f"good_{trace['trace_id']}"):
                    st.success("✅ Marked as good example (feature coming soon)")
            
            with col3:
                if st.button("🐛 Save as Bad Example", key=f"bad_{trace['trace_id']}"):
                    st.warning("⚠️ Marked as bad example (feature coming soon)")


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="PatchPro Trace Viewer",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 PatchPro Trace Viewer")
    st.caption("Analyze patch generation traces and LLM interactions")
    
    # Get trace directory
    trace_dir = get_trace_dir()
    
    # Load database
    conn = load_trace_db(trace_dir)
    
    if conn is None:
        st.error(f"❌ No traces database found at `{trace_dir / 'traces.db'}`")
        st.info("""
        **How to generate traces:**
        
        1. Run PatchPro with agentic mode enabled:
           ```bash
           patchpro analyze-pr --base main --head HEAD --with-llm
           ```
        
        2. Traces will be saved to `.patchpro/traces/`
        
        3. Rerun this viewer to see traces
        """)
        return
    
    # Show trace directory
    st.success(f"✅ Connected to: `{trace_dir}`")
    
    # Get summary stats
    stats = get_summary_stats(conn)
    
    # Render summary metrics
    render_summary_metrics(stats)
    
    st.divider()
    
    # Filters
    st.subheader("🔎 Filter Traces")
    
    filter_options = get_filter_options(conn)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        rule_id_filter = st.selectbox("Rule ID", filter_options["rule_ids"])
    
    with col2:
        status_filter = st.selectbox("Status", filter_options["statuses"])
    
    with col3:
        strategy_filter = st.selectbox("Strategy", filter_options["strategies"])
    
    with col4:
        search_text = st.text_input("Search (message/file)")
    
    # Query traces
    traces = query_traces(
        conn,
        rule_id=rule_id_filter,
        status=status_filter,
        strategy=strategy_filter,
        search_text=search_text,
        limit=100
    )
    
    # Show count
    st.write(f"**Found {len(traces)} traces**")
    
    # Render traces
    if traces:
        for trace in traces:
            render_trace_card(trace, trace_dir)
    else:
        st.info("No traces match your filters")
    
    # Close connection
    conn.close()


if __name__ == "__main__":
    main()
