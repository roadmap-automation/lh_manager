from pydantic import BaseModel, Field, validator
from enum import Enum
from copy import copy
from typing import Any, Dict, List, Literal, Union, Set, ClassVar
from uuid import uuid4

from .bedlayout import LHBedLayout
from .status import MethodError, SampleStatus

EXCLUDE_FIELDS = set(["method_name", "display_name", "complete", "method_type", "id", "tasks", "status"])

## ========== Base Methods specification =============

class MethodType(str, Enum):
    NONE = 'none'
    CONTAINER = 'container'
    TRANSFER = 'transfer'
    MIX = 'mix'
    INJECT = 'inject'
    PREPARE = 'prepare'
    MEASURE = 'measure'

class TaskContainer(BaseModel):
    id: str | None = None
    task: Any = Field(default_factory=dict)
    status: SampleStatus | None = None

class BaseMethod(BaseModel):
    """Base class for LH methods"""

    id: str | None = None
    tasks: list[TaskContainer] = Field(default_factory=list)
    status: SampleStatus = SampleStatus.INACTIVE
    method_name: Literal['BaseMethod'] = 'BaseMethod'
    display_name: Literal['BaseMethod'] = 'BaseMethod'
    method_type: Literal[MethodType.NONE] = MethodType.NONE
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    def model_post_init(self, __context):
        
        if self.id is None:
            self.id = str(uuid4())

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Actions to be taken upon executing method. Default is nothing changes"""
        return None
    
    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns new sample composition if applicable"""
        
        return ''

    def estimated_time(self, layout: LHBedLayout) -> float:
        """Estimated time for method in default time units"""
        return 0.0

    def get_methods(self, layout: LHBedLayout) -> List:
        return [self]
    
    def explode(self, layout: LHBedLayout) -> List:
        return self.get_methods(layout)
    
    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        """Renders the lh_method class to a Gilson LH-compatible format"""
        
        return [{}]

class MethodContainer(BaseMethod):
    """Special method that generates a list of basic methods when rendered"""

    method_type: Literal[MethodType.CONTAINER] = MethodType.CONTAINER
    method_name: Literal['MethodContainer'] = 'MethodContainer'
    display_name: Literal['MethodContainer'] = 'MethodContainer'

    def get_methods(self, layout: LHBedLayout) -> List[BaseMethod]:
        """Generates list of methods. Intended to be superceded for specific applications

        Args:
            layout (LHBedLayout): layout to use for generating method list

        Returns:
            List[BaseMethod]: list of base methods
        """

        return []

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Returns the error if any of the submethods give errors"""
        for m in self.get_methods(layout):
            error = m.execute(layout)
            if error is not None:
                return MethodError(f'{self.display_name}.{error.name}', error.error)

    def estimated_time(self, layout: LHBedLayout) -> float:
        return sum(m.estimated_time() for m in self.get_methods(layout))
    
    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        rendered_methods = []
        for m in self.get_methods(layout):
            rendered_methods += m.render_method(sample_name=sample_name,
                                                   sample_description=sample_description,
                                                   layout=layout)
        return rendered_methods

### =========== Methods manager ==============

MethodsType = Union[BaseMethod, MethodContainer]

class MethodManager:
    """Convenience class for managing methods."""

    def __init__(self) -> None:

        self.method_list: Set[MethodsType] = set()

    def register(self, method: MethodsType) -> None:
        """Registers a method in the manager

        Args:
            method (BaseMethod): method to register
        """

        self.method_list.add(method)

    def get_all_schema(self) -> Dict[str, Dict]:
        """Gets the schema of all the methods in the manager

        Returns:
            Dict[str, Dict]: Dictionary of method names and schema. Schema has fields 'fields', 
                                'display_name', and 'schema'; the last is the pydantic schema
        """

        lh_method_fields: Dict[str, Dict] = {}
        for method in self.method_list:
            fieldlist = []
            for name, fi in method.model_fields.items():
                if not name in EXCLUDE_FIELDS:
                    fieldlist.append(name)
            lh_method_fields[method.model_fields['method_name'].default] = {'fields': fieldlist, 'display_name': method.model_fields['display_name'].default, 'schema': method.model_json_schema(mode='serialization')}

        return lh_method_fields
    
    def get_method_by_name(self, method_name: str) -> MethodsType:
        """Gets method object by name

        Args:
            method_name (str): method name

        Returns:
            MethodsType: method class
        """

        try:
            return next(m for m in self.method_list if m.model_fields['method_name'].default == method_name)
        except StopIteration:
            print(f'{method_name} not found')
            return BaseMethod

method_manager = MethodManager()

def register(cls):
    """Decorator to register a class
    """
    method_manager.register(cls)
    return cls

## ========== Methods specification =============
# methods must be registered in methods manager

@register
class Release(BaseMethod):
    """Special method that does nothing except "release" the liquid handler, i.e. signal to
        the software that other higher priority methods can be inserted at this position and run in the interim.
        
        Basic usage is that groups of methods that need to be clustered are separated by this method, i.e.      
        this method is used to separate the individual groups of methods into individual jobs."""
    
    display_name: Literal['---release---'] = '---release---'
    method_name: Literal[''] = ''
