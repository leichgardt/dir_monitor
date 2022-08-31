from typing import Union

from aioredis.client import Redis, ConnectionPool, PubSub
from aioredis.exceptions import ConnectionError


class RedisEngine:
    core: Redis
    pool: ConnectionPool

    def __init__(self, url: str):
        self.url = url

    def connect_to_server(self):
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

    async def close(self):
        if self.core:
            await self.pool.disconnect()
            await self.core.close()

    async def set(self, name: str, value: Union[str, int, float], expire: int = None) -> bool:
        return await self.core.set(name, value, ex=expire)

    async def get(self, name: str) -> str:
        return await self.core.get(name)

    async def get_all(self) -> dict:
        keys = await self.core.keys()
        data = await self.core.mget(keys)
        return dict(zip(keys, data))

    async def delete(self, *names: str) -> int:
        return await self.core.delete(*names)

    async def clear(self):
        await self.core.delete(await self.core.keys())

    def get_pubsub(self, **kwargs) -> PubSub:
        return self.core.pubsub(**kwargs)

    async def publish(self, channel: str, message: Union[str, int, float]) -> int:
        return await self.core.publish(channel, message)
