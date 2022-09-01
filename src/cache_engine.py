import time
from functools import wraps
from typing import Union, Iterable

from aioredis.client import Redis, ConnectionPool, PubSub
from aioredis.exceptions import ConnectionError


def recursive_decode(data):
    if isinstance(data, bytes):
        return data.decode('utf-8')
    elif not isinstance(data, Iterable):
        return data

    if not isinstance(data, dict):
        if isinstance(data, (tuple, list, set)):
            return [recursive_decode(x) for x in data]
        else:
            return data

    output = {}
    for k, v in data.items():
        if isinstance(k, bytes):
            k = k.decode('utf-8')
        if isinstance(v, bytes):
            v = v.decode('utf-8')
        elif isinstance(v, dict):
            v = recursive_decode(v)
        elif isinstance(v, (tuple, list, set)):
            v = [recursive_decode(x) for x in v]
        output[k] = v
    return output


def reconnect_on_error(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            res = recursive_decode(await func(self, *args, **kwargs))
        except ConnectionError:
            await self.close()
            self.connect_to_server()
            return recursive_decode(await func(self, *args, **kwargs))
        else:
            return res

    return wrapper


class RedisEngine:
    core: Redis
    pool: ConnectionPool

    def __init__(self, url: str):
        self.url = url

    def connect_to_server(self, url: str = None):
        if url:
            self.url = url
        while True:
            try:
                self.pool = ConnectionPool.from_url(
                    url=self.url,
                    max_connections=16,
                )
                self.core = Redis(
                    socket_timeout=1,
                    socket_connect_timeout=3,
                    connection_pool=self.pool,
                    encoding='utf-8',
                    decode_responses=True
                )
            except ConnectionError:
                raise ConnectionError('Can\'t connect to Redis Server')
            except ConnectionResetError:
                time.sleep(1)
            else:
                break

    async def close(self):
        if self.core:
            await self.pool.disconnect()
            await self.core.close()

    @reconnect_on_error
    async def set(self, name: str, value: Union[str, int, float], expire: int = None) -> bool:
        return await self.core.set(name, value, ex=expire)

    @reconnect_on_error
    async def get(self, name: str) -> str:
        return await self.core.get(name)

    @reconnect_on_error
    async def get_all(self) -> dict:
        keys = await self.core.keys()
        data = await self.core.mget(keys)
        return dict(zip(keys, data))

    @reconnect_on_error
    async def delete(self, *names: str) -> int:
        return await self.core.delete(*names)

    @reconnect_on_error
    async def clear(self):
        keys = await self.core.keys()
        if keys:
            await self.core.delete(*keys)

    def get_pubsub(self, **kwargs) -> PubSub:
        return self.core.pubsub(**kwargs)

    @reconnect_on_error
    async def publish(self, channel: str, message: Union[str, int, float]) -> int:
        return await self.core.publish(channel, message)
