"""
Web application for loading from Redis and delivering a list of directory files to subscribers (clients)
using websockets
"""

import json
import os

from aioredis.client import PubSub
from aioredis.exceptions import ConnectionError as RedisConnectionError
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from websockets.exceptions import ConnectionClosedOK

from src.cache_engine import RedisEngine
from src.model_file import File
from src.logger import logger


__author__ = 'Leichgardt'


REDIS_CHANNEL = os.environ.get('REDIS_FW_CHANNEL', 'file_watcher')
REDIS_URL = os.environ.get('REDIS_FW_URL', 'redis://localhost/0')

app = FastAPI()
template = Jinja2Templates(directory='templates')
cache = RedisEngine(REDIS_URL)


@app.on_event('startup')
async def server_startup():
    cache.connect_to_server()


@app.on_event('shutdown')
async def server_startup():
    await cache.close()


@app.get('/')
async def index(request: Request):
    return template.TemplateResponse('index.html', context={'request': request})


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    # TODO Move from Redis to message broker for websocket subscribing
    pubsub: PubSub = None
    try:
        await websocket.accept()
        pubsub = cache.get_pubsub()
        data = await cache.get_all()
        sorted_data = []
        for file, time in sorted(data.items(), key=lambda item: item[1]):
            sorted_data.append(File(file=file, data={'status': 'new', 'time': time}).to_obj())
        await websocket.send_json(sorted_data)
        await pubsub.subscribe(REDIS_CHANNEL)
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                data = json.loads(message['data'].decode('utf-8'))
                await websocket.send_json(data)
    except (WebSocketDisconnect, ConnectionClosedOK):
        pass
    except RedisConnectionError as e:
        logger.error(f'Redis connection error on Websocket <{websocket.client}>: {e}')
    except Exception as e:
        logger.exception(f'WebSocket error <{websocket.client}>: {e}')
    finally:
        await websocket.close()
        if pubsub is not None:
            await pubsub.unsubscribe()
