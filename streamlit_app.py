from urllib.parse import urlencode

import requests
import streamlit as st

CHAT_API_URL = "http://127.0.0.1:8000/chat"
RESUME_API_URL = "http://127.0.0.1:8000/resume"
GITHUB_AUTH_URL = "http://127.0.0.1:8000/github-auth"
LATEST_MESSAGES_URL = "http://127.0.0.1:8000/conversation/latest"
DELETE_CHECKPOINT_URL = "http://127.0.0.1:8000/delete-checkpoint"
REQUEST_TIMEOUT_SECONDS = 120

st.set_page_config(
    page_title="RepoPilot",
    page_icon="🐙",
    layout="centered",
)

st.markdown(
    """
    <style>
    .hero {
        padding: 1.6rem 1.8rem;
        border-radius: 16px;
        background: linear-gradient(135deg, #24292f 0%, #2f3b52 55%, #6e40c9 100%);
        color: #ffffff;
        margin-bottom: 1.4rem;
        box-shadow: 0 8px 24px rgba(36, 41, 47, 0.25);
    }
    .hero h1 {
        color: #ffffff;
        font-size: 2.2rem;
        margin: 0;
        padding: 0;
    }
    .hero p {
        color: #d0d7de;
        margin: 0.35rem 0 0 0;
        font-size: 1.02rem;
    }
    .hero .chips {
        margin-top: 0.9rem;
    }
    .hero .chip {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        margin: 0 0.35rem 0.35rem 0;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.25);
        font-size: 0.8rem;
        color: #ffffff;
    }
    .sidebar-brand {
        font-size: 1.35rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sidebar-caption {
        color: #8b949e;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }
    div[data-testid="stChatMessage"] {
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>🐙 RepoPilot</h1>
        <p>Your GitHub co-pilot — you stay in control.</p>
        <div class="chips">
            <span class="chip">🔐 GitHub OAuth</span>
            <span class="chip">✅ Human-in-the-loop approvals</span>
            <span class="chip">🧮 Math</span>
            <span class="chip">🌐 Web search</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_interrupt" not in st.session_state:
    st.session_state.pending_interrupt = None


def add_message(role: str, content: str) -> None:
    st.session_state.messages.append(
        {
            "role": role,
            "content": content,
        }
    )


def validate_user_id(value: str) -> str | None:
    try:
        if len(str(value)) > 3:
            return value
    except (ValueError, AttributeError):
        return None


def call_resume(user_id: str, action: str) -> dict:
    response = requests.post(
        RESUME_API_URL,
        json={
            "user_id": user_id,
            "query": action,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def clear_agent_context(user_id: str) -> dict:
    response = requests.delete(
        DELETE_CHECKPOINT_URL,
        params={"user_id": user_id},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


github_auth_status = st.query_params.get("github_auth")
callback_user_id = st.query_params.get("user_id")
if github_auth_status == "complete" and callback_user_id:
    st.session_state.user_id = callback_user_id
    try:
        response = requests.get(
            LATEST_MESSAGES_URL,
            params={"user_id": callback_user_id},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        st.session_state.latest_conversation = response.json()
        st.session_state.pending_interrupt = None
        st.session_state.pop("github_app_install_clicked", None)
        st.query_params.clear()
    except requests.exceptions.RequestException as error:
        st.error(f"Could not restore the conversation: {error}")
elif github_auth_status == "failed":
    st.error("GitHub authorization failed or was cancelled.")
    st.query_params.clear()


st.sidebar.markdown(
    '<div class="sidebar-brand">🐙 RepoPilot</div>'
    '<div class="sidebar-caption">Session settings</div>',
    unsafe_allow_html=True,
)

user_id_input = st.sidebar.text_input(
    "🪪 User ID",
    value=st.session_state.user_id,
    placeholder="Enter a UUID",
    help="Use the same UUID to keep the same  conversation and resume approvals.",
)

valid_user_id = validate_user_id(user_id_input)

if valid_user_id:
    st.session_state.user_id = valid_user_id
    st.sidebar.success("Connected as a valid user", icon="✅")
else:
    st.sidebar.warning(
        "Enter a valid user_id to start or resume a conversation.", icon="⚠️"
    )

st.sidebar.divider()
st.sidebar.markdown(
    "**What I can do**\n"
    "- 📂 Browse repos, issues & PRs\n"
    "- ✍️ Create or update GitHub content\n"
    "- 🧮 Solve math problems\n"
    "- 🌐 Search the web\n\n"
    "Every sensitive action waits for your **approval**."
)
st.sidebar.divider()
if st.sidebar.button("🧹 Clear chat", use_container_width=True):
    st.session_state.messages = []
    st.session_state.pending_interrupt = None
    st.rerun()

if st.sidebar.button(
    "♻️ Clear agent context",
    use_container_width=True,
    disabled=valid_user_id is None,
    help="Deletes the agent's saved memory for this user ID.",
):
    try:
        clear_agent_context(valid_user_id)
        st.session_state.messages = []
        st.session_state.pending_interrupt = None
        st.session_state.pop("latest_conversation", None)
        st.session_state.pop("github_app_install_clicked", None)
        st.session_state.context_cleared = True
        st.rerun()
    except requests.exceptions.RequestException as error:
        st.sidebar.error(f"Could not clear agent context: {error}")

if st.session_state.pop("context_cleared", False):
    st.toast("Agent context cleared", icon="✅")

AVATARS = {"user": "🧑‍💻", "assistant": "🐙"}

latest_conversation = st.session_state.get("latest_conversation")
if latest_conversation:
    with st.container(border=True):
        st.subheader("🔐 GitHub Authentication")
        st.write(latest_conversation.get("result") or "No user message found.")
        install_url = latest_conversation.get("install_url")
        if install_url:
            st.info("Proceed to install the GitHub App.", icon="📦")
            if st.button("Install GitHub App"):
                st.session_state.github_app_install_clicked = True
            if st.session_state.get("github_app_install_clicked"):
                st.link_button("Open GitHub App installation ↗", install_url)
                st.caption("Once installed, rerun your GitHub query below.")
        github_query = st.text_input(
            "GitHub query",
            value=str(latest_conversation.get("github_query") or ""),
        )
        if st.button(
            "🔁 Rerun GitHub query",
            type="primary",
            disabled=valid_user_id is None or not github_query.strip(),
        ):
            st.session_state.queued_prompt = github_query.strip()

if not st.session_state.messages and not st.session_state.pending_interrupt:
    st.markdown("##### 💡 Try asking")
    suggestions = [
        "List my GitHub repositories",
        "Show open issues in my latest repo",
        "What is 37 * 49 + 12?",
        "Search the web for LangGraph news",
    ]
    suggestion_columns = st.columns(2)
    for index, suggestion in enumerate(suggestions):
        with suggestion_columns[index % 2]:
            if st.button(
                suggestion,
                key=f"suggestion_{index}",
                use_container_width=True,
                disabled=valid_user_id is None,
            ):
                st.session_state.queued_prompt = suggestion

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=AVATARS.get(message["role"])):
        st.markdown(message["content"])


if st.session_state.pending_interrupt:
    pending_interrupt = st.session_state.pending_interrupt
    is_github_auth = (
        isinstance(pending_interrupt, dict)
        and pending_interrupt.get("MCP Server") == "GitHub"
    )

    if is_github_auth:
        st.warning("GitHub authorization is required to continue.", icon="🔐")
    else:
        st.warning("This action requires your approval.", icon="🛑")

    with st.expander("🔍 Pending tool action", expanded=True):
        st.json(pending_interrupt)

    if is_github_auth:
        # The browser must open /github-auth itself so the OAuth session
        # cookie is stored in the browser, not in the Streamlit server.
        st.link_button(
            "🔑 Authorize GitHub ↗",
            f"{GITHUB_AUTH_URL}?{urlencode({'user_id': valid_user_id or ''})}",
            type="primary",
            disabled=valid_user_id is None,
        )
    else:
        accept_column, reject_column = st.columns(2)

        with accept_column:
            accept = st.button(
                "✅ Accept",
                type="primary",
                use_container_width=True,
                disabled=valid_user_id is None,
            )

        with reject_column:
            reject = st.button(
                "❌ Reject",
                use_container_width=True,
                disabled=valid_user_id is None,
            )

    if not is_github_auth and (accept or reject):
        action = "approved" if accept else "reject"

        with st.spinner("Sending your decision..."):
            try:
                data = call_resume(valid_user_id, action)

                if data.get("status") == "interrupt":
                    st.session_state.pending_interrupt = data.get("interrupt")

                elif data.get("status") == "completed":
                    st.session_state.pending_interrupt = None

                    answer = data.get(
                        "result",
                        "The request completed without a response message.",
                    )
                    add_message("assistant", answer)

                else:
                    st.session_state.pending_interrupt = None
                    add_message("assistant", f"Unexpected API response: {data}")

                st.rerun()

            except requests.exceptions.RequestException as error:
                st.error(f"Could not resume the request: {error}")

else:
    prompt = st.chat_input(
        "Ask RepoPilot about your repos, math, or the web...",
        disabled=valid_user_id is None,
    ) or st.session_state.pop("queued_prompt", None)

    if prompt:
        add_message("user", prompt)

        with st.chat_message("user", avatar=AVATARS["user"]):
            st.markdown(prompt)

        with (
            st.chat_message("assistant", avatar=AVATARS["assistant"]),
            st.spinner("RepoPilot is thinking..."),
        ):
            try:
                response = requests.post(
                    CHAT_API_URL,
                    json={
                        "user_id": valid_user_id,
                        "query": prompt,
                    },
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()

                data = response.json()
                status = data.get("status")

                if status == "completed":
                    answer = data.get(
                        "result",
                        "The request completed without a response message.",
                    )
                    st.markdown(answer)
                    add_message("assistant", answer)

                elif status == "interrupt":
                    st.session_state.pending_interrupt = data.get("interrupt")
                    st.markdown("This action needs your approval.")
                    st.rerun()

                else:
                    answer = f"Unexpected API response: {data}"
                    st.markdown(answer)
                    add_message("assistant", answer)

            except requests.exceptions.RequestException as error:
                answer = f"API error: {error}"
                st.markdown(answer)
                add_message("assistant", answer)
