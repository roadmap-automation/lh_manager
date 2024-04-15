"""Autocontrol task definition"""

from enum import Enum
from .items import Item

from pydantic.v1.dataclasses import dataclass

from dataclasses import field
from typing import List, Tuple

class TaskType(str, Enum):
    NONE = 'none'
    INIT = 'init'
    PREPARE = 'prepare'
    TRANSFER = 'transfer'
    MEASURE = 'measure'

@dataclass
class TaskData:
    device: str = ''
    channel: int | None = None
    method_data: dict = field(default_factory=dict)

@dataclass
class Task:
    id: str | None = None
    tasks: List[TaskData] = field(default_factory=list)
    task_type: TaskType = TaskType.NONE
    md: dict = field(default_factory=dict)
