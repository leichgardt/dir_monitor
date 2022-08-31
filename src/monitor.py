import asyncio
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, Generator

from art import tprint

from src.cache_engine import RedisEngine
from src.logger import Logger


REDIS_CHANNEL = os.environ.get('REDIS_FW_CHANNEL', 'file_watcher')
logger = Logger.with_default_handlers()


def get_root_path(path: Path, depth: int) -> str:
    return '/'.join(path.parts[:depth]) + '/'


def get_files(path: Path) -> Generator[Path, None, None]:
    return path.glob('[!_.]*')


def get_files_and_modified_time(
        path: Path,
        *,
        recursive: bool = True,
        depth: int = 1
) -> Generator[Tuple[str, datetime], None, None]:
    root_path = '' if depth == 1 else get_root_path(path, depth)
    depth += 1
    files = get_files(path)
    for file in files:
        if recursive and file.is_dir():
            yield from get_files_and_modified_time(file, depth=depth)
        else:
            filepath = root_path + file.name + ('/' if file.is_dir() else '')
            modified_time = datetime.fromtimestamp(file.stat().st_mtime)
            yield filepath, modified_time


class FileWatcher:

    def __init__(self, dir_path: Path, cache_url: str, sleep_time: float):
        self.path = dir_path
        self.cache = RedisEngine(cache_url)
        self.sleep_time = sleep_time

    def start(self, loop: asyncio.AbstractEventLoop = None):
        if not loop:
            loop = asyncio.get_event_loop()
        loop.run_until_complete(self.watch_files())

    async def watch_files(self):
        await logger.info('File watcher starts')
        saved_file_data = {}
        await self._pre_start(saved_file_data)
        while True:
            try:
                checked_files = await self._check_files(saved_file_data)
                await self.broadcast_new_file_data(checked_files)
            except KeyboardInterrupt:
                return
            except Exception as e:
                await logger.error(f'File watcher error: {e}')
            else:
                await asyncio.sleep(self.sleep_time)

    async def _pre_start(self, saved_files: dict):
        await self.cache.clear()
        for file, m_time in get_files_and_modified_time(self.path):
            saved_files[file] = m_time
            await self.cache.set(file, str(m_time))
        await asyncio.sleep(self.sleep_time)

    async def _check_files(self, saved_files: dict):
        """File data duplicates twice: in the monitor and in Redis (for more reactivity)."""
        checked_files = {}
        for file, m_time in get_files_and_modified_time(self.path):
            result = self._check_file(saved_files, file, m_time)
            if result:
                if result == 'new':
                    checked_files[file] = {'status': 'new', 'time': str(m_time)}
                elif result == 'update':
                    checked_files[file] = {'status': 'updated', 'time': str(m_time)}
                saved_files[file] = m_time
                await self.cache.set(file, str(m_time))
        for file in self._get_missing_files(saved_files, checked_files):
            checked_files[file] = {'status': 'deleted'}
            saved_files.pop(file)
            await self.cache.delete(file)
        return checked_files

    @staticmethod
    async def _check_file(saved_files: dict, file: str, m_time: datetime) -> str:
        if file not in saved_files:
            return 'new'
        else:
            if saved_files[file] != m_time:
                return 'update'
        return ''

    @staticmethod
    def _get_missing_files(saved_files: dict, checked_files: dict) -> set:
        return set(saved_files.keys()) - set(checked_files.keys())

    async def broadcast_new_file_data(self, file_data: dict):
        await logger.info(f'Updated files: {len(file_data)}')
        await self.cache.publish(REDIS_CHANNEL, json.dumps(file_data))


def main():
    tprint('Dir Monitor')

    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help='Path to directory to monitoring')
    parser.add_argument('--url', '-u', dest='url', type=str, default='redis://localhost/0',
                        help='Redis URL like redis://[[username]:[password]]@localhost:6379/0, '
                             'default: redis://localhost/0')
    parser.add_argument('--sleep-time', '-s', dest='sleep', type=int, default=1,
                        help='Cycle sleep time, default: 1')

    args = parser.parse_args()
    path = Path(args.path)
    if not path.is_dir():
        print('Is is not a directory')
    else:
        print(path.resolve())
        watcher = FileWatcher(path, args.url, args.sleep)
        watcher.start()


if __name__ == '__main__':
    main()
