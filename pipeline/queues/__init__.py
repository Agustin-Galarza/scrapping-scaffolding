from typing import Iterable, TypeVar, Generic, Optional, Iterator, List, Callable, Dict, Any
from uuid import uuid4
from dataclasses import dataclass
from enum import Enum

T = TypeVar('T')

class InspectionOperation(Enum):
    NONE = 1
    PUT = 2
    DELETE = 3

@dataclass
class InspectionResult(Generic[T]):
    operation: InspectionOperation
    value: Optional[T]

class MessageQueue(Generic[T], Iterator[T]):
    def __init__(self, name: Optional[str] = None, initial_items: Iterable[T] = []) -> None:
        self.name = name if name is not None else f'queue-{uuid4()}'
        self.__items: List[T] = list(initial_items)
        self.__size = len(self.__items)
        self.__iterating = False

    def enqueue(self, item: T) -> None:
        if self.__iterating:
            raise Exception('Cannot add items to the queue while iterating over it')
        self.__size += 1
        self.__items.append(item)

    def dequeue(self) -> T:
        if self.is_empty():
            self.__iterating = False
            raise StopIteration
        self.__size -= 1
        return self.__items.pop(0)

    def peek(self) -> T:
        return self.__items[0]
    
    def inspect(self, inspector: Callable[[int, T],InspectionResult[T]]) -> None:
        """
        Calls an inspector function with each message in the queue and its index, without dequeueing any item.
        For each value the function must return an InspectionResult, which can decide whether to either do nothing, replace the item or remove the item
        """
        if self.__iterating:
            raise Exception('Cannot do a queue inspection while iterating through the queue')
        for index, item in enumerate(self.__items):
            res = inspector(index, item)
            if res.operation == InspectionOperation.PUT:
                self.__items[index] = res
            elif res.operation == InspectionOperation.DELETE:
                self.__items.pop(index)
    
    def is_empty(self) -> bool:
        return self.__size == 0

    def __iter__(self):
        self.__iterating = True
        return self
    
    def __next__(self) -> T:
        return self.dequeue()
    
    def keys(self):
        return ["name", "items"]
    
    def __getitem__(self, key):
        if key == 'name':
            return self.name
        elif key == 'items':
            return self.__items
        return None

