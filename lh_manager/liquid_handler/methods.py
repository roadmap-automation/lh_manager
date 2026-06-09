import functools
import logging

from pydantic import BaseModel, Field, validator, model_serializer
from enum import Enum
from typing import Any, Dict, List, Literal, Union
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
    
class RawMethod(BaseMethod):
    """Passthrough container for a method whose schema is not registered locally.

    Stores the full raw dict in method_data so it can be forwarded to the broker
    without modification. The inherited id/status/tasks fields preserve in-flight
    tracking state across serialization cycles. method_type is populated from
    the stored dict so autocontrol can determine TaskType without a local class.

    method_name and display_name are non-Literal so they can carry the real device
    method name (e.g. 'InjectLoop') instead of the class name 'RawMethod'. This
    allows the frontend schema lookup (method_defs[method_name]) to find the schema.
    model_dump() emits a flat representation (method_data fields + tracking fields)
    so the frontend sees an identical structure to locally-registered methods.
    """
    method_name: str = 'RawMethod'
    display_name: str = 'RawMethod'
    method_type: MethodType = MethodType.NONE
    method_data: dict = Field(default_factory=dict)

    @model_serializer(mode='plain')
    def _flat_serialize(self) -> dict:
        """Flat serialization: method_data fields merged with tracking state.

        Uses @model_serializer so this is called by parent models (e.g. MethodList)
        as well as direct model_dump() calls. The frontend reads method[field_name]
        directly, so device-specific fields must be at the top level. Tracking fields
        (id, status, tasks, method_type) overlay whatever is in method_data so the
        backend round-trip is lossless — method_type must survive so that
        __method_group__ RawMethods retain their TaskType after deserialization.
        """
        base = dict(self.method_data)
        base['id'] = self.id
        base['status'] = self.status
        base['tasks'] = [t.model_dump() for t in self.tasks]
        base['method_type'] = self.method_type.value if isinstance(self.method_type, MethodType) else str(self.method_type)
        return base

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        return []

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
        return sum(m.estimated_time(layout) for m in self.get_methods(layout))
    
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


def _flatten_allof_refs(schema: dict) -> None:
    """In-place: replace allOf([{$ref: X}]) with {$ref: X} in schema properties.

    Pydantic v2 wraps a $ref in allOf when the field carries extra keywords
    (e.g. a default value).  JSON Schema allows allOf([A]) ≡ A, so flattening
    is semantically correct and makes the frontend '$ref' in prop check work.
    """
    for prop in schema.get('properties', {}).values():
        if (isinstance(prop, dict)
                and 'allOf' in prop
                and len(prop['allOf']) == 1
                and '$ref' in prop['allOf'][0]):
            ref = prop['allOf'][0]['$ref']
            prop.clear()
            prop['$ref'] = ref


class RegisteredMethod:

    def __init__(self, method: MethodsType, display: bool = True, origin: str | None = None) -> None:
        self.method = method
        self.display = display
        self.origin = origin

    @property
    def display_name(self) -> str:
        return self.method.model_fields['display_name'].default
    
    @property
    def name(self) -> str:
        return self.method.model_fields['method_name'].default

    def get_schema(self):
        schema = self.method.model_json_schema(mode='serialization')
        _flatten_allof_refs(schema)
        return {'fields': [name for name in self.method.model_fields.keys() if name not in EXCLUDE_FIELDS],
                'display': self.display,
                'display_name': self.display_name,
                'origin': self.origin,
                'schema': schema}

class MethodManager:
    """Convenience class for managing methods."""

    def __init__(self) -> None:

        self.methods: dict[str, RegisteredMethod] = {}
        # Schemas received from remote devices via device.registered broker events.
        self._remote_schemas: dict[str, dict] = {}

    def register(self, method: MethodsType, display: bool = True, origin: str | None = None) -> None:
        """Registers a method in the manager

        Args:
            method (BaseMethod): method to register
            display (bool): whether to display the method in
        """
        rmethod = RegisteredMethod(method, display=display, origin=origin)
        self.methods[rmethod.name] = rmethod

    def register_schema(self, name: str, schema: dict) -> None:
        """Register a method schema received from a remote device.

        Merges into get_all_schema() so the frontend sees device-provided methods
        without requiring a local Pydantic class.
        """
        self._remote_schemas[name] = schema

    def get_all_schema(self) -> Dict[str, Dict]:
        """Gets the schema of all the methods in the manager

        Returns:
            Dict[str, Dict]: Dictionary of method names and schema. Schema has fields 'fields',
                                'display_name', and 'schema'; the last is the pydantic schema
        """

        result = {k: rm.get_schema() for k, rm in self.methods.items()}
        result.update(self._remote_schemas)
        return result
    
    def get_method_by_name(self, method_name: str) -> MethodsType:
        """Gets method object by name

        Args:
            method_name (str): method name

        Returns:
            MethodsType: method class
        """

        try:
            return self.methods[method_name].method
        except KeyError:
            logging.error(f'{method_name} not found')
            return BaseMethod

method_manager = MethodManager()

def register(display: bool = True, origin: str | None = None):
    """Decorator factory to register a class with an origin classification
    """
    
    def decorator(cls):
        method_manager.register(cls, display=display, origin=origin)
        return cls
    
    return decorator

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
