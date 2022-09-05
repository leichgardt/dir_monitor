"""Byte decoder"""

from typing import Iterable


__all__ = ('recursive_decode',)


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
