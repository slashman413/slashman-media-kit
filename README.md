# slashman-media-kit

Shared media helpers for the video / Shorts pipelines
(`pixabay-shorts-bot`, `kling-shorts-bot`, `ai-digital-human-pipeline`,
`hermes-shortsgen`) — extracted so the same code isn't copy-pasted per repo.

## Install

```bash
pip install "slashman-media-kit @ git+https://github.com/slashman413/slashman-media-kit.git"
```

## Modules

### `media_kit.youtube`
YouTube OAuth + resumable upload. Credential lookup accepts **either**
`YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` **or**
`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, so no repo needs to rename secrets.

```python
from media_kit.youtube import upload_video_from_env
video_id = upload_video_from_env(video_path, title, description, tags, config, token_dir)
```

Also exposes `get_authenticated_service(...)` and `upload_video(service, ...)`
for callers that manage auth themselves.

## Roadmap
- `media_kit.discord` — unified Discord notify (from kling's `discord_notify.py`).
- `YouTubeUploader` class API (kling parity).

_author: claude-code_
