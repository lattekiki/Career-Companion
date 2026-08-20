import streamlit as st
from database import register_user, authenticate_user
import textwrap

# ============================================================
# LOGOUT
# ============================================================


def logout_user():
    """Log out the current user."""

    keys_to_clear = [
        "authenticated",
        "user_id",
        "user_name",
        "user_profile",
        "chat_messages",
    ]

    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()


# ============================================================
# AUTH PAGE
# ============================================================


def render_auth_page() -> bool:

    if st.session_state.get("authenticated", False):
        return True

    # ========================================================
    # CSS ONLY
    # ========================================================

    st.markdown(
        """
        <style>

        /* ====================================================
            PAGE
        ==================================================== */

        .stApp {
            background:
                radial-gradient(
                    circle at 10% 10%,
                    rgba(139, 92, 246, 0.08),
                    transparent 30%
                ),
                radial-gradient(
                    circle at 90% 90%,
                    rgba(99, 102, 241, 0.08),
                    transparent 30%
                ),
                #f8f7fc !important;
        }

        .block-container {
            max-width: 1450px !important;
            padding: 2rem !important;
        }


        /* ====================================================
            STREAMLIT COLUMNS
        ==================================================== */

        div[data-testid="column"] {
            padding-left: 0.6rem;
            padding-right: 0.6rem;
        }


        /* ====================================================
            LEFT PANEL
        ==================================================== */

        .brand-box {
            min-height: 680px;
            padding: 50px;
            border-radius: 32px;
            position: relative;
            overflow: hidden;
            color: white;
            background:
                radial-gradient(
                    circle at 20% 15%,
                    rgba(216, 180, 254, 0.30),
                    transparent 30%
                ),
                radial-gradient(
                    circle at 90% 80%,
                    rgba(129, 140, 248, 0.28),
                    transparent 32%
                ),
                linear-gradient(
                    145deg,
                    #4c1d95 0%,
                    #6d28d9 42%,
                    #7c3aed 70%,
                    #4338ca 100%
                );
            box-shadow: 0 30px 70px rgba(76, 29, 149, 0.20);
        }


        /* Decorative circles */

        .circle-a {
            position: absolute;
            width: 420px;
            height: 420px;
            top: -190px;
            right: -170px;
            border-radius: 50%;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
        }

        .circle-b {
            position: absolute;
            width: 300px;
            height: 300px;
            bottom: -160px;
            left: -140px;
            border-radius: 50%;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.07);
        }


        /* ====================================================
            BRAND LOGO
        ==================================================== */

        .brand-logo {
            width: 52px;
            height: 52px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 16px;
            background: rgba(255,255,255,0.14);
            border: 1px solid rgba(255,255,255,0.20);
            font-size: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.12);
        }


        /* ====================================================
            LEFT HEADLINE
        ==================================================== */

        .eyebrow {
            display: inline-block;
            margin-top: 95px;
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.14);
            color: rgba(255,255,255,0.90);
            font-size: 0.70rem;
            font-weight: 700;
            letter-spacing: 0.10em;
            text-transform: uppercase;
        }


        .main-headline {
            margin-top: 22px;
            font-size: clamp(2.8rem, 4vw, 4.6rem);
            line-height: 1.03;
            letter-spacing: -0.055em;
            font-weight: 850;
            color: white;
        }

        .main-headline span {
            display: block;
            color: #ddd6fe;
        }


        /* ====================================================
            DESCRIPTION
        ==================================================== */

        .brand-description {
            max-width: 500px;
            margin-top: 25px;
            color: rgba(255,255,255,0.76);
            font-size: 1rem;
            line-height: 1.75;
        }


        /* ====================================================
            FEATURE PILLS
        ==================================================== */

        .feature-container {
            display: flex;
            flex-wrap: wrap;
            gap: 9px;
            margin-top: 28px;
        }

        .feature {
            padding: 9px 12px;
            border-radius: 12px;
            background: rgba(255,255,255,0.09);
            border: 1px solid rgba(255,255,255,0.13);
            color: rgba(255,255,255,0.88);
            font-size: 0.74rem;
            font-weight: 600;
        }


        /* ====================================================
            RIGHT SIDE
        ==================================================== */

        .auth-title {
            margin-top: 130px;
            margin-bottom: 28px;
        }

        .auth-title h1 {
            margin: 0;
            color: #18152f;
            font-size: 2.25rem;
            font-weight: 850;
            letter-spacing: -0.05em;
        }

        .auth-title p {
            margin-top: 10px;
            color: #64748b;
            font-size: 0.90rem;
            line-height: 1.65;
        }


        /* ====================================================
            INPUTS
        ==================================================== */

        div[data-testid="stTextInput"] label {
            font-size: 0.78rem !important;
            font-weight: 700 !important;
            color: #334155 !important;
        }

        div[data-testid="stTextInput"] input {
            height: 50px !important;
            border-radius: 14px !important;
            border: 1px solid #e3e0eb !important;
            background: #ffffff !important;
            color: #18152f !important;
            padding: 0.7rem 1rem !important;
            font-size: 0.90rem !important;
        }

        div[data-testid="stTextInput"] input:hover {
            border-color: #c4b5fd !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: #8b5cf6 !important;
            box-shadow: 0 0 0 4px rgba(139,92,246,0.10) !important;
        }


        /* ====================================================
            TABS
        ==================================================== */

        button[data-baseweb="tab"] {
            font-weight: 700 !important;
            color: #94a3b8 !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: #7c3aed !important;
        }

        div[data-baseweb="tab-highlight"] {
            background: linear-gradient(90deg, #8b5cf6, #6366f1) !important;
            height: 3px !important;
            border-radius: 999px !important;
        }


        /* ====================================================
            BUTTON
        ==================================================== */

        .stButton button[kind="primary"] {
            height: 51px !important;
            border: none !important;
            border-radius: 14px !important;
            background: linear-gradient(135deg, #7c3aed, #6d28d9, #4f46e5) !important;
            color: white !important;
            font-weight: 750 !important;
            box-shadow: 0 10px 25px rgba(109,40,217,0.22) !important;
            transition: all 0.2s ease !important;
        }

        .stButton button[kind="primary"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 16px 32px rgba(109,40,217,0.30) !important;
        }


        /* ====================================================
            FOOTER
        ==================================================== */

        .auth-footer {
            text-align: center;
            margin-top: 25px;
            color: #94a3b8;
            font-size: 0.70rem;
        }

        .auth-footer strong {
            color: #7c3aed;
        }


        /* ====================================================
            MOBILE
        ==================================================== */

        @media (max-width: 850px) {
            .block-container {
                padding: 1rem !important;
            }
            .brand-box {
                min-height: 560px;
                padding: 32px;
                border-radius: 25px;
            }
            .eyebrow {
                margin-top: 60px;
            }
            .main-headline {
                font-size: 2.8rem;
            }
            .auth-title {
                margin-top: 40px;
            }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # SPLIT SCREEN
    # ========================================================

    left, right = st.columns(
        [1.08, 0.92],
        gap="large",
    )

# ========================================================
    # LEFT SIDE
    # ========================================================

    with left:
        st.markdown(
            '<div class="brand-box"><div class="circle-a"></div><div class="circle-b"></div><div style="position:relative; z-index:2; display:flex; align-items:center; gap:14px;"><div class="brand-logo">🧭</div><div style="font-size:1.05rem; font-weight:750; color:white;">Career Companion</div></div><div class="eyebrow">✦ &nbsp; YOUR CAREER, YOUR DIRECTION</div><div class="main-headline">Build the career<span>you deserve.</span></div><div class="brand-description">Find the roles that truly fit you, bridge any skills gap with confidence, polish your story, and take the next step toward a future you’re excited about.</div><div class="feature-container"><div class="feature">✦ Personalized Guidance</div><div class="feature">◈ Smart Job Matching</div><div class="feature">◎ Skills Insights</div></div><div style="position:relative; z-index:2; display:flex; justify-content:space-between; margin-top:150px; color:rgba(255,255,255,0.55); font-size:0.70rem;"><div>© 2026 <strong style="color:white;">Career Companion</strong></div><div>Built for your next chapter</div></div></div>',
            unsafe_allow_html=True,
        )

    # ========================================================
    # RIGHT SIDE
    # ========================================================

    with right:

        st.markdown(
            """
            <div class="auth-title">
                <h1>Welcome back</h1>
                <p>Sign in to continue your career journey, or create an account to get started.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_signup = st.tabs(["🔑  Log In", "✨  Create Account"])

        # ====================================================
        # LOGIN
        # ====================================================

        with tab_login:

            st.write("")

            login_user = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username_input",
            )

            login_pass = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password_input",
            )

            if st.button(
                "Continue to Career Companion  →",
                type="primary",
                use_container_width=True,
                key="login_btn",
            ):

                if not login_user or not login_pass:

                    st.error("Please enter your username and password.")

                else:

                    user_data = authenticate_user(
                        login_user.strip(),
                        login_pass,
                    )

                    if user_data:

                        st.session_state["authenticated"] = True

                        st.session_state["user_id"] = user_data["user_id"]

                        st.session_state["user_name"] = user_data.get(
                            "name", ""
                        )

                        st.success("Welcome back! Opening your workspace...")

                        st.rerun()

                    else:

                        st.error("Invalid username or password.")

        # ====================================================
        # SIGN UP
        # ====================================================

        with tab_signup:

            st.write("")

            reg_user = st.text_input(
                "Username",
                placeholder="Choose a unique username",
                key="reg_username_input",
            )

            reg_name = st.text_input(
                "Full Name",
                placeholder="Enter your full name",
                key="reg_name_input",
            )

            reg_pass = st.text_input(
                "Password",
                type="password",
                placeholder="Create a password",
                key="reg_password_input",
            )

            reg_pass_confirm = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Re-enter your password",
                key="reg_confirm_input",
            )

            if st.button(
                "Create My Account  →",
                type="primary",
                use_container_width=True,
                key="signup_btn",
            ):

                if (
                    not reg_user
                    or not reg_name
                    or not reg_pass
                    or not reg_pass_confirm
                ):

                    st.error("Please complete all fields.")

                elif reg_pass != reg_pass_confirm:

                    st.error("Your passwords do not match.")

                elif len(reg_pass) < 6:

                    st.error("Password must be at least 6 characters.")

                else:

                    success = register_user(
                        reg_user.strip(),
                        reg_name.strip(),
                        reg_pass,
                    )

                    if success:

                        st.success(
                            "Account created successfully! You can now log in."
                        )

                    else:

                        st.error("That username is already taken.")

        # ====================================================
        # FOOTER
        # ====================================================

        st.markdown(
            """
            <div class="auth-footer">
                By continuing, you're taking the next step
                toward <strong>your career goals.</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return False