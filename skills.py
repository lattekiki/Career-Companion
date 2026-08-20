import json
import re
import html
import streamlit as st
from langchain_core.messages import HumanMessage


def _clean(value, limit=700):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _escape(value):
    return html.escape(str(value or ""))


def _parse_json(text):
    raw = (
        str(text or "")
        .replace("```json", "")
        .replace("```JSON", "")
        .replace("```", "")
        .strip()
    )

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("The AI did not return valid JSON.")

    return json.loads(match.group(0))


def _existing_skills(profile):
    return [
        item.strip()
        for item in str(profile.get("skills", "")).replace("•", ",").split(",")
        if item.strip()
    ]


def _analyze(profile, llm):
    current_skills = _existing_skills(profile)

    fallback = {
        "current_skills": current_skills,
        "skills_to_explore": [],
        "summary": (
            "Choose one area that feels useful or interesting. "
            "You do not need to learn everything at once."
        ),
    }

    if llm is None:
        return fallback

    prompt = f"""
You are a compassionate career-development companion.

USER PROFILE
Current role: {profile.get('current_role', '')}
Experience: {profile.get('experience', '')}
Target role: {profile.get('target_role', '')}
Existing skills: {', '.join(current_skills)}
Professional summary: {profile.get('summary', '')}

Your task is to suggest 3-5 "skills worth exploring" for the user's target
role. This is NOT an assessment and NOT a deficit report.

Rules:
- Treat ONLY the explicitly listed existing skills as skills the user already has.
- Do not invent projects, achievements, qualifications, or experience.
- Do not use language such as "lacking", "behind", "unready", "weak", "failure",
  "skills gap", "career readiness", or numerical scores.
- Suggest possibilities that could open useful opportunities for the target role.
- Prefer foundational skills that unlock several related abilities.
- Keep the recommendations practical and non-overwhelming.
- For each skill give a reason, a very small first step, and a possible next step.
- If an existing skill needs deeper development, describe it as a deeper level
  to explore rather than pretending the skill is absent.

Return ONLY valid JSON:
{{
  "skills_to_explore": [
    {{
      "skill": "skill name",
      "why": "why this could be useful",
      "first_step": "a small first step that can be done without overwhelm",
      "next_step": "a reasonable next step after that"
    }}
  ],
  "summary": "one warm sentence about the most useful direction to explore"
}}
"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        data = _parse_json(response.content)

        ideas = data.get("skills_to_explore", [])
        if not isinstance(ideas, list):
            ideas = []

        cleaned = []
        for item in ideas[:5]:
            if not isinstance(item, dict):
                continue

            skill = _clean(item.get("skill"))
            if not skill:
                continue

            cleaned.append(
                {
                    "skill": skill,
                    "why": _clean(item.get("why"), 500),
                    "first_step": _clean(item.get("first_step"), 500),
                    "next_step": _clean(item.get("next_step"), 500),
                }
            )

        return {
            "current_skills": current_skills,
            "skills_to_explore": cleaned,
            "summary": _clean(
                data.get(
                    "summary",
                    "Choose one area that feels useful or interesting.",
                ),
                500,
            ),
        }

    except Exception as exc:
        print("Skills exploration error:", repr(exc))
        return fallback


def _fingerprint(profile):
    return "|".join(
        [
            str(profile.get("current_role", "")),
            str(profile.get("experience", "")),
            str(profile.get("target_role", "")),
            str(profile.get("skills", "")),
            str(profile.get("summary", "")),
        ]
    )


def render_skills_page(profile, llm=None):
    st.markdown(
        '<div class="page-title">✨ Skills Worth Exploring</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="page-subtitle">
            Not a list of things you're missing. Just possibilities that may
            open new doors for the kind of work you want.
        </div>
        """,
        unsafe_allow_html=True,
    )

    fingerprint = _fingerprint(profile)

    if (
        "skills_exploration" not in st.session_state
        or st.session_state.get("skills_exploration_fingerprint") != fingerprint
    ):
        with st.spinner("Thinking about what might be useful next..."):
            st.session_state.skills_exploration = _analyze(profile, llm)
            st.session_state.skills_exploration_fingerprint = fingerprint

    if st.button("↻ Refresh suggestions"):
        with st.spinner("Finding fresh possibilities..."):
            st.session_state.skills_exploration = _analyze(profile, llm)
            st.session_state.skills_exploration_fingerprint = fingerprint
        st.rerun()

    analysis = st.session_state.skills_exploration

    st.info(
        f"🌱 {analysis.get('summary', 'Choose one small direction that feels useful and interesting.')}"
    )

    st.markdown("## Your Current Skills")
    current = analysis.get("current_skills", [])

    if current:
        cols = st.columns(min(4, len(current)))

        for index, skill in enumerate(current):
            with cols[index % len(cols)]:
                st.html(
                    f"""
                    <div style="
                        background:#ffffff;
                        border:1px solid #e5e7eb;
                        border-radius:15px;
                        padding:17px;
                        min-height:95px;
                        margin-bottom:12px;
                    ">
                        <div style="
                            font-size:16px;
                            font-weight:750;
                            color:#111827;
                        ">
                            {_escape(skill)}
                        </div>
                        <div style="
                            font-size:13px;
                            color:#64748b;
                            margin-top:7px;
                        ">
                            Part of your current toolkit
                        </div>
                    </div>
                    """
                )
    else:
        st.info("Tell me a little more about your current skills.")

    st.write("")
    st.markdown("## ✨ Skills Worth Exploring")
    st.caption(
        "These are invitations to explore, not requirements you need to complete."
    )

    ideas = analysis.get("skills_to_explore", [])

    if not ideas:
        st.info(
            "Nothing specific has surfaced yet. Try refreshing the suggestions "
            "or adding more detail to your profile."
        )
        return

    for index, item in enumerate(ideas):
        with st.container(border=True):
            left, right = st.columns([4, 1])

            with left:
                st.markdown(f"### {item['skill']}")
                st.caption(
                    item.get(
                        "why",
                        "This could be useful for the direction you're exploring.",
                    )
                )

            with right:
                st.caption(f"Explore {index + 1}")

            st.write(
                f"**A small first step:** "
                f"{item.get('first_step', 'Start with the fundamentals.')}"
            )

            if item.get("next_step"):
                st.write(f"**Then:** {item['next_step']}")

            if st.button(
                f"Build a small plan for {item['skill']} →",
                key=f"learn_plan_{index}",
            ):
                st.session_state.chat_messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"I'd like to explore {item['skill']}. "
                            "Can you help me make a small, realistic learning plan "
                            "that connects it to my career goals without overwhelming me?"
                        ),
                    }
                )
                st.session_state.nav_page = "💬 Career Companion"
                st.session_state.page_radio = "💬 Career Companion"
                st.rerun()