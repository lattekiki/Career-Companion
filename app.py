import os
import json
import re
import textwrap
from urllib.parse import urljoin

import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from auth import render_auth_page, logout_user
from job_scraper import get_ranked_jobs
from resume_builder import render_resume_builder
from skills import render_skills_page
from interview import render_interview_page, prepare_interview_from_job

from prompts import (
    BURNOUT_ANALYSIS_PROMPT,
    COMPANION_SYSTEM_PROMPT,
)
from database import (
    init_db,
    save_user_profile,
    load_user_profile,
    save_chat_message,
    load_chat_history,
)

# ============================================================
# PAGE CONFIG (MUST BE THE FIRST STREAMLIT COMMAND)
# ============================================================

st.set_page_config(
    page_title="Career Companion",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# GLOBAL STYLING
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #2E264E !important;
    }

    /* ---------- APP BACKGROUND ---------- */
    .stApp {
        background: #F4F1FB !important;
    }

    .block-container {
        max-width: 1400px;
        padding-top: 1.8rem;
        padding-bottom: 3rem;
    }

    /* ---------- SIDEBAR STYLING ---------- */
    [data-testid="stSidebar"] {
        background: #A08CE6 !important;
        border-right: none !important;
        box-shadow: 8px 0px 24px rgba(160, 140, 230, 0.25) !important;
        border-top-right-radius: 36px;
        border-bottom-right-radius: 36px;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    .sidebar-brand {
        padding: 10px 8px;
        text-align: center;
    }

    .sidebar-avatar {
        width: 72px;
        height: 72px;
        background: #C3B4F3;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 32px;
        margin: 0 auto 12px auto;
        box-shadow: inset -3px -3px 8px rgba(0,0,0,0.08), inset 3px 3px 8px rgba(255,255,255,0.6);
    }

    .sidebar-title {
        font-size: 22px;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 4px;
        color: #1F173D !important;
    }

    .sidebar-subtitle {
        color: #382D60 !important;
        font-size: 13px;
        line-height: 1.4;
        font-weight: 500;
    }

    .sidebar-note {
        margin-top: 14px;
        padding: 12px 14px;
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.45);
        box-shadow: inset 1px 1px 3px rgba(255, 255, 255, 0.8), inset -1px -1px 3px rgba(0, 0, 0, 0.05);
        color: #241A47 !important;
        font-size: 12px;
        font-weight: 600;
        line-height: 1.45;
    }

    /* Radio Navigation Pill Buttons - Equal Width Alignment */
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 8px;
        display: flex;
        flex-direction: column;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        width: 100% !important;
        display: flex !important;
        box-sizing: border-box !important;
        background: rgba(255, 255, 255, 0.35) !important;
        border-radius: 18px !important;
        padding: 10px 16px !important;
        border: none !important;
        transition: all 0.2s ease-in-out !important;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] > label > div {
        width: 100% !important;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] label p {
        color: #1F173D !important;
        font-weight: 700 !important;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: rgba(255, 255, 255, 0.65) !important;
        transform: translateY(-2px);
    }

    /* Input Field Labels & Controls in Sidebar */
    [data-testid="stSidebar"] label {
        color: #1F173D !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        margin-bottom: 4px !important;
    }

    [data-testid="stSidebar"] div[data-baseweb="input"] {
        background: #FFFFFF !important;
        border-radius: 18px !important;
        border: 1px solid #C4B5FD !important;
        box-shadow: inset 1px 1px 4px rgba(0, 0, 0, 0.06) !important;
        overflow: hidden !important;
    }

    /* FIX FOR DARK INPUT TEXT VISIBILITY */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] select {
        background: #FFFFFF !important;
        border: none !important;
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
        font-weight: 600 !important;
        padding: 10px 14px !important;
    }

    [data-testid="stSidebar"] input::placeholder {
        color: #8C82B0 !important;
        -webkit-text-fill-color: #8C82B0 !important;
    }

    [data-testid="stSidebar"] h3 {
        color: #1F173D !important;
        font-weight: 800 !important;
    }

    /* ---------- MAIN PAGE TYPOGRAPHY ---------- */
    .page-title {
        font-size: 34px;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.2;
        color: #1F1938 !important;
        margin-bottom: 6px;
    }

    .page-subtitle {
        color: #4A426B !important;
        font-size: 15px;
        line-height: 1.5;
        max-width: 850px;
        margin-bottom: 24px;
        font-weight: 500;
    }

    .section-eyebrow {
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #5B41D9 !important;
        margin-bottom: 8px;
    }

    /* ---------- HERO & SOFT CARDS ---------- */
    .hero-card {
        background: linear-gradient(135deg, #DDD6FE 0%, #C4B5FD 100%);
        border-radius: 32px;
        padding: 32px;
        box-shadow: 
            8px 12px 24px rgba(167, 139, 250, 0.25), 
            inset -4px -4px 12px rgba(124, 58, 237, 0.15), 
            inset 4px 4px 12px rgba(255, 255, 255, 0.7);
        color: #1F1938 !important;
        margin-bottom: 24px;
    }

    .hero-card .card-kicker {
        color: #4A3A7C !important;
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
    }

    .hero-card .card-title-large {
        color: #1F1938 !important;
        font-size: 28px;
        font-weight: 800;
    }

    .hero-card .card-copy {
        color: #382E5C !important;
        font-size: 14px;
        font-weight: 500;
    }

    .soft-card {
        background: #FFFFFF;
        border-radius: 28px;
        padding: 24px;
        box-shadow: 6px 10px 20px rgba(120, 100, 160, 0.06);
        border: 1px solid #E4DCF9;
        color: #1F1938 !important;
    }

    .card-kicker {
        color: #5B41D9 !important;
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
    }

    .card-title-large {
        color: #1F1938 !important;
        font-size: 28px;
        font-weight: 800;
    }

    .card-copy {
        color: #4A426B !important;
        font-size: 14px;
    }

    .journey-chip {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 99px;
        background: #FFFFFF;
        color: #5B21B6 !important;
        font-size: 13px;
        font-weight: 800;
        margin-right: 8px;
        margin-bottom: 8px;
        box-shadow: 2px 4px 10px rgba(109, 40, 217, 0.12);
    }

    /* Container Titles */
    div[data-testid="stVerticalBlock"] h3 {
        color: #1F1938 !important;
        font-weight: 800 !important;
    }

    div[data-testid="stVerticalBlock"] p {
        color: #382E5C !important;
    }

    /* ---------- STAT & METRIC PILLS ---------- */
    .match-pill {
        display: inline-block;
        background: #E0E7FF;
        color: #312E81 !important;
        border-radius: 99px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 800;
    }

    /* ---------- BUTTONS (WHITE TEXT FIX) ---------- */
    .stButton > button {
        background: linear-gradient(180deg, #7E22CE 0%, #6B21A8 100%) !important;
        border: none !important;
        border-radius: 20px !important;
        font-weight: 700 !important;
        min-height: 46px !important;
        box-shadow: 0px 6px 14px rgba(107, 33, 168, 0.3) !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button, 
    .stButton > button *,
    .stButton > button p,
    .stButton > button span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0px 10px 20px rgba(107, 33, 168, 0.4) !important;
    }

    div[data-testid="stLinkButton"] > a {
        background: #EDE9FE !important;
        color: #5B21B6 !important;
        border-radius: 20px !important;
        border: none !important;
        font-weight: 800 !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# INITIALIZE DATABASE & AUTHENTICATION GATE
# ============================================================

load_dotenv()
init_db()

# Render auth page and stop app execution if not logged in
if not render_auth_page():
    st.stop()

# Get authenticated user ID from session state
USER_ID = st.session_state.get("user_id")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.warning(
        "GROQ_API_KEY was not found. "
        "Add it to your .env file and restart Streamlit."
    )

# Load user profile from database safely
if "user_profile" not in st.session_state or not st.session_state.user_profile:
    db_profile = load_user_profile(USER_ID)
    st.session_state.user_profile = db_profile if db_profile else {
        "name": st.session_state.get("user_name", ""),
        "current_role": "",
        "experience": "",
        "target_role": "",
        "summary": "",
        "skills": "",
    }

if st.session_state.user_profile.get("current_role") == "neondb_owner":
    st.session_state.user_profile["current_role"] = ""
if st.session_state.user_profile.get("name") == "neondb_owner":
    st.session_state.user_profile["name"] = ""

if not isinstance(st.session_state.user_profile, dict):
    st.session_state.user_profile = {}

# ============================================================
# CONSTANTS
# ============================================================

AFRIWORK_BASE_URL = "https://afriworket.com"

# ============================================================
# LLM
# ============================================================

@st.cache_resource
def get_llm():
    if not GROQ_API_KEY:
        return None

    return ChatGroq(
        temperature=0.7,
        model_name="openai/gpt-oss-120b",
        groq_api_key=GROQ_API_KEY,
    )

llm = get_llm()

# ============================================================
# SESSION STATE INITIALIZATION (Robust Defaults)
# ============================================================

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "🍀 My Journey"

if "pending_nav_page" not in st.session_state:
    st.session_state.pending_nav_page = None

# SYNC PENDING NAVIGATION BEFORE WIDGET RENDERING
if st.session_state.get("pending_nav_page"):
    st.session_state.page_radio = st.session_state.pending_nav_page
    st.session_state.nav_page = st.session_state.pending_nav_page
    st.session_state.pending_nav_page = None

if "trigger_ai_response" not in st.session_state:
    st.session_state.trigger_ai_response = False

if "chat_messages" not in st.session_state:
    db_history = load_chat_history(USER_ID)
    if db_history:
        st.session_state.chat_messages = db_history
    else:
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": (
                    "Hi! I'm your Career Companion. 👋\n\n"
                    "You can talk to me about your career, skills, job search, "
                    "work stress, interviews, or anything you're unsure about. "
                    "Tell me what's on your mind and we'll take it one step at a time."
                ),
            }
        ]

