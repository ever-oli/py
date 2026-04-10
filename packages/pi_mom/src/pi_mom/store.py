"""Channel storage for Mom."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import aiofiles
import httpx


class Attachment:
    """Represents a file attachment."""

    def __init__(self, original: str, local: str):
        self.original = original
        self.local = local

    def to_dict(self) -> dict:
        return {"original": self.original, "local": self.local}


class LoggedMessage:
    """Represents a logged message."""

    def __init__(
        self,
        date: str,
        ts: str,
        user: str,
        text: str,
        attachments: list,
        is_bot: bool,
        user_name: str | None = None,
        display_name: str | None = None,
    ):
        self.date = date
        self.ts = ts
        self.user = user
        self.text = text
        self.attachments = attachments
        self.is_bot = is_bot
        self.user_name = user_name
        self.display_name = display_name

    def to_dict(self) -> dict:
        result = {
            "date": self.date,
            "ts": self.ts,
            "user": self.user,
            "text": self.text,
            "attachments": self.attachments,
            "isBot": self.is_bot,
        }
        if self.user_name:
            result["userName"] = self.user_name
        if self.display_name:
            result["displayName"] = self.display_name
        return result


class PendingDownload:
    """Represents a pending attachment download."""

    def __init__(self, channel_id: str, local_path: str, url: str):
        self.channel_id = channel_id
        self.local_path = local_path
        self.url = url


class ChannelStore:
    """Stores channel data and manages attachment downloads."""

    def __init__(self, working_dir: str, bot_token: str):
        self.working_dir = Path(working_dir)
        self.bot_token = bot_token
        self.pending_downloads: list[PendingDownload] = []
        self._is_downloading = False
        self._recently_logged: dict[str, float] = {}

        self.working_dir.mkdir(parents=True, exist_ok=True)

    def get_channel_dir(self, channel_id: str) -> Path:
        """Get or create the directory for a channel."""
        channel_dir = self.working_dir / channel_id
        channel_dir.mkdir(parents=True, exist_ok=True)
        return channel_dir

    def generate_local_filename(self, original_name: str, timestamp: str) -> str:
        """Generate a unique local filename for an attachment."""
        ts = int(float(timestamp) * 1000)
        sanitized = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_name)
        return f"{ts}_{sanitized}"

    def process_attachments(self, channel_id: str, files: list[dict], timestamp: str) -> list[dict]:
        """Process attachments from a Slack message event."""
        attachments = []

        for file in files:
            url = file.get("url_private_download") or file.get("url_private")
            if not url:
                continue
            if not file.get("name"):
                continue

            filename = self.generate_local_filename(file["name"], timestamp)
            local_path = f"{channel_id}/attachments/{filename}"

            attachments.append({"original": file["name"], "local": local_path})

            self.pending_downloads.append(
                PendingDownload(channel_id=channel_id, local_path=local_path, url=url)
            )

        asyncio.create_task(self._process_download_queue())
        return attachments

    async def log_message(self, channel_id: str, message: LoggedMessage) -> bool:
        """Log a message to the channel's log.jsonl."""
        dedupe_key = f"{channel_id}:{message.ts}"
        if dedupe_key in self._recently_logged:
            return False

        self._recently_logged[dedupe_key] = datetime.now().timestamp()

        log_path = self.get_channel_dir(channel_id) / "log.jsonl"
        async with aiofiles.open(log_path, "a") as f:
            await f.write(json.dumps(message.to_dict()) + "\n")
        return True

    async def log_bot_response(self, channel_id: str, text: str, ts: str) -> None:
        """Log a bot response."""
        message = LoggedMessage(
            date=datetime.now().isoformat(),
            ts=ts,
            user="bot",
            text=text,
            attachments=[],
            is_bot=True,
        )
        await self.log_message(channel_id, message)

    def get_last_timestamp(self, channel_id: str) -> str | None:
        """Get the timestamp of the last logged message."""
        log_path = self.working_dir / channel_id / "log.jsonl"
        if not log_path.exists():
            return None

        try:
            with open(log_path) as f:
                lines = f.readlines()
                if lines:
                    last = json.loads(lines[-1])
                    return last.get("ts")
        except:
            pass
        return None

    async def _process_download_queue(self) -> None:
        """Process the download queue in the background."""
        if self._is_downloading:
            return
        self._is_downloading = True

        while self.pending_downloads:
            item = self.pending_downloads.pop(0)
            try:
                await self._download_attachment(item.local_path, item.url)
            except Exception as e:
                print(f"Failed to download attachment: {item.local_path}: {e}")

        self._is_downloading = False

    async def _download_attachment(self, local_path: str, url: str) -> None:
        """Download a single attachment."""
        file_path = self.working_dir / local_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {self.bot_token}"})
            response.raise_for_status()

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(response.content)
