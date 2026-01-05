import json
import logging
import os
import socket
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


_LOGGER = logging.getLogger("uvicorn.error")  # Use Uvicorn's logger


def resolve_host():
    # Try to resolve host.docker.internal, fallback to UGREEN_NAS_API_IP or localhost.
    try:
        return socket.gethostbyname("host.docker.internal")
    except socket.gaierror:
        return os.getenv("UGREEN_NAS_API_IP", "127.0.0.1")


class TokenRefresher:
    def __init__(self, username: str, password: str):

        # Validate inputs early
        if not isinstance(username, str) or not username.strip():
            raise ValueError("TokenRefresher: username must be a non-empty string")
        if not isinstance(password, str) or not password.strip():
            raise ValueError("TokenRefresher: password must be a non-empty string")

        # Store credentials
        self._username = username
        self._password = password

        # Read connection settings from environment variables
        self._scheme = os.environ.get("UGREEN_NAS_API_SCHEME", "https")
        self._host = resolve_host()
        self._port = int(os.environ.get("UGREEN_NAS_API_PORT") or "9443")
        self._verify = os.environ.get("UGREEN_NAS_API_VERIFY_SSL", "true").lower() == "true"

        # Token will be stored here after successful login
        self._token = None

    @property
    def token(self):
        # Return the last retrieved API token.
        return self._token

    async def fetch_token_async(self) -> bool:
        # Perform a headless login to UGOS Web UI, retrieve the API token

        _LOGGER.debug("Starting Playwright context for token retrieval.")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(ignore_https_errors=not self._verify)
            page = await context.new_page()

            # Build login URL and navigate
            url = f"{self._scheme}://{self._host}:{self._port}"
            _LOGGER.info("Navigating to %s", url)
            await page.goto(url, wait_until="domcontentloaded")

            # Fill in login form
            _LOGGER.debug("Filling username and password fields.")
            await page.fill('input[name="ugos-username"]', self._username)
            await page.fill('input[name="ugos-password"]', self._password)

            # Ensure the checkbox is checked
            checkbox_selector = 'div.is-login input[type="checkbox"]'
            if not await page.is_checked(checkbox_selector):
                _LOGGER.debug("Checking the 'remember me' checkbox")
                await page.check(checkbox_selector)

            # Wait for login button and click it
            _LOGGER.debug("Waiting for login button to become active.")
            await page.wait_for_selector('.login-public-button button[type="button"]:not([disabled])')
            _LOGGER.debug("Clicking login button")
            await page.click('.login-public-button button[type="button"]')

            # Wait for dashboard as confirmation of successful login
            try:
                _LOGGER.debug("Waiting for dashboard to load.")
                await page.wait_for_selector('div.dashboard', timeout=5000)
            except PlaywrightTimeoutError:
                _LOGGER.warning("Dashboard not found in time, waiting extra fallback timeout.")
                await page.wait_for_timeout(3000)

            # Extract localStorage entries
            _LOGGER.debug("Reading localStorage for token entries.")
            local_storage = await page.evaluate("Object.assign({}, window.localStorage);")

            for value in local_storage.values():
                if "api_token" in value:
                    try:
                        json_data = json.loads(value)
                        token = json_data.get("accessInfo", {}).get("api_token")
                        if token:
                            self._token = token
                            _LOGGER.info("API token successfully retrieved.")
                            return True
                    except json.JSONDecodeError as e:
                        _LOGGER.debug("Invalid JSON found in localStorage: %s.", e)

            _LOGGER.error("API token not found in localStorage.")
            return False
