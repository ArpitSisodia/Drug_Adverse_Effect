import streamlit as st
from neo4j import GraphDatabase

from chatbot.answer_synthesis import synthesize
from chatbot.cypher_safety import DEFAULT_LIMIT, ensure_limit, run_safely
from chatbot.query_router import classify, route
from chatbot.query_templates import CAVEAT
from config.settings import settings

st.set_page_config(page_title="FAERS Drug-Adverse-Event Chatbot", page_icon="\U0001F48A")


@st.cache_resource
def get_driver():
    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


@st.cache_data(show_spinner=False)
def answer_question(question: str) -> str:
    driver = get_driver()
    with driver.session(database=settings.neo4j_database) as session:
        try:
            classification = classify(question)
        except Exception:
            return "I'm having trouble reaching the language model right now (it may be rate-limited on the free tier) -- please try again in a moment."

        routed = route(session, classification)
        if routed.error:
            return routed.error

        cypher = ensure_limit(routed.cypher, DEFAULT_LIMIT)
        try:
            rows = run_safely(session, cypher, routed.params)
        except Exception as e:  # noqa: BLE001
            return f"That query didn't run successfully ({e}). Try rephrasing the question."

        return synthesize(classification.category, rows, routed.params)


st.title("FAERS Drug-Adverse-Event Chatbot")
st.caption("FDA FAERS 2026Q2 spontaneous adverse-event reports -- report counts and co-occurrence only.")

with st.sidebar:
    st.markdown("### About this data")
    st.info(CAVEAT)
    st.markdown(
        "**Can't answer:** true incidence/risk rates, causality claims, trends across "
        "quarters, or which specific drug in a multi-drug case caused a specific reaction."
    )
    st.markdown("**Example questions:**")
    st.markdown(
        "- How many reports mention pomalidomide?\n"
        "- What reactions are most reported with epinephrine?\n"
        "- Top 10 drugs by report count\n"
        "- Compare report counts for pomalidomide and epinephrine\n"
        "- Age/sex breakdown for pomalidomide reports"
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if question := st.chat_input("Ask about drugs and adverse events in this dataset..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = answer_question(question)
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
