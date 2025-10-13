import logging
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from token_refresher import TokenRefresher
from ws_keepalive import init_ws_keepalive

_LOGGER = logging.getLogger("uvicorn.error")  # Use Uvicorn's logger

app = FastAPI()                   # Create FastAPI app
init_ws_keepalive(app)            # Initialize WebSocket keep-alive

app.state.ugreen_username = None  # Central in-memory states
app.state.ugreen_password = None  # (read by other components)
app.state.ugreen_token = None


# Passive endpoint for HA: remotely update username / password / token.
@app.get("/credentials")
async def set_credentials(
    username: str = Query(None),
    password: str = Query(None),
    token: str = Query(None),
):
    if username is not None:
        app.state.ugreen_username = username
    if password is not None:
        app.state.ugreen_password = password
    if token is not None:
        app.state.ugreen_token = token

    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            f"Credentials updated: (username={app.state.ugreen_username}, "
            f"password={app.state.ugreen_password}, "
            f"token={app.state.ugreen_token})."
        )

    return JSONResponse(
        status_code=200,
        content={"code": 200, "msg": "success", "data": None},
    )


# Active endpoint for HA: fetch a fresh token, store it & return it.
@app.get("/token")
async def get_token(
    username: str = Query(None),
    password: str = Query(None),
):

    # INFO shows username only; DEBUG also includes password
    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug("Received token request (username=%s, password=%s)", username, password)
    else:
        _LOGGER.info("Received token request (username=%s)", username)

    if username is not None:
        app.state.ugreen_username = username
    if password is not None:
        app.state.ugreen_password = password

    refresher = TokenRefresher(
        username=app.state.ugreen_username,
        password=app.state.ugreen_password,
    )
    success = await refresher.fetch_token_async()
    if not success:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "msg": "Token refresh failed"},
        )

    app.state.ugreen_token = refresher.token
    
    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug("Token is %s - keep-alive adopting it soon.", app.state.ugreen_token)
    else:
        _LOGGER.info("Token successfully refreshed, returning it to HA.")

    return JSONResponse(
        status_code=200,
        content={"code": 200, "msg": "success", "data": {"token": refresher.token}},
    )
