import requests

import streamlit as st

CHAT_API_URL = "http://127.0.0.1:8000/chat"
RESUME_API_URL = "http://127.0.0.1:8000/resume"
GITHUB_AUTH_URL = "http://127.0.0.1:8000/github-auth"
LATEST_MESSAGES_URL = "http://127.0.0.1:8000/conversation/latest"
REQUEST_TIMEOUT_SECONDS = 120

st.set_page_config(
    page_title="Approval Assistant",
    page_icon="AI",
)

st.title("Approval Assistant")

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
        st.session_state.pop("github_authorization_url", None)
        st.query_params.clear()
    except requests.exceptions.RequestException as error:
        st.error(f"Could not restore the conversation: {error}")
elif github_auth_status == "failed":
    st.error("GitHub authorization failed or was cancelled.")
    st.query_params.clear()


user_id_input = st.sidebar.text_input(
    "User ID",
    value=st.session_state.user_id,
    placeholder="Enter a UUID",
    help="Use the same UUID to keep the same  conversation and resume approvals.",
)

valid_user_id = validate_user_id(user_id_input)

if valid_user_id:
    st.session_state.user_id = valid_user_id
    st.sidebar.success("Valid user ID")
else:
    st.sidebar.warning("Enter a valid user_id to start or resume a conversation.")

latest_conversation = st.session_state.get("latest_conversation")
if latest_conversation:
    st.markdown("**Latest user message:**")
    st.write(latest_conversation.get("latest_human") or "No user message found.")
    st.markdown("**Latest AI response:**")
    st.write(latest_conversation.get("latest_ai") or "No AI response found.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if st.session_state.pending_interrupt:
    pending_interrupt = st.session_state.pending_interrupt
    is_github_auth = (
        isinstance(pending_interrupt, dict)
        and pending_interrupt.get("MCP Server") == "GitHub"
    )

    if is_github_auth:
        st.warning("GitHub authorization is required to continue.")
    else:
        st.warning("This action requires your approval.")

    with st.expander("Pending tool action", expanded=True):
        st.json(pending_interrupt)

    if is_github_auth:
        if st.button("Authorize GitHub", disabled=valid_user_id is None):
            try:
                response = requests.get(
                    GITHUB_AUTH_URL,
                    headers={"user-id": valid_user_id},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                st.session_state.github_authorization_url = response.json()[
                    "authorization_url"
                ]
            except requests.exceptions.RequestException as error:
                st.error(f"Could not start GitHub authorization: {error}")

        authorization_url = st.session_state.get("github_authorization_url")
        if authorization_url:
            st.link_button("Continue to GitHub", authorization_url)
    else:
        accept_column, reject_column = st.columns(2)

        with accept_column:
            accept = st.button(
                "Accept",
                type="primary",
                use_container_width=True,
                disabled=valid_user_id is None,
            )

        with reject_column:
            reject = st.button(
                "Reject",
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
        "Ask about math, web search, or GitHub...",
        disabled=valid_user_id is None,
    )

    if prompt:
        add_message("user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"), st.spinner("Working..."):
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
