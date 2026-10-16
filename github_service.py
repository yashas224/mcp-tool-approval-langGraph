import os
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import HTTPException
import requests
load_dotenv()

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
SESSION_SECRET = os.environ["SESSION_SECRET"]
REDIRECT_URI = "http://127.0.0.1:8000/callback/"


def build_github_authorization_url(
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "read:user",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return "https://github.com/login/oauth/authorize?" + urlencode(params)


def get_github_user(token: str):
    response = requests.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub profile")

    return response.json()


def exchange_code(
    code: str,
    verifier: str,
    user_id:str
):
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="GitHub token exchange failed")

    data = response.json()

    if "access_token" not in data:
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")

    access_token=data["access_token"]

    return access_token
