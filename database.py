import json
import os
import bcrypt
import streamlit as st

from dotenv import load_dotenv

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    TIMESTAMP,
    create_engine,
    text,
    inspect,
)

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


def get_database_url():
    """Safely fetch DATABASE_URL from .env or st.secrets."""
    url = os.getenv("DATABASE_URL")
    if not url:
        try:
            # st.secrets is a mapping; check if key exists
            if "DATABASE_URL" in st.secrets:
                url = st.secrets["DATABASE_URL"]
        except Exception as e:
            print(f"DEBUG: Error accessing st.secrets: {e}")
            url = None
            
    return url


DATABASE_URL = get_database_url()


# ============================================================
# DATABASE ENGINE
# ============================================================

@st.cache_resource
def get_db_engine():
    """Create the SQLAlchemy PostgreSQL engine."""

    if not DATABASE_URL:
        st.error(
            "DATABASE_URL is not set. "
            "Please check your .env file or st.secrets."
        )
        return None

    url = DATABASE_URL

    if url.startswith("postgres://"):
        url = url.replace(
            "postgres://",
            "postgresql://",
            1,
        )

    return create_engine(
        url,
        pool_pre_ping=True,
    )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():
    """Create required database tables if they don't exist."""

    engine = get_db_engine()

    if not engine:
        return

    metadata = MetaData()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    Table(
        "users",
        metadata,

        Column(
            "user_id",
            String(100),
            primary_key=True,
        ),

        Column(
            "name",
            String(255),
        ),

        # CURRENT_ROLE is a PostgreSQL keyword.
        # SQLAlchemy will quote it correctly.
        Column(
            "current_role",
            String(255),
        ),

        Column(
            "experience",
            String(255),
        ),

        Column(
            "target_role",
            String(255),
        ),

        Column(
            "skills",
            Text,
        ),

        Column(
            "summary",
            Text,
        ),

        Column(
            "password_hash",
            Text,
        ),

        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=func.now(),
        ),
    )

    # --------------------------------------------------------
    # CHAT HISTORY
    # --------------------------------------------------------

    Table(
        "chat_history",
        metadata,

        Column(
            "id",
            Integer,
            primary_key=True,
            autoincrement=True,
        ),

        Column(
            "user_id",
            String(100),
            ForeignKey(
                "users.user_id",
                ondelete="CASCADE",
            ),
        ),

        Column(
            "role",
            String(50),
            nullable=False,
        ),

        Column(
            "content",
            Text,
            nullable=False,
        ),

        Column(
            "sentiment_score",
            Float,
        ),

        Column(
            "emotional_label",
            String(100),
        ),

        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=func.now(),
        ),
    )

    # --------------------------------------------------------
    # INTERVIEW SESSIONS
    # --------------------------------------------------------

    Table(
        "interview_sessions",
        metadata,

        Column(
            "session_id",
            Integer,
            primary_key=True,
            autoincrement=True,
        ),

        Column(
            "user_id",
            String(100),
            ForeignKey(
                "users.user_id",
                ondelete="CASCADE",
            ),
        ),

        Column(
            "target_role",
            String(255),
            nullable=False,
        ),

        Column(
            "company_name",
            String(255),
        ),

        Column(
            "transcript",
            JSONB,
            nullable=False,
        ),

        Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=func.now(),
        ),
    )

    metadata.create_all(bind=engine)


# ============================================================
# PASSWORD FUNCTIONS
# ============================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""

    salt = bcrypt.gensalt()

    return bcrypt.hashpw(
        password.encode("utf-8"),
        salt,
    ).decode("utf-8")


def check_password(
    password: str,
    hashed_password: str,
) -> bool:
    """Verify a password against a bcrypt hash."""

    if not password or not hashed_password:
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ============================================================
# REGISTER USER
# ============================================================

def register_user(
    username: str,
    name: str,
    password: str,
) -> bool:

    engine = get_db_engine()

    if not engine:
        return False

    clean_username = username.strip().lower()

    if not clean_username or not password:
        return False

    hashed_pw = hash_password(password)

    check_query = """
        SELECT user_id
        FROM users
        WHERE LOWER(user_id) = :user_id;
    """

    insert_query = """
        INSERT INTO users (
            user_id,
            name,
            password_hash
        )
        VALUES (
            :user_id,
            :name,
            :password_hash
        );
    """

    try:

        with engine.begin() as conn:

            existing = conn.execute(
                text(check_query),
                {
                    "user_id": clean_username,
                },
            ).first()

            if existing:

                print(
                    f"[AUTH] Registration failed: "
                    f"Username '{clean_username}' already exists."
                )

                return False

            conn.execute(
                text(insert_query),
                {
                    "user_id": clean_username,
                    "name": name.strip(),
                    "password_hash": hashed_pw,
                },
            )

            return True

    except Exception as e:

        print(
            f"[AUTH ERROR] Failed to register "
            f"user '{clean_username}': {e}"
        )

        return False


# ============================================================
# AUTHENTICATE USER
# ============================================================

