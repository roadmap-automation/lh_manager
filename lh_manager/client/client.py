"""Client for LH Manager"""

import concurrent.futures
import json
import requests
import time

from pprint import pprint
from threading import Event
from urllib.parse import urljoin

from ..material_db.db import Material
from ..liquid_handler.bedlayout import LHBedLayout, Solvent, Solute
from ..liquid_handler.methods import BaseMethod
from ..liquid_handler.samplelist import Sample

MANAGER_ADDRESS = 'http://localhost:5001'

class ManagerClient:
    samples: dict[str, dict] = {}
    layout: LHBedLayout = LHBedLayout()
    materials: dict[str, Material] = {}

    def __init__(self, address: str = MANAGER_ADDRESS):
        self.address = address

    def initialize(self):
        self.load_materials()
        self.get_layout()
        self.get_samples()

    def load_materials(self) -> dict[str, Material]:
        """Returns and caches dictionary of materials

        Returns:
            dict[str, Material]: dictionary of materials with material name as key
        """

        all_materials: list[dict] = requests.get(urljoin(self.address, '/Materials/all/')).json()['materials']

        self.materials = {v['name']: Material(**v) for v in all_materials}
        return self.materials

    def get_samples(self) -> dict[str, dict]:
        """Returns and caches dictionary of samples. Note that samples are not attempted to be
            rehydrated into Sample objects

        Returns:
            dict[str, dict]: dictionary of samples with sample id as key
        """
        
        samples: list[dict] = requests.get(urljoin(self.address, '/GUI/GetSamples/')).json()['samples']

        self.samples = {s['id']: s for s in samples['samples']}

        return self.samples

    def get_layout(self) -> LHBedLayout:
        """Returns and caches bed layout.

        Returns:
            LHBedLayout: bed layout
        """

        self.layout = LHBedLayout.model_validate(requests.get(urljoin(self.address, '/GUI/GetLayout/')).json())
        return self.layout

    @property
    def sample_ids(self) -> list[str]:

        return list(self.samples.keys())

    def new_sample(self, sample: Sample) -> Sample:

        if sample not in self.sample_ids:
            _, sample = self.update_sample(sample)

        return sample
        
    def update_sample(self, sample: Sample) -> tuple[str, Sample]:

        response: dict[str, str] = requests.post(urljoin(self.address, '/GUI/UpdateSample/'), data=sample.model_dump_json()).json()

        # should return {'sample added': id} or {}'sample updated': id}

        self.get_samples()

        return list(response.values())[0], self.rehydrate_sample(sample.id)

    def rehydrate_sample(self, sample_id: str) -> Sample:

        return Sample.model_validate(self.samples[sample_id])
    
    def archive_sample(self, sample: Sample) -> dict:

        response: dict[str, str] = requests.post(urljoin(self.address, '/GUI/ArchiveandRemoveSample/'), data=json.dumps(dict(id=sample.id))).json()
        self.get_samples()

        return response

    def run_sample(self, sample_id: str) -> tuple[str, Sample]:

        sample = self.samples[sample_id]
        response: dict = requests.post(urljoin(self.address, '/GUI/RunSample/'), json={'name': sample['name'], 'id': sample['id'], 'uuid': sample.get('uuid', None), 'slotID': None, 'stage': ['methods']}).json()
        self.get_samples()
        return response, self.rehydrate_sample(sample_id)

    def get_task_complete(self, task_id: str) -> str | dict:

        response = requests.get(urljoin(self.address, '/autocontrol/GetTaskStatus'), json={'task_id': task_id})
        try:
            resp: dict = response.json()
        except json.JSONDecodeError:
            return {'error': 'json could not be decoded'}
        
        if not response.ok:
            return {'error': resp}

        if resp.get('queue', '') == 'history':
            return {'success': 'complete'}
        
        return {}

    def monitor_task(self, task_id: str, thread_result: dict, poll_interval: float = 5, stop_event: Event = Event()) -> str:
        current_status = {}
        while (current_status.get('success', 'incomplete') == 'incomplete') & (not stop_event.is_set()):
            time.sleep(poll_interval)
            current_status = self.get_task_complete(task_id=task_id)
        
        thread_result['result'] = current_status

    def get_task_result(self, task_id: str, subtask_id: str) -> dict:

        data = dict(task_id=task_id,
                    subtask_id=subtask_id)

        response: dict = requests.get(urljoin(self.address, '/autocontrol/GetTaskResult'), json=data).json()

        return response

    def wait_for_result(self, sample: Sample, measure_method_id: str, stop_event: Event = Event()) -> dict:
        """Waits for the result of a method

        Args:
            sample (Sample): sample object containing the method
            measure_method_id (str): id of method to wait for
            stop_event (Event, optional): stop thread-safe event. When set, cancels the waiting. Defaults to Event().

        Returns:
            dict: measurement result
        """

        # extract task_id and subtask_id for measurement task (assumed to be last task in the method)
        measure_method: BaseMethod = next((m for m in sample.stages['methods'].active if m.id == measure_method_id), None)
        if measure_method is None:
            print(f'Warning: no active tasks found with sample {sample.id} and method {measure_method_id}')
            return
        
        task = measure_method.tasks[-1]
        subtask_id = task.task['tasks'][-1].get('id', None)

        print(f'\tSubtask id: {subtask_id}')
        # wait until measurement is complete and then read the result
        thread_result = dict(result={},
                             task_id=task.id,
                             subtask_id=subtask_id)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.monitor_task,task.id, thread_result, stop_event=stop_event)
            concurrent.futures.thread._threads_queues.clear()
        
            future.result()

        if thread_result['result'].get('success', None) is not None:
            return self.get_task_result(task.id, subtask_id)
        else:
            pprint(thread_result)

    def solvent_from_material(self, name: str, fraction: float) -> Solvent:
        """Gets solvent properties from material definition

        Args:
            name (str): material name
            fraction (float): fraction

        Returns:
            Solvent: returned solvent object
        """

        material = self.materials[name]

        return Solvent(name=material.name, fraction=fraction)

    def solute_from_material(self, name: str, concentration: float, units: str | None = None) -> Solute:
        """Gets solute properties from material definition

        Args:
            name (str): material name
            concentration (float): concentration
            units (str, optional): units. Defaults to material default units

        Returns:
            Solute: returned solute object
        """

        material = self.materials[name]

        return Solute(name=material.name,
                    molecular_weight=material.molecular_weight,
                    concentration=concentration,
                    units=units if units is not None else material.concentration_units)
