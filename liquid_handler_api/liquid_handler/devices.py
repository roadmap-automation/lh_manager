from dataclasses import fields
from pydantic import BaseModel
from typing import Dict, List, Literal, Union, Set, ClassVar
from .job import JobBase

EXCLUDE_FIELDS = set([])

class DeviceBase(BaseModel):
    """Base class for device definitions
    """

    device_name: ClassVar[str] = 'none'
    device_type: str = 'none'
    multichannel: bool = False
    allow_sample_mixing: bool = False
    address: str = 'http://0.0.0.0:0000'

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

        return {'method_list': method_list}


### =========== Methods manager ==============

DevicesType = Union[DeviceBase]

class DeviceManager:
    """Convenience class for managing devices."""

    def __init__(self) -> None:

        self.devices: Dict[str, DevicesType] = {}

    @property
    def device_list(self) -> List[DevicesType]:
        return self.devices.values()

    def register(self, device: DeviceBase) -> None:
        """Registers a device in the manager

        Args:
            device (DeviceBase): method to register
        """

        self.devices.update({device.device_name: device})

    def get_all_schema(self) -> Dict[str, Dict]:
        """Gets the schema of all the devides in the manager

        Returns:
            Dict[str, Dict]: Dictionary of devices names and schema. Schema has fields 'fields', 
                                'display_name', and 'schema'; the last is the pydantic schema
        """

        lh_method_fields: Dict[str, Dict] = {}
        for device in self.devices.values():
            fieldlist = []
            for fi in fields(device):
                if not fi.name in EXCLUDE_FIELDS:
                    fieldlist.append(fi.name)
            lh_method_fields[device.device_name] = {'fields': fieldlist, 'device_name': device.device_name, 'schema': device.model_json_schema()}

        return lh_method_fields
    
    def get_device_by_name(self, device_name: str) -> DevicesType:
        """Gets device object by name

        Args:
            device_name (str): device name

        Returns:
            DevicesType: device class
        """

        return self.devices[device_name]

device_manager = DeviceManager()

def register_device(cls):
    """Decorator to register a class
    """
    device_manager.register(cls)
    return cls