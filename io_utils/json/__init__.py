from abc import ABC
from pathlib import Path
from typing_extensions import Self
from typing import Union
import json

class JSONable(ABC):
    def to_json(self, destination_file: Union[str,Path]) -> None:
        with open(destination_file, '+w') as file:
            json.dump(self.__dict__, file)

    def to_json_str(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, file_path: Union[str,Path]) -> Self:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return cls(**data)

    @classmethod
    def from_json_str(cls, data: str) -> Self:
        return cls(**json.loads(data))    


class JSONableDataclass(JSONable):
    def to_json(self, destination_file: Union[str,Path]) -> None:
        return super().to_json(destination_file)        

    def to_json_str(self) -> str:
        return super().to_json_str()

    @classmethod
    def from_json(cls, file_path: Union[str,Path]) -> Self:
        return super().from_json(file_path)

    @classmethod
    def from_json_str(cls, data: str) -> Self:
        return super().from_json_str(data)

