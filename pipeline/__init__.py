from abc import ABC, abstractmethod
from typing import Iterable, TypeVar, Generic, Optional, List, Callable, Dict, Any
from uuid import uuid4
from dataclasses import dataclass
from queues import MessageQueue, InspectionOperation, InspectionResult

M = TypeVar('M')

@dataclass
class PipelineMessage(Generic[M]):
    from_job: str # id of the job that created the message
    data: M
    max_hops: Optional[int]

class PipelineJob(ABC):

    def __init__(self, name: str):
        self.name = name
        self.id: Optional[str] = None

    def configure(self, id: str, pipeline: 'Pipeline') -> None:
        self.id = id
        self.pipeline = pipeline
    
    def push_message(self, queue_name: str, message: Any) -> None:
        self.pipeline.push_message(queue_name, message)

    def pop_message(self, queue_name: str) -> Optional[Any]:
        return self.pipeline.pop_message(queue_name)
    
    def peek_message(self, queue_name: str) -> Optional[Any]:
        return self.pipeline.peek_message(queue_name)
    
    def set_state(self, path: str, value: Any) -> None:
        self.pipeline.set_state(path, value)

    def get_state(self, path: str) -> Any:
        self.pipeline.get_state(path)

    def update_state(self, path: str, update: Callable[[Any], Any]) -> None:
        self.update_state(path, update)

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError('Abstract method must be implemented')
    
class Pipeline:

    def __init__(self) -> None:
        #configurations
        self.__global_state = dict()
        self.__queues: Dict[str, MessageQueue] = dict()

    def prepare(self, jobs: Iterable[PipelineJob]):
        self.jobs = jobs
        for j in self.jobs:
            j.configure(id=uuid4(),pipeline=self)

    def run(self, **kwargs) -> Dict[str, Any]:
        args: Dict = kwargs
        for j in self.jobs:
            args = j.run(**args)
        return args
    
    ####### State operations
    def __parse_path(self, path: str) -> List[str]:
        return path.split('.')
    
    def get_state(self, path: str) -> Any:
        path_sections = self.__parse_path(path)
        res = self.__global_state
        for section in path_sections:
            res = res.get(section, None)
            if res is None:
                break
        return res

    def update_state(self, path: str, update: Callable[[Any], Any]) -> None:
        path_sections = self.__parse_path(path)
        state = self.__global_state
        for section in path_sections[:-1]:
            if state.get(section) is None:
                state[section] = dict()
            state = state[section]
        state[path_sections[-1]] = update(state.get(path_sections[-1]))

    def set_state(self, path: str, value: Any) -> None:
        self.update_state(path, lambda _: value)

    ####### Queue operations
    def add_queue(self, name: str, initial_items: Optional[Iterable]=None) -> MessageQueue:
        self.__queues[name] = MessageQueue(name, initial_items)
        return self.__queues[name]
    
    def get_queue(self, name: str) -> Optional[MessageQueue]:
        return self.__queues.get(name)
    
    def push_message(self, queue_name: str, message: Any) -> None:
        queue = self.get_queue(queue_name)
        if queue is None:
            self.add_queue(queue_name, [message])
            return
        queue.enqueue(message)

    def pop_message(self, queue_name: str) -> Optional[Any]:
        queue = self.get_queue(queue_name)
        if queue is None:
            return None
        return queue.dequeue()
    
    def peek_message(self, queue_name: str) -> Optional[Any]:
        queue = self.get_queue(queue_name)
        if queue is None:
            return None
        return queue.peek()

    def __inspect_message(index: int, message: PipelineMessage) -> InspectionResult[PipelineMessage]:
        if message.max_hops is not None:
            message.max_hops -= 1
            if message.max_hops < 0:
                return InspectionResult(InspectionOperation.DELETE, None)
        
    