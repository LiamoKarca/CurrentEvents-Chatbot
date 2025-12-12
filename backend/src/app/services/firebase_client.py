# -*- coding: utf-8-sig -*-
"""
Firebase Admin / Firestore initialization helpers.

This module centralizes how we bootstrap the Firebase Admin SDK so that the
rest of the application can simply call ``get_firestore_client()`` without
duplicating credential parsing logic.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict

import firebase_admin
from firebase_admin import credentials, firestore

_firestore_client: firestore.Client | None = None


def _load_service_account() -> Dict[str, Any]:
    """Load service account JSON from environment variables.

    Supports multiple configuration styles:
        - FIREBASE_SERVICE_ACCOUNT_FILE: path to a JSON file
        - FIREBASE_SERVICE_ACCOUNT_JSON: raw JSON string
        - FIREBASE_SERVICE_ACCOUNT_BASE64: base64-encoded JSON string
        - FIREBASE_PROJECT_ID + FIREBASE_CLIENT_EMAIL + FIREBASE_PRIVATE_KEY + ...

    Returns:
        Parsed JSON dict suitable for firebase_admin.credentials.Certificate.
    """
    path = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")
    if path:
        return path  # type: ignore[return-value]

    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        data = json.loads(raw_json)
        if isinstance(data, dict):
            return data

    b64_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
    if b64_json:
        decoded = base64.b64decode(b64_json)
        data = json.loads(decoded.decode("utf-8"))
        if isinstance(data, dict):
            return data

    # Fallback: build JSON from individual env vars
    project_id = os.getenv("FIREBASE_PROJECT_ID")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
    private_key_id = os.getenv("FIREBASE_PRIVATE_KEY_ID")
    client_id = os.getenv("FIREBASE_CLIENT_ID")
    token_uri = os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token")
    auth_uri = os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
    auth_provider_cert_url = os.getenv(
        "FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"
    )
    client_cert_url = os.getenv("FIREBASE_CLIENT_X509_CERT_URL")

    if project_id and private_key and client_email:
        private_key = private_key.replace("\\n", "\n")
        return {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id or "",
            "private_key": private_key,
            "client_email": client_email,
            "client_id": client_id or "",
            "token_uri": token_uri,
            "auth_uri": auth_uri,
            "auth_provider_x509_cert_url": auth_provider_cert_url,
            "client_x509_cert_url": client_cert_url or "",
        }

    raise RuntimeError(
        "Firebase credentials not configured. "
        "Set FIREBASE_SERVICE_ACCOUNT_BASE64 (recommended) or other supported env vars."
    )


def get_firestore_client() -> firestore.Client:
    """Get a singleton Firestore client instance."""
    global _firestore_client
    if _firestore_client:
        return _firestore_client

    sa_info = _load_service_account()
    if isinstance(sa_info, str):
        cred = credentials.Certificate(sa_info)
    else:
        # firebase_admin expects actual newline characters in the private key.
        pk = sa_info.get("private_key")
        if isinstance(pk, str):
            sa_info = {**sa_info, "private_key": pk.replace("\\n", "\n")}
        cred = credentials.Certificate(sa_info)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    else:
        # Ensure default app exists (avoid re-initializing with different options).
        firebase_admin.get_app()

    _firestore_client = firestore.client()
    return _firestore_client


__all__ = ["get_firestore_client"]