"""Recursive generator to walk at directories and get files"""

from datetime import datetime
from pathlib import Path
from typing import Tuple, Generator


__all__ = ('get_files_and_their_modification_time',)


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
