"""
slashman-media-kit — YouTube uploader (shared).

Consolidated from the per-repo copies that used to live in
pixabay-shorts-bot / kling-shorts-bot / ai-digital-human-pipeline.
Behaviour is identical to the original pixabay implementation; the only
change is that credential lookup accepts BOTH the `YOUTUBE_*` and the
`GOOGLE_*` environment-variable names, so every repo can adopt it without
renaming any secrets.

Handles OAuth 2.0 authentication and video upload to YouTube.
"""

import os
import json
import pickle  # noqa: F401  (parity with kling's original module)
import logging
import random
import http.client  # noqa: F401  (kept for parity with original module)
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "youtube_token.json"
CLIENT_SECRET_FILE = "client_secret.json"

# Redirect URI for OAuth desktop flow
REDIRECT_URI = "http://localhost"


def resolve_oauth_env():
    """Return (client_id, client_secret) from env, accepting either the
    YOUTUBE_* or the GOOGLE_* naming scheme. Either may be None."""
    client_id = os.getenv("YOUTUBE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET")
    return client_id, client_secret


def get_authenticated_service(
    client_id: str,
    client_secret: str,
    token_path: Path,
    client_secret_path: Optional[Path] = None,
):
    """
    Get an authenticated YouTube API service.
    Uses stored refresh token if available, otherwise runs OAuth flow.
    """
    credentials = None

    # Try loading saved token
    if token_path.exists():
        logger.info(f"Loading saved token from {token_path}")
        with open(token_path, "r") as f:
            token_data = json.load(f)
        credentials = Credentials.from_authorized_user_info(token_data, SCOPES)

    # If no valid credentials, run OAuth flow
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            logger.info("Token expired, refreshing...")
            credentials.refresh(Request())
        else:
            logger.info("No valid token found. Running OAuth flow...")
            credentials = _run_oauth_flow(
                client_id, client_secret,
                client_secret_path, token_path,
            )
        # Save token for next run
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            json.dump(
                {
                    "token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "token_uri": credentials.token_uri,
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "scopes": credentials.scopes,
                },
                f,
            )
        logger.info(f"Token saved to {token_path}")

    return build("youtube", "v3", credentials=credentials)


def _run_oauth_flow(
    client_id: str,
    client_secret: str,
    client_secret_path: Optional[Path],
    token_path: Path,
) -> Credentials:
    """
    Run the OAuth 2.0 desktop flow for YouTube upload.
    First tries using a client_secret.json file if available,
    otherwise constructs credentials from env variables.
    """
    if client_secret_path and client_secret_path.exists():
        logger.info("Using client_secret.json for OAuth flow")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path), SCOPES
        )
    else:
        # Construct client config from environment variables
        logger.info("Using env variable credentials for OAuth flow")
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    # Run local server flow (opens browser for user to authorize)
    credentials = flow.run_local_server(
        port=random.randint(8080, 8099),
        prompt="consent",
        authorization_prompt_message="",
    )
    return credentials


def upload_video(
    service,
    video_path: Path,
    title: str,
    description: str,
    tags: list,
    category_id: str = "22",
    privacy_status: str = "public",
) -> str:
    """
    Upload a video to YouTube.
    Returns the video ID.
    """
    body = {
        "snippet": {
            "title": title[:100],  # YouTube title max 100 chars
            "description": description[:5000],  # YouTube description max 5000 chars
            "tags": tags[:500],  # YouTube tags max 500 chars total
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=64 * 1024 * 1024,  # 64MB chunks for resume
        resumable=True,
    )

    logger.info(f"Uploading video: {title}")
    logger.info(f"  File size: {video_path.stat().st_size / 1e6:.1f} MB")

    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    progress = 0
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            if pct >= progress + 10:  # Log every 10%
                logger.info(f"  Upload progress: {pct}%")
                progress = pct

    video_id = response.get("id")
    video_url = f"https://youtu.be/{video_id}"
    logger.info(f"Upload complete! Video ID: {video_id}")
    logger.info(f"URL: {video_url}")

    return video_id


def upload_video_from_env(
    video_path: Path,
    title: str,
    description: str,
    tags: list,
    config: dict,
    token_dir: Path,
    client_secret_path: Optional[Path] = None,
) -> str:
    """
    Convenience function: load OAuth credentials from env variables,
    authenticate, and upload. Accepts YOUTUBE_* or GOOGLE_* env names.
    """
    client_id, client_secret = resolve_oauth_env()

    if not client_id or not client_secret:
        raise ValueError(
            "YouTube OAuth credentials not found. Set YOUTUBE_CLIENT_ID and "
            "YOUTUBE_CLIENT_SECRET (or GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) "
            "environment variables."
        )

    token_path = token_dir / TOKEN_FILE
    service = get_authenticated_service(
        client_id=client_id,
        client_secret=client_secret,
        token_path=token_path,
        client_secret_path=client_secret_path,
    )

    yt_conf = config.get("youtube", {})
    category_id = yt_conf.get("category", "22")
    privacy_status = yt_conf.get("privacy", "public")

    video_id = upload_video(
        service=service,
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        category_id=category_id,
        privacy_status=privacy_status,
    )

    return video_id


class YouTubeUploader:
    """Upload videos to YouTube via a refresh-token flow (ported verbatim from
    kling-shorts-bot). Credential env names accept YOUTUBE_* or GOOGLE_*."""

    def __init__(self):
        self.client_id, self.client_secret = resolve_oauth_env()
        self.refresh_token = (
            os.environ.get("YOUTUBE_REFRESH_TOKEN")
            or os.environ.get("GOOGLE_REFRESH_TOKEN")
        )
        self.token_file = self._get_token_path()

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError(
                "YouTube OAuth not configured.\n"
                "Required env vars (YOUTUBE_* or GOOGLE_*):\n"
                "  YOUTUBE_CLIENT_ID\n"
                "  YOUTUBE_CLIENT_SECRET\n"
                "  YOUTUBE_REFRESH_TOKEN\n"
            )

        self.service = self._authenticate()

    def _get_token_path(self) -> Path:
        return Path(os.environ.get("YOUTUBE_TOKEN_PATH", "./youtube_token.pickle"))

    def _authenticate(self):
        """Authenticate with YouTube using OAuth 2.0 refresh token."""
        creds = Credentials(
            None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list,
        category_id: str = "24",  # 24 = Entertainment (Shorts-friendly)
        privacy_status: str = "public",
    ) -> Optional[str]:
        """Upload a video to YouTube Shorts. Returns the video ID."""
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "categoryId": category_id,
                "defaultLanguage": "zh-TW",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_path,
            chunksize=1024 * 1024,
            resumable=True,
        )

        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YouTube] Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        print(f"[YouTube] Uploaded! Video ID: {video_id}")
        print(f"[YouTube] URL: https://youtube.com/watch?v={video_id}")
        return video_id

    def upload_shorts_batch(
        self, videos: list, shorts_prefix: str = "#Shorts"
    ) -> list:
        """Upload multiple videos as Shorts. Returns a list of video IDs."""
        video_ids = []
        for i, video in enumerate(videos):
            print(f"\n[YouTube] Uploading video {i+1}/{len(videos)}: {video['title']}")

            vid = self.upload_video(
                video_path=video["path"],
                title=f"{shorts_prefix} {video['title']}",
                description=video.get("description", ""),
                tags=video.get("tags", []),
            )
            if vid:
                video_ids.append(vid)

        return video_ids
