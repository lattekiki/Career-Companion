import os
import json
import re
from io import BytesIO
import requests
import streamlit as st
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from audio_recorder_streamlit import audio_recorder
from groq import Groq

# Database imports
from database import save_interview_session

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


def _clean(text, limit=18000):
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _json(text):
    raw = str(text or "").replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("The AI did not return valid JSON.")
    return json.loads(match.group(0))


def _fetch_url(url):
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 CareerCompanion/1.0"},
        timeout=15,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    return _clean(soup.get_text(" ", strip=True))


def _read_pdf(file):
    if PdfReader is None:
        raise RuntimeError("PDF uploads need pypdf. Install it with: python -m pip install pypdf")
    reader = PdfReader(BytesIO(file.read()))
    return _clean("\n".join(page.extract_text() or "" for page in reader.pages))


def _research_company(name):
    if not name.strip():
        return ""
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": f"{name} company careers values"},
            headers={"User-Agent": "Mozilla/5.0 CareerCompanion/1.0"},
            timeout=12,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        pieces = []
        for result in soup.select(".result")[:6]:
            title = result.select_one(".result__title")
            snippet = result.select_one(".result__snippet")
            if title:
                pieces.append(title.get_text(" ", strip=True))
            if snippet:
                pieces.append(snippet.get_text(" ", strip=True))
        return _clean("\n".join(pieces), 7000)
    except Exception as exc:
        print("Company research error:", repr(exc))
        return ""


def _job_text(job):
    if not job:
        return ""
    return _clean(f"""
Role: {job.get('title', '')}
Company: {job.get('company', '')}
Location: {job.get('location', '')}
Matched skills: {', '.join(job.get('matched_skills', []) or [])}
Description:
{job.get('description', '')}
""", 14000)


def prepare_interview_from_job(job):
    st.session_state.interview_target_role = str((job or {}).get("title", "")).strip()
    st.session_state.interview_source_text = _job_text(job)
    st.session_state.interview_company = str((job or {}).get("company", "")).strip()
    st.session_state.interview_company_research = ""
    st.session_state.interview_context = None
    st.session_state.interview_started = False
    st.session_state.interview_transcript = []
    st.session_state.interview_feedback = ""


def _transcribe_audio_groq(audio_bytes):
    """Accurately transcribes spoken audio into text using Groq's Whisper API."""
    if not audio_bytes:
        return ""

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        st.error("GROQ_API_KEY is missing from environment variables.")
        return ""

    try:
        client = Groq(api_key=groq_api_key)
        
        # Pass audio stream payload directly to Groq Whisper
        transcription = client.audio.transcriptions.create(
            file=("user_speech.wav", audio_bytes),
            model="whisper-large-v3-turbo",
            response_format="text",
        )
        return str(transcription).strip()
    except Exception as exc:
        print("Whisper Transcription Error:", repr(exc))
        st.error(f"Failed to transcribe speech: {exc}")
        return ""


def _get_active_llm(llm):
    """Ensures a valid LLM instance is available."""
    if llm is not None:
        return llm
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        return ChatGroq(model_name="llama-3.3-70b-versatile", groq_api_key=groq_api_key)
    return None


def _build_context(profile, role_title, role_text, company_research, llm):
    llm = _get_active_llm(llm)

    prompt = f"""
You are a warm, human, deeply engaging interview coach.

TARGET ROLE APPLYING FOR:
{role_title}

USER PROFILE
Current role: {profile.get('current_role', '')}
Experience: {profile.get('experience', '')}
Skills: {profile.get('skills', '')}
Summary: {profile.get('summary', '')}

ROLE MATERIAL
{role_text}

PUBLIC COMPANY CONTEXT
{company_research or 'No additional company context was available.'}

Create a customized interview plan for the role: "{role_title}". 
The goal is to have a flowing, authentic conversation to understand the candidate's personality, background, and perspective.

Return ONLY valid JSON:
{{
  "role": "{role_title}",
  "company": "...",
  "themes": ["...", "...", "..."],
  "opening_question": "Hi there! It's great to meet you. Thanks so much for taking the time to chat today about the {role_title} position. How are you doing, and could you tell me a little bit about yourself and your background to get us started?",
  "warmup_note": "We'll take our time to chat casually and get to know your unique background and personality."
}}
"""
    if llm is None:
        return {
            "role": role_title or profile.get("target_role", "Target Role"),
            "company": "",
            "themes": [],
            "opening_question": f"Hi there! Thanks for meeting with me today for the {role_title} role. How are you doing, and could you tell me a little bit about yourself?",
            "warmup_note": "We'll keep this conversational and natural.",
        }
    response = llm.invoke([HumanMessage(content=prompt)])
    return _json(response.content)


