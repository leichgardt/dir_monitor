import asyncio
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, List, Union, Generator

from art import tprint

from src.cache_engine import RedisEngine
from src.logger import logger
from src.file_model import File


REDIS_CHANNEL = os.environ.get('REDIS_FW_CHANNEL', 'file_watcher')


def get_root_path(path: Path, depth: int) -> str:
    return '/'.join(path.parts[:depth]) + '/'


def get_files(path: Path) -> Generator[Path, None, None]:
    return path.glob('[!_.]*')


def get_files_and_their_modification_time(
        path: Path,
        *,
        recursive: bool = True,
        depth: int = 1
) -> Generator[Tuple[str, datetime], None, None]:
    root_path = '' if depth == 1 else get_root_path(path, depth)
    depth += 1
    for file in get_files(path):
        if recursive and file.is_dir():
            yield from get_files_and_their_modification_time(file, depth=depth)
        else:
            filepath = root_path + file.name + ('/' if file.is_dir() else '')
            modified_time = datetime.fromtimestamp(file.stat().st_mtime)
            yield filepath, modified_time


class FileWatcher:

    def __init__(self, dir_path: Path, cache_url: str, sleep_time: float):
        self.path = dir_path
        self.cache = RedisEngine(cache_url)
        self.sleep_time = sleep_time
        self.saved_files = {}

    def start(self, loop: asyncio.AbstractEventLoop = None):
        if not loop:
            loop = asyncio.get_event_loop()
        self.cache.connect_to_server()
        loop.run_until_complete(self.watch_files())

    async def watch_files(self):
        logger.info('File watcher starts')
        await self._pre_start()
        while True:
            try:
                checked_files = await self.check_and_handle_files()
                updated_files = [File(file=file, data=data).to_obj() for file, data in checked_files.items() if data]
                if updated_files:
                    await self.broadcast_new_file_data(updated_files)
            except KeyboardInterrupt:
                return
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.exception(f'File watcher error: {e}')
                exit()
            else:
                await asyncio.sleep(self.sleep_time)

    async def _pre_start(self):
        await self.cache.clear()
        logger.info('Cache server clear')
        for file, m_time in get_files_and_their_modification_time(self.path):
            self.saved_files[file] = m_time
            await self.cache.set(file, str(m_time))
        logger.info(f'Loaded files: {len(self.saved_files)}')
        await asyncio.sleep(self.sleep_time)

    async def check_and_handle_files(self) -> Dict[str, Dict[str, Union[str, datetime]]]:
        """File data duplicates twice: in the monitor and in Redis (for more reactivity)."""
        checked_files = {}
        for file, m_time in self.get_files_to_load(checked_files):
            if await self.cache.set(file, str(m_time)):
                logger.debug(f'File "{file}" has been loaded to cache')
        missed_files = list(self._get_missed_files_to_delete(checked_files))
        if missed_files:
            await self.cache.delete(*missed_files)
            for file in missed_files:
                self.saved_files.pop(file)
            logger.info(f'Deleted missing files: {len(missed_files)}')
        return checked_files

    def get_files_to_load(self, checked_files: dict) -> Generator[Tuple[str, datetime], None, None]:
        for file, m_time in get_files_and_their_modification_time(self.path):
            file_status = self.get_file_status(file, m_time)
            if file_status:
                logger.debug(f'File "{file}". Result={file_status}')
                if file_status == 'new':
                    checked_files[file] = {'status': 'new', 'time': str(m_time)}
                elif file_status == 'update':
                    checked_files[file] = {'status': 'updated', 'time': str(m_time)}
                self.saved_files[file] = m_time
                yield file, m_time
            else:
                checked_files[file] = None  # status: file not changed

    def get_file_status(self, file: str, m_time: datetime) -> str:
        if file not in self.saved_files:
            return 'new'
        elif self.saved_files[file] != m_time:
            return 'update'
        else:
            return ''
    
    def _get_missed_files_to_delete(self, checked_files: dict) -> Generator[str, None, None]:
        for file in self._get_missing_files(checked_files):
            logger.debug(f'Missed file "{file}". Deleting')
            checked_files[file] = {'status': 'deleted'}
            yield file

    def _get_missing_files(self, checked_files: dict) -> Generator[str, None, None]:
        return (file for file in self.saved_files.keys() if file not in checked_files)

    async def broadcast_new_file_data(self, file_data: List[File]):
        await self.cache.publish(REDIS_CHANNEL, json.dumps(file_data))
        logger.info(f'Updated files: {len(file_data)}')


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
