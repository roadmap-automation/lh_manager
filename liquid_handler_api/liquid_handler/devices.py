from dataclasses import fields
from pydantic.v1.dataclasses import dataclass
from typing import Dict, List, Literal, Union, Set
from .job import JobBase

EXCLUDE_FIELDS = set([])

@dataclass
class DeviceBase:
    """Base class for device definitions
    """

    device_name: str = 'none'
    device_type: str = 'none'
    multichannel: bool = False
    address: str = 'http://0.0.0.0:0000'

    @classmethod
    def is_multichannel(cls) -> bool:
        """Determines if device is a multichannel device

        Returns:
            bool: True if multichannel, False if not
        """

        return cls.multichannel

    @dataclass
    class Job(JobBase):
        pass

    @staticmethod
    def create_job_data(method_list: List[dict]) -> dict:
        """Creates a task formatted for the appropriate device

        Args:
            method_list (List[dict]): method data to format

        Returns:
            dict: task data
        """

        return {}

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