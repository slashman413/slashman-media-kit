"""slashman-media-kit: shared media helpers for the video/Shorts pipelines."""

from .youtube import (  # noqa: F401
    SCOPES,
    TOKEN_FILE,
    CLIENT_SECRET_FILE,
    REDIRECT_URI,
    resolve_oauth_env,
    get_authenticated_service,
    upload_video,
    upload_video_from_env,
    YouTubeUploader,
)

__version__ = "0.1.0"
