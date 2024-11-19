"""Autocontrol task definition"""

from enum import Enum
from .items import Item

from pydantic import BaseModel

from dataclasses import field
from typing import List, Tuple

class TaskType(str, Enum):
    NONE = 'none'
    INIT = 'init'
    PREPARE = 'prepare'
    TRANSFER = 'transfer'
    MEASURE = 'measure'

class TaskData(BaseModel):
    device: str = ''
    channel: int | None = None
    method_data: dict = field(default_factory=dict)

class Task(BaseModel):
    id: str | None = None
    tasks: List[TaskData] = field(default_factory=list)
    task_type: TaskType = TaskType.NONE
    md: dict = field(default_factory=dict)
