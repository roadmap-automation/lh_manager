from .bedlayout import LHBedLayout
from .methods import BaseMethod, MethodType, register
from .devices import DeviceBase, device_manager
from .job import JobBase

from dataclasses import field
from pydantic import BaseModel
from typing import List, Literal, ClassVar

class RinseSystemDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: Literal['Rinse System Device'] = 'Rinse System Device'
    device_type: Literal['rinse'] = 'rinse'
    multichannel: bool = False
    allow_sample_mixing: bool = False
    address: str = 'http://localhost:5014'

    class Job(JobBase):
        pass

rinsedevice = RinseSystemDevice()
device_manager.register(rinsedevice)

class BaseRinseMethod(BaseMethod):
    """Base class for LH methods"""

    method_type: Literal[MethodType.NONE] = MethodType.NONE
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    class sub_method(BaseModel):
        """Base class for representation in sample lists"""
        method_name: str
        method_data: dict = field(default_factory=dict)

        def to_dict(self) -> dict:
            """Creates dictionary representation; all custom field keys are prepended with a hash (#)
            Returns:
                dict: dictionary representation
            """

            d2 = {rinsedevice.device_name: [self.model_dump()]}

            return d2

@register
class RinseInitiateTransfer(BaseRinseMethod):
    """Register a solution in the QCMD instrument"""
    display_name: Literal['Initiate Rinse'] = 'Initiate Rinse'
    method_name: Literal['InitiateRinse'] = 'InitiateRinse'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data={}
                                ).to_dict()]
    