def _next(profile, context, transcript, answer, llm):
    llm = _get_active_llm(llm)

    prompt = f"""
You are an expert, deeply attentive human interviewer conducting a live practice conversation. Your absolute priority is building connection, acknowledging what the candidate just said, and drawing out their personality and experiences organically.

USER PROFILE:
Role: {profile.get('current_role', '')}
Experience: {profile.get('experience', '')}
Skills: {profile.get('skills', '')}

INTERVIEW CONTEXT:
{json.dumps(context, indent=2)}

CANDIDATE'S LATEST INPUT:
"{answer}"

TRANSCRIPT HISTORY:
{json.dumps(transcript[-6:], indent=2)}

CRITICAL INSTRUCTIONS:
1. **READ AND REACT SPECIFICALLY:** Look closely at CANDIDATE'S LATEST INPUT above. If they mentioned their name (e.g., Banana), their background (e.g., software developer), a specific hobby, or a feeling, you MUST explicitly acknowledge and validate it in your response. Never ignore what they just said!
2. **BE A HUMAN CONVERSATIONALIST:** Do not sound like a scripted checklist. If they respond to a greeting or introduction, chat back like a real person, react warmly to their background, and follow up smoothly on *what they just shared* before introducing any new direction.
3. **ONE QUESTION ONLY:** Ask exactly ONE thoughtful follow-up question that builds directly on their previous statement to learn more about who they are or their experience.

Return ONLY valid JSON:
{{
  "feedback": "Warm, specific, personalized reaction acknowledging their exact words and building rapport",
  "next_question": "A natural, conversational follow-up question that builds directly on what they just shared"
}}
"""
    if llm is None:
        return {
            "feedback": "It's great to meet you!",
            "next_question": "What got you started in your tech journey?",
        }

    response = llm.invoke([HumanMessage(content=prompt)])
    res = _json(response.content)

    if not res.get("next_question"):
        res["next_question"] = "That's fascinating! Could you tell me a bit more about how that experience shaped your career?"

    return res


def _start(profile, target_role, llm):
    role_text = st.session_state.interview_source_text.strip()
    if not role_text:
        st.warning("Add a job link, upload the role material, or paste the job description first.")
        return
    with st.spinner("Reading the role material and shaping your session..."):
        try:
            context = _build_context(
                profile,
                target_role,
                role_text,
                st.session_state.get("interview_company_research", ""),
                llm,
            )
        except Exception as exc:
            st.error(f"I couldn't prepare the interview yet: {exc}")
            return

    st.session_state.interview_context = context
    st.session_state.interview_started = True
    st.session_state.interview_feedback = ""
    opening = context.get(
        "opening_question",
        f"Hi there! It's wonderful to connect with you today for the {target_role} position. How are you doing, and could you tell me a little bit about yourself and your background?",
    )
    st.session_state.interview_transcript = [{"role": "interviewer", "content": opening}]
    
    # Save session to Neon DB
    user_id = st.session_state.get("user_id", "demo_user_1")
    save_interview_session(user_id, target_role, st.session_state.get("interview_company", ""), st.session_state.interview_transcript)
    st.rerun()


