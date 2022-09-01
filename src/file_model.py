from datetime import datetime
from typing import Dict, Union

from pydantic import BaseModel


class File(BaseModel):
    file: str
    data: Dict[str, Union[datetime, str]]

    def to_obj(self):
        return [self.file, {k: str(v) if isinstance(v, datetime) else v for k, v in self.data.items()}]


if __name__ == '__main__':
    f = File(file='test.mp3', data={'status': 'new', 'time': datetime.now()})
    print(f)
    print(f.to_obj())
