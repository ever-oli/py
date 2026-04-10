"""Slack bot implementation for Mom."""

import asyncio
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient

from .store import ChannelStore


class SlackEvent:
    """Represents a Slack event."""

    def __init__(
        self,
        event_type: str,
        channel: str,
        ts: str,
        user: str,
        text: str,
        files: list | None = None,
        attachments: list | None = None,
    ):
        self.type = event_type
        self.channel = channel
        self.ts = ts
        self.user = user
        self.text = text
        self.files = files or []
        self.attachments = attachments or []


class SlackUser:
    """Represents a Slack user."""

    def __init__(self, user_id: str, user_name: str, display_name: str):
        self.id = user_id
        self.user_name = user_name
        self.display_name = display_name


class SlackChannel:
    """Represents a Slack channel."""

    def __init__(self, channel_id: str, name: str):
        self.id = channel_id
        self.name = name


class SlackContext:
    """Context for Slack interactions."""

    def __init__(
        self,
        message: dict,
        channel_name: str | None,
        store: ChannelStore,
        channels: list,
        users: list,
        respond_func: Callable,
        replace_message_func: Callable,
        respond_in_thread_func: Callable,
        set_typing_func: Callable,
        upload_file_func: Callable,
        set_working_func: Callable,
        delete_message_func: Callable,
    ):
        self.message = message
        self.channel_name = channel_name
        self.store = store
        self.channels = channels
        self.users = users
        self._respond = respond_func
        self._replace_message = replace_message_func
        self._respond_in_thread = respond_in_thread_func
        self._set_typing = set_typing_func
        self._upload_file = upload_file_func
        self._set_working = set_working_func
        self._delete_message = delete_message_func
        self._accumulated_text = ""
        self._is_working = True
        self._working_indicator = " ..."

    async def respond(self, text: str, should_log: bool = True) -> None:
        """Send a response message."""
        self._accumulated_text = (
            f"{self._accumulated_text}\n{text}" if self._accumulated_text else text
        )

        # Truncate if too long
        max_length = 35000
        if len(self._accumulated_text) > max_length:
            truncation_note = "\n\n_(message truncated, ask me to elaborate on specific parts)_"
            self._accumulated_text = (
                self._accumulated_text[: max_length - len(truncation_note)] + truncation_note
            )

        display_text = self._accumulated_text + (
            self._working_indicator if self._is_working else ""
        )
        await self._respond(display_text, should_log)

    async def replace_message(self, text: str) -> None:
        """Replace the entire message."""
        max_length = 35000
        if len(text) > max_length:
            truncation_note = "\n\n_(message truncated, ask me to elaborate on specific parts)_"
            self._accumulated_text = text[: max_length - len(truncation_note)] + truncation_note
        else:
            self._accumulated_text = text

        display_text = self._accumulated_text + (
            self._working_indicator if self._is_working else ""
        )
        await self._replace_message(display_text)

    async def respond_in_thread(self, text: str) -> None:
        """Respond in a thread."""
        max_length = 20000
        if len(text) > max_length:
            text = f"{text[: max_length - 50]}\n\n_(truncated)_"
        await self._respond_in_thread(text)

    async def set_typing(self, is_typing: bool) -> None:
        """Set typing indicator."""
        await self._set_typing(is_typing)

    async def upload_file(self, file_path: str, title: str | None = None) -> None:
        """Upload a file."""
        await self._upload_file(file_path, title)

    async def set_working(self, working: bool) -> None:
        """Set working state."""
        self._is_working = working
        display_text = self._accumulated_text + (
            self._working_indicator if self._is_working else ""
        )
        await self._set_working(display_text)

    async def delete_message(self) -> None:
        """Delete the message."""
        await self._delete_message()


class MomHandler:
    """Handler interface for Mom events."""

    def is_running(self, channel_id: str) -> bool:
        """Check if channel is currently running."""
        raise NotImplementedError

    async def handle_stop(self, channel_id: str, slack: "SlackBot") -> None:
        """Handle stop command."""
        raise NotImplementedError

    async def handle_event(
        self, event: SlackEvent, slack: "SlackBot", is_event: bool = False
    ) -> None:
        """Handle an event."""
        raise NotImplementedError