def render_interview_page(profile, llm):
    for key, default in {
        "interview_target_role": profile.get("target_role", ""),
        "interview_source_text": "",
        "interview_company": "",
        "interview_company_research": "",
        "interview_context": None,
        "interview_started": False,
        "interview_transcript": [],
        "interview_feedback": "",
        "last_audio_bytes": None,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    st.markdown('<div class="page-title">🎤 Interview Practice</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="page-subtitle">
            Bring a real role. We'll prepare and practice for that conversation together.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----------------------------------------------------
    # SCREEN 2: ACTIVE INTERVIEW CONVERSATION
    # ----------------------------------------------------
    if st.session_state.interview_started:
        context = st.session_state.interview_context or {}
        role_display = context.get('role') or st.session_state.get('interview_target_role') or 'Target Role'
        company_display = context.get('company') or st.session_state.get('interview_company', '')

        header_col1, header_col2 = st.columns([4, 1])
        with header_col1:
            st.html(f"""
                <div style="background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:22px;margin-bottom:18px;">
                    <div style="font-size:12px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Practicing for</div>
                    <div style="font-size:25px;font-weight:800;color:#111827;margin-top:6px;">{role_display}</div>
                    <div style="color:#64748b;margin-top:4px;">{company_display}</div>
                </div>
            """)
        with header_col2:
            if st.button("⚙️ Reset Session", use_container_width=True):
                st.session_state.interview_started = False
                st.session_state.interview_context = None
                st.session_state.interview_transcript = []
                st.session_state.interview_feedback = ""
                st.session_state.last_audio_bytes = None
                st.rerun()

        if context.get("warmup_note"):
            st.info(f"🌱 {context['warmup_note']}")

        # Transcript Stream (Clean Text Conversation)
        for item in st.session_state.interview_transcript:
            if item["role"] == "interviewer":
                with st.chat_message("assistant"):
                    st.write(item["content"])
            else:
                with st.chat_message("user"):
                    st.write(item["content"])

        if st.session_state.interview_feedback:
            st.success(st.session_state.interview_feedback)

        # INPUT BAR: PUSH-TO-TALK MIC + TEXT FIELD
        st.markdown("---")
        input_col1, input_col2 = st.columns([1, 6])

        with input_col1:
            st.write("🎙️ **Push-to-Talk:**")
            recorded_audio = audio_recorder(
                text="",
                recording_color="#e11d48",
                neutral_color="#6366f1",
                icon_name="microphone",
                icon_size="2x",
            )

        with input_col2:
            typed_answer = st.chat_input("Or type your response here...")

        # Process Answer (Audio or Text)
        answer = None

        if recorded_audio and recorded_audio != st.session_state.last_audio_bytes:
            st.session_state.last_audio_bytes = recorded_audio
            with st.spinner("Transcribing your speech via Whisper..."):
                answer = _transcribe_audio_groq(recorded_audio)
        elif typed_answer:
            answer = typed_answer

        if answer and answer.strip():
            st.session_state.interview_transcript.append({"role": "candidate", "content": answer})
            with st.spinner("Listening closely and responding..."):
                try:
                    result = _next(
                        profile,
                        context,
                        st.session_state.interview_transcript,
                        answer,
                        llm,
                    )
                except Exception as exc:
                    st.error(f"I couldn't continue the interview: {exc}")
                    return

            st.session_state.interview_feedback = str(result.get("feedback", "Thanks for sharing!"))
            st.session_state.interview_transcript.append({
                "role": "interviewer",
                "content": str(result.get("next_question", "Tell me more about that!")),
            })

            # Save full updated transcript to Neon Postgres
            user_id = st.session_state.get("user_id", "demo_user_1")
            save_interview_session(user_id, role_display, company_display, st.session_state.interview_transcript)

            st.rerun()
        return

    # ----------------------------------------------------
    # SCREEN 1: SETUP FORM
    # ----------------------------------------------------
    st.html("""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:24px;margin-bottom:18px;">
            <div style="font-size:21px;font-weight:800;color:#111827;">Prepare for a real interview</div>
            <div style="color:#64748b;line-height:1.65;margin-top:7px;">
                Paste a public job link, upload role material, or paste the job description below. Specify the position you're applying for to start a guided conversation.
            </div>
        </div>
    """)

    # Target Role Field
    target_role_input = st.text_input(
        "Role you are applying for *",
        value=st.session_state.get("interview_target_role", profile.get("target_role", "")),
        placeholder="e.g. Software Engineer, Product Manager",
    )

    url = st.text_input("Public job or company link", placeholder="https://company.com/jobs/software-engineer")
    upload = st.file_uploader("Upload job/interview material", type=["pdf", "txt"])
    pasted = st.text_area("Or paste the job description", value=st.session_state.interview_source_text, height=180)
    company = st.text_input("Company name (optional)", value=st.session_state.get("interview_company", ""))

    if st.button("Prepare my interview →", type="primary", use_container_width=True):
        if not target_role_input.strip():
            st.warning("Please enter the role you are applying for before starting.")
            return

        source = ""
        if upload:
            try:
                if upload.name.lower().endswith('.pdf'):
                    source = _read_pdf(upload)
                else:
                    source = _clean(upload.getvalue().decode('utf-8', errors='ignore'))
            except Exception as exc:
                st.error(f"Failed to process file: {exc}")
                return
        elif url.strip():
            try:
                with st.spinner("Fetching contents from public page..."):
                    source = _fetch_url(url.strip())
            except Exception:
                st.warning("I couldn't read that URL directly. Please copy and paste the text into the job description box below.")
        elif pasted.strip():
            source = pasted.strip()

        if not source:
            st.warning("Please add a link, upload a file, or paste the job description.")
            return

        st.session_state.interview_target_role = target_role_input.strip()
        st.session_state.interview_source_text = source
        st.session_state.interview_company = company.strip()

        if company.strip():
            with st.spinner("Searching public company context..."):
                st.session_state.interview_company_research = _research_company(company.strip())

        _start(profile, target_role_input.strip(), llm)

    if st.session_state.interview_source_text:
        with st.expander("Preview parsed role material"):
            st.write(st.session_state.interview_source_text[:12000])

    st.info(
        "💛 This is practice, not a test. We won't give you a readiness score. "
        "We'll look at what you already do well, gently work through harder parts, and build confidence through practice."
    )