if "sentiment_score" not in st.session_state:
    st.session_state.sentiment_score = 0.0

if "emotional_label" not in st.session_state:
    st.session_state.emotional_label = "Neutral"

# ============================================================
# NAVIGATION FUNCTION
# ============================================================

def go_to_page(page_name):
    st.session_state.nav_page = page_name
    st.session_state.pending_nav_page = page_name
    st.rerun()

# ============================================================
# AI: SENTIMENT ANALYSIS
# ============================================================

def analyze_burnout_and_sentiment(text, chat_history=None):
    if llm is None:
        return 0.0, "Neutral"

    chat_history = chat_history or []
    current = re.sub(r"\s+", " ", str(text).lower().strip())

    previous_assistant = ""
    for msg in reversed(chat_history[:-1]):
        if msg.get("role") == "assistant":
            previous_assistant = re.sub(r"\s+", " ", str(msg.get("content", "")).lower().strip())
            break

    dissatisfaction_replies = {
        "nothing", "nothing at all", "nothing really", "not really", "not much",
        "nah", "no", "i hate it", "hate it", "i don't like it", "don't like it",
        "i hate my job", "nothing good",
    }

    dissatisfaction_questions = [
        "what do you like", "what do you like most", "what do you enjoy",
        "what do you enjoy most", "what do you enjoy about your work",
        "what do you like about your work", "how do you feel about your work",
        "what motivates you", "what do you find rewarding", "what is your favorite part of your work",
    ]

    short_negative_context = (
        current in dissatisfaction_replies
        and any(phrase in previous_assistant for phrase in dissatisfaction_questions)
    )

    strong_negative_patterns = [
        "i feel hopeless", "i am hopeless", "i'm hopeless", "i feel completely hopeless",
        "i can't do this anymore", "i cannot do this anymore", "i want to give up",
        "i've given up", "i have given up", "i feel like giving up", "nothing is working",
        "i feel completely exhausted", "i am completely exhausted", "i'm completely exhausted",
        "i''m overwhelmed", "i am overwhelmed", "i feel overwhelmed", "i can't cope",
        "i cannot cope", "i feel stuck and hopeless",
    ]

    moderate_negative_patterns = [
        "i'm exhausted", "i am exhausted", "i'm frustrated", "i am frustrated",
        "i'm discouraged", "i am discouraged", "i'm burned out", "i am burned out",
        "i'm burnt out", "i am burnt out", "i'm stressed", "i am stressed",
        "i'm unhappy", "i am unhappy", "i'm miserable", "i am miserable",
        "i dislike my job", "i don't enjoy my work", "i don't enjoy my job",
        "i feel drained", "i feel demotivated", "i feel unmotivated",
        "i've been struggling", "i have been struggling",
    ]

    positive_patterns = [
        "i'm excited", "i am excited", "i'm motivated", "i am motivated",
        "i feel motivated", "i'm happy", "i am happy", "i feel good",
        "i'm feeling good", "i feel great", "i'm feeling great",
        "i'm confident", "i am confident", "i'm looking forward",
        "i am looking forward", "i'm proud", "i am proud",
    ]

    ordinary_question_patterns = [
        "what do you recommend", "what should i do", "what can i do",
        "how can i be more productive", "how can i improve", "what should i work on",
        "what should i learn", "what can i learn", "what skills should i learn",
        "where should i start", "how do i start", "what would you recommend",
        "any advice for today", "what do you suggest",
    ]

    has_strong_negative = any(phrase in current for phrase in strong_negative_patterns)
    has_moderate_negative = any(phrase in current for phrase in moderate_negative_patterns)
    has_positive = any(phrase in current for phrase in positive_patterns)
    is_ordinary_question = ("?" in current and any(phrase in current for phrase in ordinary_question_patterns))

    if short_negative_context:
        return -0.55, "Dissatisfied"
    if has_strong_negative:
        return -0.78, "Overwhelmed"
    if has_moderate_negative and not is_ordinary_question:
        return -0.45, "Discouraged"
    if has_positive and not has_strong_negative:
        return 0.45, "Positive"
    if is_ordinary_question and not has_moderate_negative and not has_strong_negative:
        return 0.05, "Neutral"

    context = f"\nPrevious assistant message:\n{previous_assistant}\n" if previous_assistant else ""

    analysis_prompt = f"""
You are a conservative sentiment analyzer for a career coaching chatbot.
Analyze the CURRENT user message first.

Scale:
- -1.0 = extremely negative
- -0.7 = strongly negative
- -0.4 = moderately negative
- 0.0 = neutral
- +0.4 = moderately positive
- +0.7 = strongly positive
- +1.0 = extremely positive

{context}

Current user message:
{text}

Return ONLY valid JSON:
{{
    "score": <float between -1.0 and 1.0>,
    "label": "<2-3 word emotional state>"
}}
"""

    try:
        response = llm.invoke([HumanMessage(content=analysis_prompt)])
        raw = str(response.content).replace("```json", "").replace("```JSON", "").replace("```", "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("Sentiment model did not return valid JSON.")

        data = json.loads(match.group(0))
        score = max(-1.0, min(1.0, float(data.get("score", 0.0))))
        label = str(data.get("label", "Neutral")).strip() or "Neutral"

        if is_ordinary_question and not has_moderate_negative and not has_strong_negative and score < -0.30:
            score = 0.05
            label = "Neutral"

        return score, label

    except Exception as exc:
        print("Sentiment analysis error:", repr(exc))
        return 0.0, "Neutral"

# ============================================================
# AI: CONVERSATIONAL RESPONSE
# ============================================================

def generate_adaptive_ai_response(chat_history, score, label):
    if llm is None:
        return "I'm currently unable to connect to the AI service. Please check your GROQ_API_KEY."

    profile = st.session_state.user_profile

    system_prompt = (
        COMPANION_SYSTEM_PROMPT
        .replace("{emotional_state}", str(label))
        .replace("{sentiment_score}", str(round(score, 2)))
    )

    system_prompt += f"""

USER PROFILE
- Full Name: {profile.get("name") or "Not provided"}
- Current role: {profile.get("current_role") or "Not provided"}
- Experience: {profile.get("experience") or "Not provided"}
- Target role: {profile.get("target_role") or "Not provided"}
- Current Skills: {profile.get("skills") or "Not provided"}
- Summary: {profile.get("summary") or "Not provided"}

HUMANISTIC CONVERSATION RULES
- Be warm, grounded, and genuinely conversational.
- Adapt dynamically to whatever current skills and background the user provides.
"""

    messages = [SystemMessage(content=system_prompt)]

    for msg in chat_history[-12:]:
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=content))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=content))

    try:
        response = llm.invoke(messages)
        return str(response.content).strip()
    except Exception as exc:
        print("Career Companion response error:", repr(exc))
        return "I'm having trouble connecting right now. Please try sending that message again."

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    raw_name = str(st.session_state.user_profile.get("name") or "").strip()
    user_disp_name = raw_name.split()[0] if raw_name else "there"

    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-avatar">👩‍💻</div>
            <div class="sidebar-title">Hi, {user_disp_name}! 👋</div>
            <div class="sidebar-subtitle">
                A warmer, calmer way to navigate your career journey.
            </div>
            <div class="sidebar-note">
                ✨ Logged in as: <b>{USER_ID}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    pages = [
        "🍀 My Journey",
        "💬 Career Companion",
        "💼 Job Matches",
        "📄 Resume Builder",
        "✨ Skills Worth Exploring",
        "🎤 Interview Practice",
    ]

    selected_page = st.radio(
        "Navigation",
        pages,
        key="page_radio",
        label_visibility="collapsed",
    )

    st.session_state.nav_page = selected_page

    st.divider()

    st.markdown("### 👤 Your Profile")

    val_name = st.text_input(
        "Full Name",
        value=st.session_state.user_profile.get("name") or "",
        placeholder="e.g. Alex Morgan",
        key="sb_full_name"
    )

    val_role = st.text_input(
        "Current Role",
        value=st.session_state.user_profile.get("current_role") or "",
        placeholder="e.g. Graphic Designer, Data Analyst",
        key="sb_current_role"
    )

    val_exp = st.text_input(
        "Experience",
        value=st.session_state.user_profile.get("experience") or "",
        placeholder="e.g. 2 years",
        key="sb_experience"
    )

    val_target = st.text_input(
        "Target Role",
        value=st.session_state.user_profile.get("target_role") or "",
        placeholder="e.g. Art Director, Senior Analyst",
        key="sb_target_role"
    )

    val_skills = st.text_input(
        "Current Skills",
        value=st.session_state.user_profile.get("skills") or "",
        placeholder="e.g. Figma, Photoshop, Color Theory",
        help="Type your current skills separated by commas",
        key="sb_skills"
    )

    if st.button("Save Profile", type="primary", use_container_width=True):
        updated_profile = {
            "name": val_name,
            "current_role": val_role,
            "experience": val_exp,
            "target_role": val_target,
            "skills": val_skills,
            "summary": st.session_state.user_profile.get("summary") or "",
        }
        st.session_state.user_profile = updated_profile
        save_user_profile(USER_ID, updated_profile)
        st.success("Profile saved to database!")
    if st.button("🚪 Log Out", use_container_width=True):
        logout_user()