class ChannelQueue:
    """Per-channel queue for sequential processing."""

    def __init__(self):
        self._queue: list[Callable] = []
        self._processing = False

    def enqueue(self, work: Callable) -> None:
        """Add work to the queue."""
        self._queue.append(work)
        asyncio.create_task(self._process_next())

    def size(self) -> int:
        """Get queue size."""
        return len(self._queue)

    async def _process_next(self) -> None:
        """Process next item in queue."""
        if self._processing or not self._queue:
            return
        self._processing = True
        work = self._queue.pop(0)
        try:
            await work()
        except Exception as e:
            print(f"Queue error: {e}")
        self._processing = False
        if self._queue:
            asyncio.create_task(self._process_next())


class SlackBot:
    """Slack bot for Mom."""

    def __init__(
        self,
        handler: MomHandler,
        app_token: str,
        bot_token: str,
        working_dir: str,
        store: ChannelStore,
    ):
        self.handler = handler
        self.app_token = app_token
        self.bot_token = bot_token
        self.working_dir = Path(working_dir)
        self.store = store

        self.socket_client: SocketModeClient | None = None
        self.web_client = AsyncWebClient(token=bot_token)
        self.bot_user_id: str | None = None
        self.startup_ts: str | None = None

        self.users: dict[str, SlackUser] = {}
        self.channels: dict[str, SlackChannel] = {}
        self.queues: dict[str, ChannelQueue] = {}

    async def start(self) -> None:
        """Start the bot."""
        auth = await self.web_client.auth_test()
        self.bot_user_id = auth["user_id"]

        await asyncio.gather(self._fetch_users(), self._fetch_channels())

        print(f"Loaded {len(self.channels)} channels, {len(self.users)} users")

        # Setup socket mode client
        self.socket_client = SocketModeClient(app_token=self.app_token, web_client=self.web_client)

        self.socket_client.socket_mode_request_listeners.append(self._handle_request)

        await self._backfill_all_channels()

        self.startup_ts = f"{datetime.now().timestamp():.6f}"
        print("Connected to Slack")

        await self.socket_client.connect()

        # Keep running
        while True:
            await asyncio.sleep(1)

    def get_user(self, user_id: str) -> SlackUser | None:
        """Get user by ID."""
        return self.users.get(user_id)

    def get_channel(self, channel_id: str) -> SlackChannel | None:
        """Get channel by ID."""
        return self.channels.get(channel_id)

    def get_all_users(self) -> list[SlackUser]:
        """Get all users."""
        return list(self.users.values())

    def get_all_channels(self) -> list[SlackChannel]:
        """Get all channels."""
        return list(self.channels.values())

    async def post_message(self, channel: str, text: str) -> str:
        """Post a message to a channel."""
        result = await self.web_client.chat_postMessage(channel=channel, text=text)
        return result["ts"]

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        """Update a message."""
        await self.web_client.chat_update(channel=channel, ts=ts, text=text)

    async def delete_message(self, channel: str, ts: str) -> None:
        """Delete a message."""
        await self.web_client.chat_delete(channel=channel, ts=ts)

    async def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str:
        """Post a message in a thread."""
        result = await self.web_client.chat_postMessage(
            channel=channel, thread_ts=thread_ts, text=text
        )
        return result["ts"]

    async def upload_file(self, channel: str, file_path: str, title: str | None = None) -> None:
        """Upload a file to a channel."""
        import aiofiles

        filename = title or Path(file_path).name
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()

        await self.web_client.files_upload_v2(
            channel_id=channel, file=content, filename=filename, title=filename
        )

    def log_to_file(self, channel: str, entry: dict) -> None:
        """Log a message to log.jsonl."""
        import json

        channel_dir = self.working_dir / channel
        channel_dir.mkdir(parents=True, exist_ok=True)

        log_path = channel_dir / "log.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_bot_response(self, channel: str, text: str, ts: str) -> None:
        """Log a bot response."""
        self.log_to_file(
            channel,
            {
                "date": datetime.now().isoformat(),
                "ts": ts,
                "user": "bot",
                "text": text,
                "attachments": [],
                "isBot": True,
            },
        )

    def enqueue_event(self, event: SlackEvent) -> bool:
        """Enqueue an event for processing."""
        queue = self._get_queue(event.channel)
        if queue.size() >= 5:
            print(f"Event queue full for {event.channel}, discarding: {event.text[:50]}")
            return False

        print(f"Enqueueing event for {event.channel}: {event.text[:50]}")
        queue.enqueue(lambda: self.handler.handle_event(event, self, True))
        return True

    def _get_queue(self, channel_id: str) -> ChannelQueue:
        """Get or create a queue for a channel."""
        if channel_id not in self.queues:
            self.queues[channel_id] = ChannelQueue()
        return self.queues[channel_id]

    async def _handle_request(self, client: SocketModeClient, req: Any) -> None:
        """Handle a socket mode request."""
        await client.acknowledge(req)

        payload = req.payload
        event_type = payload.get("event", {}).get("type")

        if event_type == "app_mention":
            await self._handle_app_mention(payload.get("event", {}))
        elif event_type == "message":
            await self._handle_message(payload.get("event", {}))

    async def _handle_app_mention(self, event: dict) -> None:
        """Handle app mention event."""
        channel = event.get("channel")

        # Skip DMs (handled by message event)
        if channel and channel.startswith("D"):
            return

        slack_event = SlackEvent(
            event_type="mention",
            channel=channel,
            ts=event.get("ts"),
            user=event.get("user"),
            text=self._strip_mentions(event.get("text", "")),
            files=event.get("files", []),
        )

        slack_event.attachments = self._log_user_message(slack_event)

        # Skip old messages
        if self.startup_ts and slack_event.ts < self.startup_ts:
            print(
                f"[{channel}] Logged old message (pre-startup), not triggering: {slack_event.text[:30]}"
            )
            return

        # Check for stop command
        if slack_event.text.lower().strip() == "stop":
            if self.handler.is_running(channel):
                await self.handler.handle_stop(channel, self)
            else:
                await self.post_message(channel, "_Nothing running_")
            return

        if self.handler.is_running(channel):
            await self.post_message(channel, "_Already working. Say `@mom stop` to cancel._")
        else:
            self._get_queue(channel).enqueue(lambda: self.handler.handle_event(slack_event, self))

    async def _handle_message(self, event: dict) -> None:
        """Handle message event."""
        bot_id = event.get("bot_id")
        user = event.get("user")
        channel = event.get("channel")
        channel_type = event.get("channel_type")

        # Skip bot messages
        if bot_id or not user or user == self.bot_user_id:
            return

        subtype = event.get("subtype")
        if subtype and subtype != "file_share":
            return

        text = event.get("text", "")
        if not text and not event.get("files"):
            return

        is_dm = channel_type == "im"
        is_bot_mention = f"<@{self.bot_user_id}>" in text

        # Skip channel mentions (handled by app_mention)
        if not is_dm and is_bot_mention:
            return

        slack_event = SlackEvent(
            event_type="dm" if is_dm else "mention",
            channel=channel,
            ts=event.get("ts"),
            user=user,
            text=self._strip_mentions(text),
            files=event.get("files", []),
        )

        slack_event.attachments = self._log_user_message(slack_event)

        # Skip old messages
        if self.startup_ts and slack_event.ts < self.startup_ts:
            return

        # Only trigger handler for DMs
        if is_dm:
            if slack_event.text.lower().strip() == "stop":
                if self.handler.is_running(channel):
                    await self.handler.handle_stop(channel, self)
                else:
                    await self.post_message(channel, "_Nothing running_")
                return

            if self.handler.is_running(channel):
                await self.post_message(channel, "_Already working. Say `stop` to cancel._")
            else:
                self._get_queue(channel).enqueue(
                    lambda: self.handler.handle_event(slack_event, self)
                )

    def _strip_mentions(self, text: str) -> str:
        """Strip @mentions from text."""
        import re

        return re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    def _log_user_message(self, event: SlackEvent) -> list:
        """Log a user message."""
        user = self.users.get(event.user)
        attachments = event.files if event.files else []
        processed = (
            self.store.process_attachments(event.channel, attachments, event.ts)
            if attachments
            else []
        )

        self.log_to_file(
            event.channel,
            {
                "date": datetime.fromtimestamp(float(event.ts)).isoformat(),
                "ts": event.ts,
                "user": event.user,
                "userName": user.user_name if user else None,
                "displayName": user.display_name if user else None,
                "text": event.text,
                "attachments": processed,
                "isBot": False,
            },
        )

        return processed

    async def _fetch_users(self) -> None:
        """Fetch all users from Slack."""
        cursor = None
        while True:
            result = await self.web_client.users_list(limit=200, cursor=cursor)
            members = result.get("members", [])

            for u in members:
                if u.get("id") and u.get("name") and not u.get("deleted"):
                    self.users[u["id"]] = SlackUser(
                        user_id=u["id"],
                        user_name=u["name"],
                        display_name=u.get("real_name") or u["name"],
                    )

            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    async def _fetch_channels(self) -> None:
        """Fetch all channels from Slack."""
        cursor = None
        while True:
            result = await self.web_client.conversations_list(
                types="public_channel,private_channel",
                exclude_archived=True,
                limit=200,
                cursor=cursor,
            )
            channels = result.get("channels", [])

            for c in channels:
                if c.get("id") and c.get("name") and c.get("is_member"):
                    self.channels[c["id"]] = SlackChannel(channel_id=c["id"], name=c["name"])

            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        # Also fetch DM channels
        cursor = None
        while True:
            result = await self.web_client.conversations_list(types="im", limit=200, cursor=cursor)
            ims = result.get("channels", [])

            for im in ims:
                if im.get("id"):
                    user = self.users.get(im.get("user", ""))
                    name = f"DM:{user.user_name}" if user else f"DM:{im['id']}"
                    self.channels[im["id"]] = SlackChannel(channel_id=im["id"], name=name)

            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    async def _backfill_all_channels(self) -> None:
        """Backfill messages for all known channels."""
        channels_to_backfill = []
        for channel_id, channel in self.channels.items():
            log_path = self.working_dir / channel_id / "log.jsonl"
            if log_path.exists():
                channels_to_backfill.append((channel_id, channel))

        for channel_id, channel in channels_to_backfill:
            try:
                count = await self._backfill_channel(channel_id)
                if count > 0:
                    print(f"Backfilled #{channel.name}: {count} messages")
            except Exception as e:
                print(f"Failed to backfill #{channel.name}: {e}")

    async def _backfill_channel(self, channel_id: str) -> int:
        """Backfill messages for a single channel."""
        log_path = self.working_dir / channel_id / "log.jsonl"

        existing_ts = set()
        if log_path.exists():
            with open(log_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            import json

                            entry = json.loads(line)
                            if entry.get("ts"):
                                existing_ts.add(entry["ts"])
                        except:
                            pass

        latest_ts = None
        for ts in existing_ts:
            if latest_ts is None or float(ts) > float(latest_ts):
                latest_ts = ts

        all_messages = []
        cursor = None
        page_count = 0
        max_pages = 3

        while page_count < max_pages:
            result = await self.web_client.conversations_history(
                channel=channel_id, oldest=latest_ts, inclusive=False, limit=1000, cursor=cursor
            )

            messages = result.get("messages", [])
            all_messages.extend(messages)

            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            page_count += 1

        relevant = []
        for msg in all_messages:
            ts = msg.get("ts")
            if not ts or ts in existing_ts:
                continue
            if msg.get("bot_id") and msg.get("user") != self.bot_user_id:
                continue
            if msg.get("subtype") and msg.get("subtype") != "file_share":
                continue
            if not msg.get("user"):
                continue
            if not msg.get("text") and not msg.get("files"):
                continue
            relevant.append(msg)

        relevant.reverse()

        for msg in relevant:
            is_mom = msg.get("user") == self.bot_user_id
            user = self.users.get(msg.get("user", ""))
            text = self._strip_mentions(msg.get("text", ""))
            attachments = msg.get("files", [])
            processed = (
                self.store.process_attachments(channel_id, attachments, msg["ts"])
                if attachments
                else []
            )

            self.log_to_file(
                channel_id,
                {
                    "date": datetime.fromtimestamp(float(msg["ts"])).isoformat(),
                    "ts": msg["ts"],
                    "user": "bot" if is_mom else msg["user"],
                    "userName": None if is_mom else (user.user_name if user else None),
                    "displayName": None if is_mom else (user.display_name if user else None),
                    "text": text,
                    "attachments": processed,
                    "isBot": is_mom,
                },
            )

        return len(relevant)
