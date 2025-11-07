from __future__ import annotations
import os
import asyncio
import contextlib
import time
import aiohttp
import logging
from uuid import uuid4
from typing import Optional
from aiohttp import WSMsgType
from token_refresher import resolve_host

_LOGGER = logging.getLogger("uvicorn.error")  # Use Uvicorn's logger


def init_ws_keepalive(app) -> None:

    # configuration through env
    SCHEME = os.environ.get("UGREEN_NAS_API_SCHEME", "http").lower()
    VERIFY_SSL = os.environ.get("UGREEN_NAS_API_VERIFY_SSL", "true").lower() == "true"
    WS_SCHEME = "wss" if SCHEME == "https" else "ws"
    ORIGIN_SCHEME = "https" if SCHEME == "https" else "http"
    PORT = int(os.environ.get("UGREEN_NAS_API_PORT") or "9443")
    LANG = os.environ.get("UGREEN_LANG", "de-DE")
    HEARTBEAT = int(os.environ.get("UGREEN_WS_HEARTBEAT", "25"))  # keep wss:// alive every 25s

    # internal state
    state = {
        "host": resolve_host(),
        "token": None,
        "task": None,
        "session": None,
        "stop": asyncio.Event(),
        "ws": None,
        # Used for logging only:
        "no_creds_logged": False,
        "no_token_logged": False,
        "heartbeat_logged": False,
    }

    async def _ensure_session() -> aiohttp.ClientSession:
        # Ensure aiohttp.ClientSession is available and open
        if state["session"] and not state["session"].closed:
            return state["session"]
        timeout = aiohttp.ClientTimeout(total=60)
        connector = aiohttp.TCPConnector(ssl=VERIFY_SSL)
        state["session"] = aiohttp.ClientSession(timeout=timeout, connector=connector)
        _LOGGER.debug("Created new keep-alive aiohttp ClientSession.")
        return state["session"]

    async def _fetch_token_if_needed() -> Optional[str]:
        # Return existing token if present
        if state["token"]:
            return state["token"]

        # Adopt token from central state (set via /token or /creds)
        token = getattr(app.state, "ugreen_token", None)
        if token and token != state.get("token"):
            state["token"] = token
            _LOGGER.info("WebSocket token adopted from app.state.")
            # reset once we have a token so future 'no token' logs can appear again if needed
            state["no_token_logged"] = False
            return state["token"]

        # No token available yet — log once, then stay quiet until a token is set by /creds or /token
        if not state["no_token_logged"]:
            _LOGGER.debug("No token yet; keep-alive idle. Checking again every 15s until avail.")
            state["no_token_logged"] = True
        return None

    def _ws_url(token: str) -> str:
        # Build the WebSocket URL with client ID, lang and token
        return (
            f"{WS_SCHEME}://{state['host']}:{PORT}/ugreen/v1/desktop/ws"
            f"?client_id={uuid4()}-WEB&lang={LANG}&token={token}"
        )

    async def _ws_loop():
        # Endless loop: Ensure token, connect websocket, send heartbeat, reconnect on errors

        backoff = [1, 2, 5, 10, 15, 30, 60]
        while not state["stop"].is_set():
            try:
                # Ensure token is present
                if not state["token"]:
                    await _fetch_token_if_needed()

                if not state["token"]:
                    # log once, then stay quiet until a token appears
                    if not state["no_token_logged"]:
                        _LOGGER.debug("No credentials = no token: Skipping ws: subscription for now.")
                        state["no_token_logged"] = True  # comment out to see every 15s retry in log
                    await asyncio.sleep(15)
                    continue
                else:
                    # reset flag when a token is present again
                    state["no_token_logged"] = False

                # Open WS connection
                sess = await _ensure_session()

                apptoken = getattr(app.state, "ugreen_token", None)
                if apptoken and apptoken != state["token"]:
                    state["token"] = apptoken
                    _LOGGER.debug("Using updated token from app.state for next connect.")
                url = _ws_url(state["token"])
                headers = {
                    "Origin": f"{ORIGIN_SCHEME}://{state['host']}:{PORT}",
                    "Pragma": "no-cache",
                    "Cache-Control": "no-cache",
                }

                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug("Connecting WebSocket to %s", url)
                else:
                    _LOGGER.info("Connecting WebSocket to %s", url.split("?", 1)[0])

                async with sess.ws_connect(url, headers=headers, heartbeat=None, ssl=VERIFY_SSL) as ws:
                    state["ws"] = ws

                    # reset once-per-connection heartbeat log flag
                    state["heartbeat_logged"] = False

                    # subscription for certain topics, so connection is kept on both ends
                    with contextlib.suppress(Exception):
                        await ws.send_json(
                            {
                                "op": "subscribe",
                                "topics": ["cpu_usage", "cpu_temp"],
                                "ts": int(time.time() * 1000),
                            }
                        )
                        _LOGGER.info("Subscribed cpu_usage + cpu_temp, keep_alive setup completed.")

                    last_ping = 0.0
                    backoff = [1, 2, 5, 10, 15, 30, 60]  # reset after successful connect

                    while not state["stop"].is_set():
                        now = time.time()
                        if now - last_ping >= HEARTBEAT:
                            # log only once per (re)connection
                            if not state["heartbeat_logged"]:
                                _LOGGER.debug(
                                    "Sending keep-alive heartbeat to websocket every %ss from now on.", HEARTBEAT
                                )
                                state["heartbeat_logged"] = True  # comment out to see every 25s heartbeat log
                            await ws.ping()
                            last_ping = now

                        msg = await ws.receive(timeout=HEARTBEAT + 5)
                        if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.ERROR):
                            _LOGGER.warning("WebSocket closed or error received, forcing reconnect.")
                            raise RuntimeError("WS closed.")

            except asyncio.CancelledError:
                _LOGGER.info("WebSocket loop cancelled.")
                break
            except Exception as e:
                delay = backoff[0]
                backoff = backoff[1:] or [60]
                # Clear local token so next connect adopts the latest app.state token
                state["token"] = None
                _LOGGER.error("WebSocket loop error: %s — reconnecting in %ds.", e, delay)
                await asyncio.sleep(delay)

        # Cleanup on stop
        if state["session"]:
            with contextlib.suppress(Exception):
                await state["session"].close()
                _LOGGER.debug("Closed aiohttp session.")
        state["session"] = None

    # ---------- FastAPI Lifecycle Hooks ----------

    @app.on_event("startup")
    async def _startup_ws_sidecar():
        # Start ws keepalive loop at application startup
        if state["task"] is None or state["task"].done():
            state["stop"].clear()
            state["task"] = asyncio.create_task(_ws_loop(), name="ugreen-ws-sidecar")
            _LOGGER.debug("Started WebSocket keep-alive task.")

    @app.on_event("shutdown")
    async def _shutdown_ws_sidecar():
        # Stop ws keepalive loop at application shutdown
        state["stop"].set()
        if state["task"]:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(state["task"], timeout=5)
            _LOGGER.info("Stopped WebSocket keep-alive task.")
        if state["session"]:
            with contextlib.suppress(Exception):
                await state["session"].close()
                _LOGGER.debug("Closed aiohttp keep-alive session.")
        state["session"] = None