# ============================================================
# MY JOURNEY
# ============================================================

if st.session_state.nav_page == "🍀 My Journey":
    profile = st.session_state.user_profile

    try:
        ranked_jobs = get_ranked_jobs(profile)
    except Exception as exc:
        print("Job ranking error:", repr(exc))
        ranked_jobs = []

    job_count = len(ranked_jobs)
    
    skills_text = profile.get("skills") or ""

    skill_count = len([
        item.strip()
        for item in skills_text.replace("•", ",").split(",")
        if item.strip()
    ])

    raw_name = str(profile.get("name") or "").strip()
    user_disp_name = raw_name.split()[0] if raw_name else "there"

    st.markdown(
        f"""
        <div class="page-title">
            Good day, {user_disp_name}! ☀️
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="page-subtitle">
            Let's keep your job search human, practical, and manageable.
            You don't need to figure everything out at once.
        </div>
        """,
        unsafe_allow_html=True,
    )

    target_role_display = profile.get("target_role") if profile.get("target_role") else "Your next role"
    st.html(
        f"""
        <div class="hero-card">
            <div class="card-kicker">🎯 Your Goal Direction</div>

            <div class="card-title-large">
                {target_role_display}
            </div>

            <div class="card-copy">
                We'll work from where you are now — your experience,
                your interests, your questions, and the opportunities
                that feel worth exploring.
            </div>

            <div style="margin-top:20px;">
                <span class="journey-chip">
                    💼 {job_count} opportunities
                </span>

                <span class="journey-chip">
                    ✨ {skill_count} skills in profile
                </span>

                <span class="journey-chip">
                    🌱 Explore at your pace
                </span>
            </div>
        </div>
        """
    )

    st.write("")

    left, right = st.columns([1.45, 1], gap="large")

    with left:
        st.markdown('<div class="section-eyebrow">A possible next step</div>', unsafe_allow_html=True)

        if ranked_jobs:
            best = ranked_jobs[0]
            best_title = str(best.get("title", "a promising opportunity"))
            company = str(best.get("company", "Company not listed"))
            score = int(best.get("match_score", 0))
            description = str(best.get("description", "")).strip()

            with st.container(border=True):
                st.markdown(f"### {best_title}")
                st.caption(f"🏢 {company} • 📍 {best.get('location', 'Location not listed')}")
                st.markdown(f'<div class="match-pill">✨ {score}% match score</div>', unsafe_allow_html=True)
                st.write("")
                st.write("A match score is only a starting point. Take a look and decide whether this role feels interesting and worth exploring.")

                if description:
                    with st.expander("Preview the role"):
                        st.write(description[:3500])

                if st.button("Explore this opportunity →", key="journey_explore_job", use_container_width=True):
                    go_to_page("💼 Job Matches")

        else:
            with st.container(border=True):
                st.markdown("### Start with a conversation")
                st.write("Tell me what kind of work you're hoping to find, and we'll explore directions together.")

                if st.button("Talk to your Companion →", key="journey_talk", use_container_width=True):
                    go_to_page("💬 Career Companion")

        st.write("")
        st.markdown('<div class="section-eyebrow">Your tools</div>', unsafe_allow_html=True)

        tool1, tool2 = st.columns(2)
        with tool1:
            with st.container(border=True):
                st.markdown("### 🎤 Interview Practice")
                st.caption("Bring a real role and practice for that specific conversation.")
                if st.button("Practice an interview", key="journey_interview", use_container_width=True):
                    go_to_page("🎤 Interview Practice")

        with tool2:
            with st.container(border=True):
                st.markdown("### ✨ Skills Worth Exploring")
                st.caption("Gentle suggestions for skills that could open new doors.")
                if st.button("Explore skills", key="journey_skills", use_container_width=True):
                    go_to_page("✨ Skills Worth Exploring")

    with right:
        with st.container(border=True):
            st.markdown("### 💬 Need somewhere to start?")
            st.caption("You can talk about uncertainty, motivation, job searching, interviews, or what you might want to learn.")
            st.write("")
            if st.button("Open Career Companion", key="journey_companion", use_container_width=True):
                go_to_page("💬 Career Companion")

        st.write("")
        with st.container(border=True):
            st.markdown("### 🌱 Keep it manageable")
            st.write("You don't have to solve your whole career today. One useful conversation, one opportunity, or one small learning step is enough.")

        st.write("")
        with st.container(border=True):
            st.markdown("### 📌 Your profile snapshot")
            st.markdown(f"**Name:** {profile.get('name') or 'Not set'}")
            st.markdown(f"**Current role:** {profile.get('current_role') or 'Not set'}")
            st.markdown(f"**Experience:** {profile.get('experience') or 'Not set'}")
            st.markdown(f"**Target:** {profile.get('target_role') or 'Not set'}")
            st.markdown(f"**Current Skills:** {profile.get('skills') or 'None listed'}")
            st.caption("You can update these details anytime in the sidebar.")

