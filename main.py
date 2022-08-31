"""
Нужно реализовать монитор содержимого каталога.
Есть сервер и клиент. После запуска сервер следит за изменениями в заданном каталоге.
Если содержимое изменилось, оно должно быстро обновиться на клиенте.
Сервер должен каким-то образом получать путь к каталогу (например, через ключ запуска
или конфиг).
Клиент и сервер работают независимо

Код может запускаться в докере или просто консоли. Клиентское приложение может быть страничкой в браузере.
"""
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK

from src.cache_engine import RedisEngine
from src.logger import Logger


REDIS_CHANNEL = os.environ.get('REDIS_FW_CHANNEL', 'file_watcher')
REDIS_URL = os.environ.get('REDIS_FW_URL', 'redis://localhost/0')

app = FastAPI()
cache = RedisEngine(REDIS_URL)
logger = Logger.with_default_handlers()


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    pubsub = cache.get_pubsub()
    try:
        await websocket.accept()
        await websocket.send_json({'data': await cache.get_all()})
        await pubsub.subscribe(REDIS_CHANNEL)
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                await websocket.send_json(json.loads(message).get('data'))
    except (WebSocketDisconnect, ConnectionClosedOK):
        pass
    except Exception as e:
        await logger.exception(f'WebSocket error: {e}')
    finally:
        await pubsub.unsubscribe()