def authenticate_user(
    username: str,
    password: str,
) -> dict | None:

    engine = get_db_engine()

    if not engine:
        return None

    clean_username = username.strip().lower()

    query = """
        SELECT
            user_id,
            name,
            password_hash
        FROM users
        WHERE LOWER(user_id) = :user_id;
    """

    try:

        with engine.connect() as conn:

            result = conn.execute(
                text(query),
                {
                    "user_id": clean_username,
                },
            ).mappings().first()

            if result:

                stored_hash = result.get(
                    "password_hash"
                )

                if stored_hash and check_password(
                    password,
                    stored_hash,
                ):

                    return dict(result)

    except Exception as e:

        print(
            f"[AUTH ERROR] Login failed: {e}"
        )

    return None


# ============================================================
# SAVE USER PROFILE
# ============================================================

def save_user_profile(
    user_id: str,
    profile_data: dict,
):
    """Save or update a user's career profile."""

    engine = get_db_engine()

    if not engine:
        return False

    query = """
        INSERT INTO users (
            user_id,
            name,
            "current_role",
            experience,
            target_role,
            skills,
            summary
        )

        VALUES (
            :user_id,
            :name,
            :current_role,
            :experience,
            :target_role,
            :skills,
            :summary
        )

        ON CONFLICT (user_id)

        DO UPDATE SET

            name = EXCLUDED.name,

            "current_role" =
                EXCLUDED."current_role",

            experience =
                EXCLUDED.experience,

            target_role =
                EXCLUDED.target_role,

            skills =
                EXCLUDED.skills,

            summary =
                EXCLUDED.summary;
    """

    try:

        with engine.begin() as conn:

            conn.execute(
                text(query),
                {
                    "user_id": user_id,

                    "name": profile_data.get(
                        "name",
                        "",
                    ),

                    "current_role": profile_data.get(
                        "current_role",
                        "",
                    ),

                    "experience": profile_data.get(
                        "experience",
                        "",
                    ),

                    "target_role": profile_data.get(
                        "target_role",
                        "",
                    ),

                    "skills": profile_data.get(
                        "skills",
                        "",
                    ),

                    "summary": profile_data.get(
                        "summary",
                        "",
                    ),
                },
            )

        return True

    except Exception as e:

        print(
            f"[PROFILE ERROR] Failed to save profile: {e}"
        )

        return False


# ============================================================
# LOAD USER PROFILE
# ============================================================

def load_user_profile(
    user_id: str,
) -> dict:

    engine = get_db_engine()

    if not engine:
        return {}

    query = """
        SELECT
            name,
            "current_role",
            experience,
            target_role,
            skills,
            summary

        FROM users

        WHERE user_id = :user_id;
    """

    try:

        with engine.connect() as conn:

            result = conn.execute(
                text(query),
                {
                    "user_id": user_id,
                },
            ).mappings().first()

            if result:
                return dict(result)

    except Exception as e:

        print(
            f"[PROFILE ERROR] Failed to load profile: {e}"
        )

    return {}


# ============================================================
# INTERVIEW SESSION
# ============================================================

def save_interview_session(
    user_id: str,
    target_role: str,
    company_name: str,
    transcript: list,
):

    engine = get_db_engine()

    if not engine:
        return False

    query = """
        INSERT INTO interview_sessions (
            user_id,
            target_role,
            company_name,
            transcript
        )

        VALUES (
            :user_id,
            :target_role,
            :company_name,
            :transcript
        );
    """

    try:

        with engine.begin() as conn:

            conn.execute(
                text(query),
                {
                    "user_id": user_id,
                    "target_role": target_role,
                    "company_name": company_name,
                    "transcript": json.dumps(
                        transcript
                    ),
                },
            )

        return True

    except Exception as e:

        print(
            f"[INTERVIEW ERROR] "
            f"Failed to save session: {e}"
        )

        return False


# ============================================================
# CHAT HISTORY
# ============================================================

def save_chat_message(
    user_id: str,
    role: str,
    content: str,
    sentiment_score: float = 0.0,
    emotional_label: str = "Neutral",
):

    engine = get_db_engine()

    if not engine:
        return False

    query = """
        INSERT INTO chat_history (
            user_id,
            role,
            content,
            sentiment_score,
            emotional_label
        )

        VALUES (
            :user_id,
            :role,
            :content,
            :sentiment_score,
            :emotional_label
        );
    """

    try:

        with engine.begin() as conn:

            conn.execute(
                text(query),
                {
                    "user_id": user_id,
                    "role": role,
                    "content": content,
                    "sentiment_score": sentiment_score,
                    "emotional_label": emotional_label,
                },
            )

        return True

    except Exception as e:

        print(
            f"[CHAT ERROR] "
            f"Failed to save chat message: {e}"
        )

        return False


def load_chat_history(
    user_id: str,
) -> list:

    engine = get_db_engine()

    if not engine:
        return []

    query = """
        SELECT
            role,
            content

        FROM chat_history

        WHERE user_id = :user_id

        ORDER BY id ASC;
    """

    try:

        with engine.connect() as conn:

            results = conn.execute(
                text(query),
                {
                    "user_id": user_id,
                },
            ).mappings().all()

            return [
                dict(row)
                for row in results
            ]

    except Exception as e:

        print(
            f"[CHAT ERROR] "
            f"Failed to load chat history: {e}"
        )

        return []