# ============================================================
# CAREER COMPANION
# ============================================================

elif st.session_state.nav_page == "💬 Career Companion":
    st.markdown('<div class="page-title">💬 Career Companion</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">A real conversation about your career — adapted to where you are, including how you\'re feeling.</div>', unsafe_allow_html=True)

    if st.session_state.get("trigger_ai_response", False):
        st.session_state.trigger_ai_response = False
        latest_user_msg = st.session_state.chat_messages[-1]["content"]
        
        with st.spinner("Listening..."):
            new_score, new_label = analyze_burnout_and_sentiment(latest_user_msg, st.session_state.chat_messages)

        st.session_state.sentiment_score = new_score
        st.session_state.emotional_label = new_label
        save_chat_message(USER_ID, "user", latest_user_msg, new_score, new_label)

        with st.spinner("Thinking with you..."):
            ai_reply = generate_adaptive_ai_response(st.session_state.chat_messages, new_score, new_label)

        st.session_state.chat_messages.append({"role": "assistant", "content": ai_reply})
        save_chat_message(USER_ID, "assistant", ai_reply, new_score, new_label)

    for msg in st.session_state.chat_messages:
        role = "user" if msg["role"] == "user" else "assistant"
        with st.chat_message(role):
            st.write(msg["content"])

    user_input = st.chat_input("Tell me what's on your mind...")

    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        with st.spinner("Listening..."):
            new_score, new_label = analyze_burnout_and_sentiment(user_input, st.session_state.chat_messages)

        st.session_state.sentiment_score = new_score
        st.session_state.emotional_label = new_label

        save_chat_message(USER_ID, "user", user_input, new_score, new_label)

        with st.spinner("Thinking with you..."):
            ai_reply = generate_adaptive_ai_response(st.session_state.chat_messages, new_score, new_label)

        st.session_state.chat_messages.append({"role": "assistant", "content": ai_reply})
        save_chat_message(USER_ID, "assistant", ai_reply, new_score, new_label)
        st.rerun()

