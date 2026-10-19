import base64
import hashlib
import secrets


def generate_pkce():
    verifier = secrets.token_urlsafe(32)

    digest = hashlib.sha256(verifier.encode("ascii")).digest()

    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return verifier, challenge
