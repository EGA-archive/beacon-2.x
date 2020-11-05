import logging
import base64
import json
import traceback
import sys

#import aiohttp_csrf
import aiohttp_jinja2
from aiohttp import web
from cryptography import fernet
from aiohttp_session import setup as session_setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage

LOG = logging.getLogger(__name__)

CSRF_FIELD_NAME = 'csrf_token'
SESSION_STORAGE = 'beacon_session'

error_templates = {
    400: '400.html',
    404: '404.html',
    500: '500.html',
}

default_errors = {
    400: 'Bad request',
    404: 'This URL does not exist',
    500: 'Server Error',
}

def handle_error(request, exc):
    # exc is a web.HTTPException
    
    template = error_templates.get(exc.status)
    if not template:
        raise exc # We don't handle it

    context = {
        'cookies': request.cookies,
        'exception': exc
    }
    return aiohttp_jinja2.render_template(template,
                                          request,
                                          context)


@web.middleware
async def error_middleware(request, handler):
    try:
        return await handler(request)
    except web.HTTPError as ex: # Just the 400's and 500's

        # if the request comes from /api/*, we output the json version
        LOG.error('Error on page %s: %s', request.path, ex)

        if hasattr(ex, 'api_error'):
            raise

        # Else, we are a regular HTML response
        if ex.status == 401: # Unauthorized
            raise web.HTTPFound('/login')

        if ex.status >= 500:
            LOG.error('Error caught: %s', ex)
            traceback.print_stack(file=sys.stderr)

        return handle_error(request, ex)

# @web.middleware
# async def json_middleware(request, handler):
#     data = await handler(request)
#     return await json_stream(request, data)


def setup(app):
    # Session middleware
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key) # 32 url-safe base64-encoded bytes
    session_setup(app, EncryptedCookieStorage(secret_key))

    # CSRF middleware
    # aiohttp_csrf.setup(app,
    #                    policy=aiohttp_csrf.policy.FormPolicy(CSRF_FIELD_NAME),
    #                    storage=aiohttp_csrf.storage.SessionStorage(SESSION_STORAGE))
    # app.middlewares.append(aiohttp_csrf.csrf_middleware)

    # Capture 404 and 500
    app.middlewares.append(error_middleware)



