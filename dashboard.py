import streamlit as st
import pandas as pd
from app.database import get_all_reviews, get_labels, label_suggestion, init_db

init_db()

st.set_page_config(page_title="Code Review Bot — Eval Dashboard", layout="wide")
st.title("🤖 Code Review Bot — Evaluation Dashboard")

# ── Metrics row ──────────────────────────────────────────────────────────────
labels = get_labels()
total = len(labels)
labeled = [l for l in labels if l["acted_on"] is not None]
acted_on = [l for l in labeled if l["acted_on"] is True]

precision = len(acted_on) / len(labeled) * 100 if labeled else 0
noise_rate = 100 - precision if labeled else 0
coverage = len(labeled) / total * 100 if total > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Suggestions", total)
col2.metric("Labeled", f"{len(labeled)}/{total}")
col3.metric("Precision", f"{precision:.0f}%",
            help="% of suggestions that were acted on by the author")
col4.metric("Noise Rate", f"{noise_rate:.0f}%",
            help="% of suggestions that were ignored")

st.divider()

# ── Reviews table ─────────────────────────────────────────────────────────────
st.subheader("📋 All Reviews")
reviews = get_all_reviews()

if not reviews:
    st.info("No reviews yet. Trigger a PR webhook to generate some.")
else:
    for review in reviews:
        with st.expander(
            f"PR #{review['pr_number']} — {review['pr_title']} ({review['repo']})"
        ):
            st.markdown(f"**Summary:** {review['summary']}")
            st.markdown(f"**Test coverage:** {review['test_coverage']}")

            col_r, col_s = st.columns(2)
            with col_r:
                st.markdown("**⚠️ Risks**")
                for r in review["risks"]:
                    st.markdown(f"- {r}")
            with col_s:
                st.markdown("**💡 Suggestions**")
                for s in review["suggestions"]:
                    st.markdown(f"- {s}")

st.divider()

# ── Labeling interface ────────────────────────────────────────────────────────
st.subheader("🏷️ Label Suggestions")
st.caption("Mark each suggestion as acted on or ignored to build your precision dataset.")

unlabeled = [l for l in labels if l["acted_on"] is None]

if not unlabeled:
    st.success("All suggestions labeled! Check the precision metric above.")
else:
    st.info(f"{len(unlabeled)} suggestions waiting to be labeled.")

    for item in unlabeled[:10]:  # show 10 at a time
        kind = "Risk" if item["is_risk"] else "Suggestion"
        with st.container():
            st.markdown(f"**[{kind}]** {item['suggestion_text']}")
            col_a, col_b, col_c = st.columns([1, 1, 4])
            with col_a:
                if st.button("✅ Acted on", key=f"yes_{item['id']}"):
                    label_suggestion(item["id"], acted_on=True)
                    st.rerun()
            with col_b:
                if st.button("❌ Ignored", key=f"no_{item['id']}"):
                    label_suggestion(item["id"], acted_on=False)
                    st.rerun()
            st.divider()

# ── Precision over time ───────────────────────────────────────────────────────
if len(labeled) >= 3:
    st.subheader("📈 Precision Over Time")
    df = pd.DataFrame(labeled)
    df["cumulative_precision"] = (
        df["acted_on"]
        .expanding()
        .mean()
        .mul(100)
        .round(1)
    )
    st.line_chart(df["cumulative_precision"])