from dataclasses import fields, field, asdict
from pydantic.v1.dataclasses import dataclass
from enum import Enum
from copy import copy
from typing import Dict, List, Literal, Union, Set

EXCLUDE_FIELDS = set([])

@dataclass
class DeviceBase:
    """Base class for device definitions
    """

    device_name: Literal['none'] = 'none'

    def create_task_data(self, method_data: dict) -> dict:
        """Creates a task formatted for the appropriate device

        Args:
            method_data (dict): method data to format

        Returns:
            dict: task data
        """

        raise NotImplementedError

### =========== Methods manager ==============

DevicesType = Union[DeviceBase]

class DeviceManager:
    """Convenience class for managing devices."""

    def __init__(self) -> None:

        self.device_list: Set[DevicesType] = set()

    def register(self, device: DeviceBase) -> None:
        """Registers a device in the manager

        Args:
            device (DeviceBase): method to register
        """

        self.device_list.add(device)

    def get_all_schema(self) -> Dict[str, Dict]:
        """Gets the schema of all the devides in the manager

        Returns:
            Dict[str, Dict]: Dictionary of devices names and schema. Schema has fields 'fields', 
                                'display_name', and 'schema'; the last is the pydantic schema
        """

        lh_method_fields: Dict[str, Dict] = {}
        for device in self.device_list:
            fieldlist = []
            for fi in fields(device):
                if not fi.name in EXCLUDE_FIELDS:
                    fieldlist.append(fi.name)
            lh_method_fields[device.device_name] = {'fields': fieldlist, 'device_name': device.device_name, 'schema': device.__pydantic_model__.schema()}

        return lh_method_fields
    
    def get_device_by_name(self, device_name: str) -> DevicesType:
        """Gets device object by name

        Args:
            device_name (str): device name

        Returns:
            DevicesType: device class
        """

        return next(m for m in self.device_list if m.device_name == device_name)

device_manager = DeviceManager()

def register_device(cls):
    """Decorator to register a class
    """
    device_manager.register(cls)
    return cls