# ============================================================
# JOB MATCHES
# ============================================================

elif st.session_state.nav_page == "💼 Job Matches":
    st.markdown('<div class="page-title">💼 Explore Jobs</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Opportunities that may be worth exploring based on your current profile.</div>', unsafe_allow_html=True)

    profile = st.session_state.user_profile

    try:
        ranked_jobs = get_ranked_jobs(profile)
    except Exception as exc:
        st.error(f"Could not load ranked jobs: {exc}")
        ranked_jobs = []

    if not ranked_jobs:
        st.warning("No jobs found matching current criteria.")
    else:
        f1, f2, f3 = st.columns(3)
        with f1:
            locations = ["Any location"]
            for job in ranked_jobs:
                location = str(job.get("location", "")).strip()
                if location and location not in locations:
                    locations.append(location)
            selected_location = st.selectbox("Location", locations)

        with f2:
            minimum_match = st.slider("Minimum Match Score", min_value=0, max_value=100, value=0, step=5)

        with f3:
            sort_option = st.selectbox("Sort by", ["Best Match", "Newest"])

        filtered_jobs = []
        for job in ranked_jobs:
            location = str(job.get("location", ""))
            if selected_location != "Any location" and selected_location.lower() not in location.lower():
                continue
            if job.get("match_score", 0) < minimum_match:
                continue
            filtered_jobs.append(job)

        if sort_option == "Best Match":
            filtered_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        st.write("")
        st.html(f"""
            <div class="soft-card">
                <div class="card-kicker">Opportunities</div>
                <div class="card-title-large">{len(filtered_jobs)} roles to explore</div>
            </div>
        """)
        st.write("")

        for index, job in enumerate(filtered_jobs):
            score = int(job.get("match_score", 0))
            raw_link = job.get("link") or job.get("url") or ""
            job_link = urljoin(AFRIWORK_BASE_URL, raw_link)

            with st.container(border=True):
                left_col, score_col = st.columns([5, 1])
                with left_col:
                    st.markdown(f"### {job.get('title', 'Untitled Job')}")
                    st.caption(f"🏢 {job.get('company', 'Company not listed')} • 📍 {job.get('location', 'Location not listed')}")
                    st.caption(f"🕒 {job.get('posted', 'Recently posted')}")
                    matched = job.get("matched_skills", [])
                    if matched:
                        st.write("You already bring: " + " • ".join(matched))

                with score_col:
                    st.metric("Match", f"{score}%")

                description = str(job.get("description", "")).strip()
                if description:
                    with st.expander("View role details"):
                        st.write(description)

                b1, b2 = st.columns(2)
                with b1:
                    if job_link:
                        st.link_button("View Job ↗", job_link, use_container_width=True)
                with b2:
                    if st.button("🎤 Prepare for interview", key=f"prepare_interview_{index}", use_container_width=True):
                        prepare_interview_from_job(job)
                        go_to_page("🎤 Interview Practice")

# ============================================================
# RESUME BUILDER
# ============================================================

elif st.session_state.nav_page == "📄 Resume Builder":
    render_resume_builder(st.session_state.user_profile)

# ============================================================
# SKILLS WORTH EXPLORING
# ============================================================

elif st.session_state.nav_page == "✨ Skills Worth Exploring":
    render_skills_page(st.session_state.user_profile, llm=llm)

# ============================================================
# INTERVIEW PRACTICE
# ============================================================

elif st.session_state.nav_page == "🎤 Interview Practice":
    render_interview_page(profile=st.session_state.user_profile, llm=llm)