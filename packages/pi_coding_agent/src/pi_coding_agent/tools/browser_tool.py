"""Browser tool for web scraping using Playwright."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrowserOptions:
    """Options for the browser tool."""

    headless: bool = True
    timeout: int = 30000
    wait_for_load: str | None = "networkidle"
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str | None = None
    cookies: list[dict] = field(default_factory=list)


@dataclass
class BrowserAction:
    """A browser action to perform."""

    action: str  # click, type, scroll, wait, screenshot, evaluate
    selector: str | None = None
    text: str | None = None
    value: str | None = None
    delay_ms: int = 0
    timeout: int = 5000


async def browser_tool(
    url: str,
    actions: list[dict] | None = None,
    options: dict | None = None,
) -> dict[str, Any]:
    """Browser automation tool using Playwright.

    Args:
        url: URL to navigate to
        actions: List of actions to perform (click, type, scroll, wait, screenshot, evaluate)
        options: Browser options (headless, timeout, viewport, etc.)

    Returns:
        Results including page content, screenshot data, and action results

    Example:
        >>> result = await browser_tool(
        ...     url="https://example.com",
        ...     actions=[
        ...         {"action": "click", "selector": "#button"},
        ...         {"action": "type", "selector": "#input", "text": "hello"},
        ...         {"action": "screenshot"},
        ...     ]
        ... )
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install",
            "content": "",
        }

    opts = BrowserOptions(**(options or {}))
    results = []
    screenshot_data = None
    final_url = url
    page_title = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=opts.headless)
        context = await browser.new_context(
            viewport={"width": opts.viewport_width, "height": opts.viewport_height},
            user_agent=opts.user_agent,
        )

        if opts.cookies:
            await context.add_cookies(opts.cookies)

        page = await context.new_page()

        try:
            # Navigate to URL
            await page.goto(url, wait_until=opts.wait_for_load, timeout=opts.timeout)
            final_url = page.url
            page_title = await page.title()

            # Execute actions
            if actions:
                for action_def in actions:
                    action = BrowserAction(**action_def)
                    action_result = await _execute_action(page, action)
                    results.append(action_result)

                    if action.action == "screenshot" and action_result.get("success"):
                        screenshot_data = action_result.get("data")

            # Get page content
            content = await page.content()

            await browser.close()

            return {
                "success": True,
                "url": final_url,
                "title": page_title,
                "content": content,
                "screenshot": screenshot_data,
                "actions": results,
            }

        except Exception as e:
            await browser.close()
            return {
                "success": False,
                "error": str(e),
                "url": final_url,
                "title": page_title,
                "content": "",
            }


async def _execute_action(page, action: BrowserAction) -> dict[str, Any]:
    """Execute a single browser action."""
    try:
        if action.action == "click":
            if not action.selector:
                raise ValueError("Selector required for click action")
            await page.click(action.selector, timeout=action.timeout)
            return {"action": "click", "success": True, "selector": action.selector}

        elif action.action == "type":
            if not action.selector or action.text is None:
                raise ValueError("Selector and text required for type action")
            await page.fill(action.selector, action.text, timeout=action.timeout)
            return {"action": "type", "success": True, "selector": action.selector}

        elif action.action == "press":
            if not action.selector or not action.value:
                raise ValueError("Selector and value required for press action")
            await page.press(action.selector, action.value)
            return {"action": "press", "success": True, "key": action.value}

        elif action.action == "scroll":
            if action.selector:
                await page.evaluate(f"document.querySelector('{action.selector}').scrollIntoView()")
            else:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return {"action": "scroll", "success": True}

        elif action.action == "wait":
            if action.selector:
                await page.wait_for_selector(action.selector, timeout=action.timeout)
            elif action.delay_ms:
                await asyncio.sleep(action.delay_ms / 1000)
            return {"action": "wait", "success": True}

        elif action.action == "screenshot":
            screenshot_bytes = await page.screenshot(full_page=True)
            import base64

            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return {"action": "screenshot", "success": True, "data": screenshot_b64}

        elif action.action == "evaluate":
            if not action.value:
                raise ValueError("Value (JavaScript) required for evaluate action")
            result = await page.evaluate(action.value)
            return {"action": "evaluate", "success": True, "result": result}

        elif action.action == "select":
            if not action.selector or action.value is None:
                raise ValueError("Selector and value required for select action")
            await page.select_option(action.selector, action.value)
            return {"action": "select", "success": True}

        else:
            return {
                "action": action.action,
                "success": False,
                "error": f"Unknown action: {action.action}",
            }

    except Exception as e:
        return {"action": action.action, "success": False, "error": str(e)}


def create_browser_tool(cwd: str | None = None) -> dict[str, Any]:
    """Create a browser tool instance."""
    return {
        "name": "browser",
        "description": """Web browser automation using Playwright.

Navigate to URLs, interact with pages, take screenshots, and extract content.

Supported actions:
- click: Click an element (requires selector)
- type: Type text into an input (requires selector, text)
- press: Press a key (requires selector, value)
- scroll: Scroll page or to element (optional selector)
- wait: Wait for selector or delay (requires selector or delay_ms)
- screenshot: Take full page screenshot
- evaluate: Execute JavaScript (requires value)
- select: Select dropdown option (requires selector, value)
""",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to navigate to",
                },
                "actions": {
                    "type": "array",
                    "description": "List of actions to perform",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": [
                                    "click",
                                    "type",
                                    "press",
                                    "scroll",
                                    "wait",
                                    "screenshot",
                                    "evaluate",
                                    "select",
                                ],
                            },
                            "selector": {"type": "string"},
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "delay_ms": {"type": "integer"},
                            "timeout": {"type": "integer"},
                        },
                    },
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "headless": {"type": "boolean", "default": True},
                        "timeout": {"type": "integer", "default": 30000},
                        "wait_for_load": {
                            "type": "string",
                            "enum": ["load", "domcontentloaded", "networkidle", None],
                        },
                        "viewport_width": {"type": "integer", "default": 1920},
                        "viewport_height": {"type": "integer", "default": 1080},
                        "user_agent": {"type": "string"},
                    },
                },
            },
            "required": ["url"],
        },
        "execute": browser_tool,
    }


browser_tool_definition = create_browser_tool()
