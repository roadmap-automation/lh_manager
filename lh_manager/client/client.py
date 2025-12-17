"""Client for LH Manager.

This module provides clients to interact with the LH Manager REST API.
It includes:
    - ManagerClient: A synchronous client using `requests`.
    - AsyncManagerClient: An asynchronous client using `aiohttp`.

This code was produced with the assistance of Gemini, a large language model from Google.
"""

import asyncio
import concurrent.futures
import json
import logging
import time
from pprint import pprint
from threading import Event
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import aiohttp
import requests

from ..liquid_handler.bedlayout import LHBedLayout, Rack, Solute, Solvent, Well, WellLocation, Composition
from ..liquid_handler.methods import BaseMethod
from ..liquid_handler.samplelist import Sample
from ..material_db.db import Material

MANAGER_ADDRESS = 'http://localhost:5001'
logger = logging.getLogger(__name__)

class AsyncManagerClient:
    """Asynchronous client for LH Manager API.

    Attributes:
        address (str): Base URL of the manager (e.g., 'http://localhost:5001').
        samples (dict[str, dict]): Cache of samples (raw dicts).
        layout (LHBedLayout): Cache of the current bed layout.
        materials (dict[str, Material]): Cache of materials.

    Usage notes:
    from aiohttp import web
    from lh_manager.client import AsyncManagerClient

    async def manager_client_ctx(app):
        # 1. Setup: Create the client and attach it to the app
        client = AsyncManagerClient()
        
        # Optional: Pre-load data so the cache is ready immediately
        # await client.initialize() 
        
        app['manager_client'] = client
        
        yield  # This separates startup from cleanup
        
        # 2. Cleanup: Close the session when the server shuts down
        await client.close()

    # --- Example Route ---
    async def handle_get_samples(request):
        # Retrieve the shared client
        client: AsyncManagerClient = request.app['manager_client']
        
        # Use the client (session is reused automatically)
        samples = await client.get_samples()
        return web.json_response(samples)

    # --- App Setup ---
    app = web.Application()
    app.cleanup_ctx.append(manager_client_ctx) # Register the context manager
    app.router.add_get('/my_route/', handle_get_samples)

    if __name__ == '__main__':
        web.run_app(app, port=8080)

    """

    samples: Dict[str, Dict] = {}
    layout: LHBedLayout = LHBedLayout()
    materials: Dict[str, Material] = {}

    def __init__(self, address: str = MANAGER_ADDRESS):
        self.address = address
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        session = await self._get_session()
        url = urljoin(self.address, endpoint)
        async with session.request(method, url, **kwargs) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                text = await response.text()
                raise Exception(f"Failed to decode JSON from {url}. Status: {response.status}. Text: {text}")
            
            if not response.ok:
                logger.error(f"Request to {endpoint} failed: {data}")
            return data
        
    async def close(self):
        """Closes the underlying aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def initialize(self):
        """Initializes the client by loading materials, layout, and samples."""
        await asyncio.gather(
            self.load_materials(),
            self.get_layout(),
            self.get_samples()
        )

    # =========================================================================
    # Material DB Endpoints
    # =========================================================================

    async def load_materials(self) -> Dict[str, Material]:
        """Fetches and caches all materials from the database.

        Returns:
            Dict[str, Material]: Dictionary of materials keyed by name.
        """
        response = await self._request('GET', '/Materials/all/')
        self.materials = {v['name']: Material(**v) for v in response.get('materials', [])}
        return self.materials

    async def update_material(self, material: Material) -> Material:
        """Updates or adds a material in the database.

        Args:
            material (Material): The material object to update.

        Returns:
            Material: The updated material object.
        """
        response = await self._request('POST', '/Materials/update/', json=material.model_dump())
        return Material(**response['material'])

    async def get_material_by_uuid(self, uuid: str) -> Optional[Material]:
        """Gets a material by its UUID."""
        response = await self._request('GET', '/Materials/get_uuid/', params={'uuid': uuid})
        mat_data = response.get('material')
        return Material(**mat_data) if mat_data else None

    async def get_material_by_pubchem(self, cid: int) -> Optional[Material]:
        """Gets a material by its PubChem CID."""
        response = await self._request('GET', '/Materials/get_pubchem_cid/', params={'pubchem_cid': cid})
        mat_data = response.get('material')
        return Material(**mat_data) if mat_data else None

    async def search_material_name(self, query: str) -> List[Material]:
        """Searches for materials by name."""
        response = await self._request('GET', '/Materials/search_name/', params={'query': query})
        return [Material(**m) for m in response.get('materials', [])]

    async def delete_material(self, material: Material) -> str:
        """Deletes a material from the database."""
        response = await self._request('POST', '/Materials/delete/', json=material.model_dump())
        return response.get('deleted')

    async def material_from_sequence(self, sequence: str, type: str = 'aa', name: str = '') -> Optional[Material]:
        """Creates a material from a sequence (AA, DNA, RNA)."""
        data = {'sequence': sequence, 'type': type, 'name': name}
        response = await self._request('POST', '/Materials/MaterialFromSequence/', json=data)
        mat_data = response.get('material')
        return Material(**mat_data) if mat_data else None

    # =========================================================================
    # GUI / Sample Management Endpoints
    # =========================================================================

    async def get_samples(self) -> Dict[str, Dict]:
        """Fetches and caches the list of samples.

        Returns:
            Dict[str, Dict]: Dictionary of samples keyed by sample ID.
        """
        response = await self._request('GET', '/GUI/GetSamples/')
        self.samples = {s['id']: s for s in response.get('samples', {}).get('samples', [])}
        return self.samples

    async def get_sample_status(self) -> Dict[str, Any]:
        """Fetches the status of all samples."""
        return await self._request('GET', '/GUI/GetSampleStatus/')

    async def add_sample(self, sample: Sample) -> Tuple[Sample, LHBedLayout]:
        """Adds a new sample (testing endpoint)."""
        response = await self._request('POST', '/webform/AddSample/', json=sample.model_dump())
        new_sample = Sample(**response['new sample'])
        layout = LHBedLayout(**response['layout'])
        return new_sample, layout

    async def update_sample(self, sample: Sample) -> str:
        """Updates or creates a sample.
        
        Returns:
            str: The ID of the updated/added sample.
        """
        response = await self._request('POST', '/GUI/UpdateSample/', json=sample.model_dump())
        await self.get_samples() # Refresh cache
        return list(response.values())[0]

    async def explode_sample(self, sample_id: str, stage: str):
        """Explodes a sample stage into specific instructions."""
        await self._request('POST', '/GUI/ExplodeSample/', json={'id': sample_id, 'stage': stage})

    async def duplicate_sample(self, sample_id: str, channel: Optional[int] = None) -> str:
        """Duplicates an existing sample.
        
        Returns:
            str: The ID of the new duplicate sample.
        """
        data = {'id': sample_id}
        if channel is not None:
            data['channel'] = channel
        response = await self._request('POST', '/GUI/DuplicateSample/', json=data)
        await self.get_samples()
        return response.get('sample duplicated')

    async def remove_sample(self, sample_id: str) -> str:
        """Removes a sample."""
        response = await self._request('POST', '/GUI/RemoveSample/', json={'id': sample_id})
        await self.get_samples()
        return response.get('sample removed')

    async def archive_sample(self, sample_id: str) -> str:
        """Archives and removes a sample."""
        response = await self._request('POST', '/GUI/ArchiveandRemoveSample/', json={'id': sample_id})
        await self.get_samples()
        return response.get('sample archived and removed')

    async def run_sample(self, sample_id: str, sample_name: str, uuid: Optional[str] = None, slot_id: Any = None, stage: List[str] = ['methods']):
        """Submits a sample run request."""
        data = {'name': sample_name, 'id': sample_id, 'uuid': uuid, 'slotID': slot_id, 'stage': stage}
        return await self._request('POST', '/GUI/RunSample/', json=data)

    async def run_method(self, sample_name: str, method_id: str, uuid: Optional[str] = None, slot_id: Any = None, stage: List[str] = ['methods']):
        """Submits a specific method run request."""
        data = {'name': sample_name, 'uuid': uuid, 'slotID': slot_id, 'stage': stage, 'method_id': method_id}
        return await self._request('POST', '/GUI/RunMethod/', json=data)

    async def resubmit_tasks(self, tasks: List[Dict]):
        """Resubmits a list of tasks."""
        return await self._request('POST', '/GUI/ResubmitTasks/', json={'tasks': tasks})

    async def cancel_tasks(self, tasks: List[Dict]):
        """Cancels a list of tasks."""
        return await self._request('POST', '/GUI/CancelTasks/', json={'tasks': tasks})

    # =========================================================================
    # Queue / Dry Run Endpoints
    # =========================================================================

    async def update_dry_run_queue(self, queue_data: Dict):
        """Updates the dry run queue."""
        return await self._request('POST', '/GUI/UpdateDryRunQueue/', json=queue_data)

    async def dry_run(self) -> List[Any]:
        """Performs a dry run and returns errors."""
        response = await self._request('POST', '/GUI/DryRun/')
        return response.get('dry run errors', [])

    async def update_run_queue(self, queue_data: Dict):
        """Updates the active run queue."""
        return await self._request('POST', '/GUI/UpdateRunQueue/', json=queue_data)

    async def get_run_queue(self) -> Dict:
        """Gets the current run queue."""
        response = await self._request('GET', '/GUI/GetRunQueue/')
        return response.get('run_queue')

    # =========================================================================
    # Layout and Device Endpoints
    # =========================================================================

    async def get_layout(self) -> LHBedLayout:
        """Fetches and caches the bed layout."""
        response = await self._request('GET', '/GUI/GetLayout/')
        self.layout = LHBedLayout.model_validate(response)
        return self.layout

    async def get_components(self) -> Dict[str, List[Tuple[str, str]]]:
        """Gets lists of solvents and solutes in the layout."""
        return await self._request('GET', '/GUI/GetComponents/')

    async def get_wells(self, well_locations: Optional[List[WellLocation]] = None) -> List[Dict]:
        """Gets details of specific wells or all wells if None."""
        json_data = [w.model_dump() for w in well_locations] if well_locations else None
        return await self._request('GET', '/GUI/GetWells', json=json_data)

    async def update_rack(self, rack_id: str, rack_data: Dict) -> Dict:
        """Updates a rack definition."""
        data = {'rack_id': rack_id, 'rack': rack_data}
        return await self._request('POST', '/GUI/UpdateRack/', json=data)

    async def update_well(self, well: Well) -> Well:
        """Updates a well definition."""
        response = await self._request('POST', '/GUI/UpdateWell/', json=well.model_dump())
        return Well(**response)

    async def remove_well_definition(self, rack_id: str, well_number: int):
        """Removes a well definition."""
        await self._request('POST', '/GUI/RemoveWellDefinition/', json={'rack_id': rack_id, 'well_number': well_number})

    async def get_all_devices(self) -> Dict:
        """Gets schema for all devices."""
        return await self._request('GET', '/GUI/GetAllDevices/')

    async def update_device(self, device_name: str, param_name: str, param_value: Any):
        """Updates a parameter of a device."""
        data = {'device_name': device_name, 'param_name': param_name, 'param_value': param_value}
        return await self._request('POST', '/GUI/UpdateDevice/', json=data)

    async def initialize_devices(self):
        """Triggers device initialization."""
        return await self._request('POST', '/GUI/InitializeDevices/')

    async def get_all_methods(self) -> Dict:
        """Gets schema for all methods."""
        return await self._request('GET', '/GUI/GetAllMethods/')

    # =========================================================================
    # LH Interface Endpoints
    # =========================================================================

    async def get_job(self, job_id: str) -> Dict:
        """Gets a job by UUID."""
        return await self._request('GET', f'/LH/GetJob/{job_id}')

    async def get_active_job(self) -> Optional[Dict]:
        """Gets the currently active job."""
        response = await self._request('GET', '/LH/GetActiveJob/')
        return response.get('active_job')

    async def submit_job(self, job_data: Dict):
        """Submits a raw LHJob object."""
        return await self._request('POST', '/LH/SubmitJob/', json=job_data)

    async def check_formulation(self, 
                                target_composition: Composition, 
                                target_volume: float, 
                                exact_match: bool = True) -> Dict[str, Any]:
        """Checks if a target composition can be formulated.

        Args:
            target_composition (Composition): The desired composition.
            target_volume (float): The desired volume.
            exact_match (bool): Whether to require exact match of components.

        Returns:
            Dict[str, Any]: Dictionary containing 'success', 'error', 'volumes', and 'wells'.
        """
        data = {
            'target_composition': target_composition.model_dump(),
            'target_volume': target_volume,
            'exact_match': exact_match
        }
        return await self._request('POST', '/LH/CheckFormulation/', json=data)

    async def get_list_of_sample_lists(self) -> List:
        """Gets list of sample lists."""
        response = await self._request('GET', '/LH/GetListofSampleLists/')
        return response.get('sampleLists', [])

    async def get_sample_list(self, sample_list_id: str) -> Dict:
        """Gets specific sample list by ID."""
        return await self._request('GET', f'/LH/GetSampleList/{sample_list_id}')

    async def put_sample_list_validation(self, sample_list_id: str, validation_data: Dict):
        """Updates validation status for a sample list."""
        return await self._request('POST', f'/LH/PutSampleListValidation/{sample_list_id}', json=validation_data)

    async def put_sample_data(self, sample_data: Dict):
        """Uploads run data results."""
        return await self._request('POST', '/LH/PutSampleData/', json=sample_data)

    async def report_error(self, error_data: Dict):
        """Reports an error to the interface."""
        return await self._request('POST', '/LH/ReportError/', json=error_data)

    async def reset_error_state(self):
        """Resets the error state of the interface."""
        return await self._request('POST', '/LH/ResetErrorState/')

    async def resubmit_active_job(self):
        """Increments LH_ID of active job to rerun it."""
        return await self._request('POST', '/LH/ResubmitActiveJob/')

    async def deactivate_interface(self):
        """Deactivates the LH interface."""
        return await self._request('POST', '/LH/Deactivate/')

    async def get_lh_state(self) -> Dict:
        """Gets full LH interface state."""
        return await self._request('GET', '/LH/GetState/')

    async def pause_resume(self):
        """Toggles pause/resume state."""
        return await self._request('POST', '/LH/PauseResume/')

    # =========================================================================
    # Waste Manager Endpoints
    # =========================================================================

    async def get_waste_layout(self) -> Dict:
        """Gets waste layout."""
        return await self._request('GET', '/Waste/GUI/GetLayout')

    async def add_waste(self, volume: float, composition: Any):
        """Adds waste to the manager."""
        data = {'volume': volume, 'composition': composition}
        return await self._request('POST', '/Waste/AddWaste', json=data)

    async def empty_waste(self):
        """Empties the waste container."""
        return await self._request('POST', '/Waste/EmptyWaste')

    async def get_waste_wells(self, well_locations: Optional[List[WellLocation]] = None) -> List[Dict]:
        """Gets waste wells."""
        json_data = [w.model_dump() for w in well_locations] if well_locations else None
        return await self._request('GET', '/Waste/GUI/GetWells', json=json_data)

    async def update_waste_well(self, well: Well) -> Well:
        """Updates a waste well."""
        response = await self._request('POST', '/Waste/GUI/UpdateWell', json=well.model_dump())
        return Well(**response)

    async def remove_waste_well_definition(self, rack_id: str, well_number: int):
        """Removes a waste well definition."""
        await self._request('POST', '/Waste/GUI/RemoveWellDefinition', json={'rack_id': rack_id, 'well_number': well_number})

    async def get_waste_timestamp_table(self) -> List:
        """Gets waste history timestamps."""
        response = await self._request('GET', '/Waste/GUI/GetTimestampTable')
        return response.get('timestamp_table', [])

    async def update_waste_rack(self, rack_id: str, rack_data: Dict) -> Dict:
        """Updates a waste rack."""
        data = {'rack_id': rack_id, 'rack': rack_data}
        return await self._request('POST', '/Waste/GUI/UpdateRack', json=data)

    async def generate_waste_report(self, bottle_id: str) -> str:
        """Generates a text report for a waste bottle."""
        response = await self._request('POST', '/Waste/GUI/GenerateWasteReport', json={'bottle_id': bottle_id})
        return response.get('report', '')

    # =========================================================================
    # Autocontrol & Logic Helper Methods
    # =========================================================================

    async def get_autocontrol_status(self) -> Dict:
        """Gets Autocontrol status."""
        return await self._request('GET', '/autocontrol/GetStatus')

    async def get_task_status(self, task_id: str) -> Dict:
        """Gets the status of a specific task."""
        try:
            return await self._request('GET', '/autocontrol/GetTaskStatus', json={'task_id': task_id})
        except Exception as e:
            return {'error': str(e)}

    async def get_task_result(self, task_id: str, subtask_id: str) -> Dict:
        """Gets the result of a subtask."""
        data = {'task_id': task_id, 'subtask_id': subtask_id}
        return await self._request('GET', '/autocontrol/GetTaskResult', json=data)

    async def get_task_complete(self, task_id: str) -> Dict:
        """Checks if a task is complete (moved to history)."""
        response = await self.get_task_status(task_id)
        if response.get('queue', '') == 'history':
            return {'success': 'complete'}
        return {}

    async def monitor_task(self, task_id: str, poll_interval: float = 5.0) -> Dict:
        """Polls a task until it is complete.
        
        Args:
            task_id (str): The ID of the task to monitor.
            poll_interval (float): Seconds between checks.

        Returns:
            Dict: The completion status.
        """
        while True:
            status = await self.get_task_complete(task_id)
            if status.get('success') == 'complete':
                return status
            if status.get('error'):
                return status
            await asyncio.sleep(poll_interval)

    async def wait_for_result(self, sample: Sample, measure_method_id: str, poll_interval: float = 5.0) -> Dict:
        """Waits for the result of a method in a sample's method list.

        Args:
            sample (Sample): The sample containing the method.
            measure_method_id (str): The ID of the method to wait for.
            poll_interval (float): Polling interval in seconds.

        Returns:
            Dict: The result of the measurement task.
        """
        # Find the method
        methods_stage = sample.stages.get('methods')
        if not methods_stage:
            logger.warning(f'Sample {sample.id} has no methods stage.')
            return {}
            
        measure_method: Optional[BaseMethod] = next((m for m in methods_stage.active if m.id == measure_method_id), None)
        if measure_method is None:
            logger.warning(f'No active tasks found with sample {sample.id} and method {measure_method_id}')
            return {}

        # Assuming the measurement task is the last one in the method
        if not measure_method.tasks:
            logger.warning(f'Method {measure_method_id} has no tasks.')
            return {}
            
        task = measure_method.tasks[-1]
        # Assuming the subtask of interest is the last one
        if not task.task.get('tasks'):
             logger.warning(f'Task {task.id} has no subtasks.')
             return {}
             
        subtask_id = task.task['tasks'][-1].get('id')

        logger.info(f'Waiting for task {task.id}, subtask {subtask_id}')

        # Wait for task completion
        monitor_result = await self.monitor_task(task.id, poll_interval)

        if monitor_result.get('success'):
            return await self.get_task_result(task.id, subtask_id)
        else:
            logger.error(f"Task monitoring failed: {monitor_result}")
            return monitor_result

    # =========================================================================
    # Helpers
    # =========================================================================

    @property
    def sample_ids(self) -> List[str]:
        return list(self.samples.keys())

    def rehydrate_sample(self, sample_id: str) -> Sample:
        """Converts cached dict sample to Sample object."""
        return Sample.model_validate(self.samples[sample_id])

    def solvent_from_material(self, name: str, fraction: float) -> Solvent:
        """Creates a Solvent object from cached materials."""
        material = self.materials[name]
        return Solvent(name=material.name, fraction=fraction)

    def solute_from_material(self, name: str, concentration: float, units: Optional[str] = None) -> Solute:
        """Creates a Solute object from cached materials."""
        material = self.materials[name]
        return Solute(name=material.name,
                      molecular_weight=material.molecular_weight,
                      concentration=concentration,
                      units=units if units is not None else material.concentration_units)

class ManagerClient:
    """Synchronous Client for LH Manager.
    
    This client allows interaction with the LH Manager via standard blocking calls.
    It replicates the functionality of AsyncManagerClient but uses `requests`.
    """
    
    samples: Dict[str, Dict] = {}
    layout: LHBedLayout = LHBedLayout()
    materials: Dict[str, Material] = {}

    def __init__(self, address: str = MANAGER_ADDRESS):
        self.address = address

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = urljoin(self.address, endpoint)
        response = requests.request(method, url, **kwargs)
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise Exception(f"Failed to decode JSON from {url}. Status: {response.status_code}. Text: {response.text}")
        
        if not response.ok:
            logger.error(f"Request to {endpoint} failed: {data}")
        return data

    def initialize(self):
        """Initializes the client by loading materials, layout, and samples."""
        self.load_materials()
        self.get_layout()
        self.get_samples()

    # =========================================================================
    # Material DB Endpoints
    # =========================================================================

    def load_materials(self) -> Dict[str, Material]:
        """Returns and caches dictionary of materials.

        Returns:
            dict[str, Material]: dictionary of materials with material name as key
        """
        response = self._request('GET', '/Materials/all/')
        self.materials = {v['name']: Material(**v) for v in response.get('materials', [])}
        return self.materials

    def update_material(self, material: Material) -> Material:
        """Updates or adds a material in the database."""
        response = self._request('POST', '/Materials/update/', json=material.model_dump())
        return Material(**response['material'])

    def get_material_by_uuid(self, uuid: str) -> Optional[Material]:
        """Gets a material by its UUID."""
        response = self._request('GET', '/Materials/get_uuid/', params={'uuid': uuid})
        mat_data = response.get('material')
        return Material(**mat_data) if mat_data else None

    def get_material_by_pubchem(self, cid: int) -> Optional[Material]:
        """Gets a material by its PubChem CID."""
        response = self._request('GET', '/Materials/get_pubchem_cid/', params={'pubchem_cid': cid})
        mat_data = response.get('material')
        return Material(**mat_data) if mat_data else None

    def search_material_name(self, query: str) -> List[Material]:
        """Searches for materials by name."""
        response = self._request('GET', '/Materials/search_name/', params={'query': query})
        return [Material(**m) for m in response.get('materials', [])]

    def delete_material(self, material: Material) -> str:
        """Deletes a material from the database."""
        response = self._request('POST', '/Materials/delete/', json=material.model_dump())
        return response.get('deleted')

    def material_from_sequence(self, sequence: str, type: str = 'aa', name: str = '') -> Optional[Material]:
        """Creates a material from a sequence."""
        data = {'sequence': sequence, 'type': type, 'name': name}
        response = self._request('POST', '/Materials/MaterialFromSequence/', json=data)
        mat_data = response.get('material')
        return Material(**mat_data) if mat_data else None

    # =========================================================================
    # GUI / Sample Management Endpoints
    # =========================================================================

    def get_samples(self) -> Dict[str, Dict]:
        """Returns and caches dictionary of samples.

        Returns:
            dict[str, dict]: dictionary of samples with sample id as key
        """
        response = self._request('GET', '/GUI/GetSamples/')
        self.samples = {s['id']: s for s in response.get('samples', {}).get('samples', [])}
        return self.samples

    def get_sample_status(self) -> Dict[str, Any]:
        """Fetches the status of all samples."""
        return self._request('GET', '/GUI/GetSampleStatus/')

    def get_layout(self) -> LHBedLayout:
        """Returns and caches bed layout.

        Returns:
            LHBedLayout: bed layout
        """
        response = self._request('GET', '/GUI/GetLayout/')
        self.layout = LHBedLayout.model_validate(response)
        return self.layout

    @property
    def sample_ids(self) -> List[str]:
        return list(self.samples.keys())

    def new_sample(self, sample: Sample) -> Sample:
        """Adds a new sample if it doesn't exist (Legacy helper)."""
        if sample.id not in self.samples:
            _, sample = self.update_sample(sample)
        return sample

    def add_sample(self, sample: Sample) -> Tuple[Sample, LHBedLayout]:
        """Adds a new sample (Testing endpoint)."""
        response = self._request('POST', '/webform/AddSample/', json=sample.model_dump())
        new_sample = Sample(**response['new sample'])
        layout = LHBedLayout(**response['layout'])
        return new_sample, layout

    def update_sample(self, sample: Sample) -> Tuple[str, Sample]:
        """Updates or creates a sample.
        
        Returns:
            Tuple[str, Sample]: Tuple of (ID/message, Updated Sample object).
        """
        response = self._request('POST', '/GUI/UpdateSample/', json=sample.model_dump())
        self.get_samples() # Refresh cache
        # Original logic returned list(response.values())[0] and rehydrated sample
        return list(response.values())[0], self.rehydrate_sample(sample.id)

    def explode_sample(self, sample_id: str, stage: str):
        """Explodes a sample stage."""
        self._request('POST', '/GUI/ExplodeSample/', json={'id': sample_id, 'stage': stage})

    def duplicate_sample(self, sample_id: str, channel: Optional[int] = None) -> str:
        """Duplicates an existing sample."""
        data = {'id': sample_id}
        if channel is not None:
            data['channel'] = channel
        response = self._request('POST', '/GUI/DuplicateSample/', json=data)
        self.get_samples()
        return response.get('sample duplicated')

    def remove_sample(self, sample_id: str) -> str:
        """Removes a sample."""
        response = self._request('POST', '/GUI/RemoveSample/', json={'id': sample_id})
        self.get_samples()
        return response.get('sample removed')

    def archive_sample(self, sample: Sample) -> Dict:
        """Archives and removes a sample."""
        response = self._request('POST', '/GUI/ArchiveandRemoveSample/', json={'id': sample.id})
        self.get_samples()
        return response

    def run_sample(self, sample_id: str, sample_name: Optional[str] = None) -> Tuple[Any, Sample]:
        """Submits a sample run request.

        Args:
            sample_id (str): ID of the sample to run.
            sample_name (Optional[str]): Name of sample. If None, looked up from cache.
        
        Returns:
            Tuple[Any, Sample]: Response and rehydrated sample.
        """
        if sample_name is None:
            sample_data = self.samples.get(sample_id)
            if sample_data:
                sample_name = sample_data.get('name')
                uuid = sample_data.get('uuid')
            else:
                raise ValueError(f"Sample {sample_id} not found in cache. Update samples first.")
        else:
            uuid = None # Or passed in if we change signature further

        data = {'name': sample_name, 'id': sample_id, 'uuid': uuid, 'slotID': None, 'stage': ['methods']}
        response = self._request('POST', '/GUI/RunSample/', json=data)
        self.get_samples()
        return response, self.rehydrate_sample(sample_id)

    def run_method(self, sample_name: str, method_id: str, uuid: Optional[str] = None, slot_id: Any = None, stage: List[str] = ['methods']):
        """Submits a specific method run request."""
        data = {'name': sample_name, 'uuid': uuid, 'slotID': slot_id, 'stage': stage, 'method_id': method_id}
        return self._request('POST', '/GUI/RunMethod/', json=data)

    def resubmit_tasks(self, tasks: List[Dict]):
        """Resubmits a list of tasks."""
        return self._request('POST', '/GUI/ResubmitTasks/', json={'tasks': tasks})

    def cancel_tasks(self, tasks: List[Dict]):
        """Cancels a list of tasks."""
        return self._request('POST', '/GUI/CancelTasks/', json={'tasks': tasks})

    # =========================================================================
    # Queue / Dry Run Endpoints
    # =========================================================================

    def update_dry_run_queue(self, queue_data: Dict):
        """Updates the dry run queue."""
        return self._request('POST', '/GUI/UpdateDryRunQueue/', json=queue_data)

    def dry_run(self) -> List[Any]:
        """Performs a dry run and returns errors."""
        response = self._request('POST', '/GUI/DryRun/')
        return response.get('dry run errors', [])

    def update_run_queue(self, queue_data: Dict):
        """Updates the active run queue."""
        return self._request('POST', '/GUI/UpdateRunQueue/', json=queue_data)

    def get_run_queue(self) -> Dict:
        """Gets the current run queue."""
        response = self._request('GET', '/GUI/GetRunQueue/')
        return response.get('run_queue')

    # =========================================================================
    # Layout and Device Endpoints
    # =========================================================================

    def get_components(self) -> Dict[str, List[Tuple[str, str]]]:
        """Gets lists of solvents and solutes in the layout."""
        return self._request('GET', '/GUI/GetComponents/')

    def get_wells(self, well_locations: Optional[List[WellLocation]] = None) -> List[Dict]:
        """Gets details of specific wells or all wells if None."""
        json_data = [w.model_dump() for w in well_locations] if well_locations else None
        return self._request('GET', '/GUI/GetWells', json=json_data)

    def update_rack(self, rack_id: str, rack_data: Dict) -> Dict:
        """Updates a rack definition."""
        data = {'rack_id': rack_id, 'rack': rack_data}
        return self._request('POST', '/GUI/UpdateRack/', json=data)

    def update_well(self, well: Well) -> Well:
        """Updates a well definition."""
        response = self._request('POST', '/GUI/UpdateWell/', json=well.model_dump())
        return Well(**response)

    def remove_well_definition(self, rack_id: str, well_number: int):
        """Removes a well definition."""
        self._request('POST', '/GUI/RemoveWellDefinition/', json={'rack_id': rack_id, 'well_number': well_number})

    def get_all_devices(self) -> Dict:
        """Gets schema for all devices."""
        return self._request('GET', '/GUI/GetAllDevices/')

    def update_device(self, device_name: str, param_name: str, param_value: Any):
        """Updates a parameter of a device."""
        data = {'device_name': device_name, 'param_name': param_name, 'param_value': param_value}
        return self._request('POST', '/GUI/UpdateDevice/', json=data)

    def initialize_devices(self):
        """Triggers device initialization."""
        return self._request('POST', '/GUI/InitializeDevices/')

    def get_all_methods(self) -> Dict:
        """Gets schema for all methods."""
        return self._request('GET', '/GUI/GetAllMethods/')

    # =========================================================================
    # LH Interface Endpoints
    # =========================================================================

    def get_job(self, job_id: str) -> Dict:
        """Gets a job by UUID."""
        return self._request('GET', f'/LH/GetJob/{job_id}')

    def get_active_job(self) -> Optional[Dict]:
        """Gets the currently active job."""
        response = self._request('GET', '/LH/GetActiveJob/')
        return response.get('active_job')

    def submit_job(self, job_data: Dict):
        """Submits a raw LHJob object."""
        return self._request('POST', '/LH/SubmitJob/', json=job_data)

    def check_formulation(self, 
                          target_composition: Composition, 
                          target_volume: float, 
                          exact_match: bool = True) -> Dict[str, Any]:
        """Checks if a target composition can be formulated.

        Args:
            target_composition (Composition): The desired composition.
            target_volume (float): The desired volume.
            exact_match (bool): Whether to require exact match of components.

        Returns:
            Dict[str, Any]: Dictionary containing 'success', 'error', 'volumes', and 'wells'.
        """
        data = {
            'target_composition': target_composition.model_dump(),
            'target_volume': target_volume,
            'exact_match': exact_match
        }
        return self._request('POST', '/LH/CheckFormulation/', json=data)

    def get_list_of_sample_lists(self) -> List:
        """Gets list of sample lists."""
        response = self._request('GET', '/LH/GetListofSampleLists/')
        return response.get('sampleLists', [])

    def get_sample_list(self, sample_list_id: str) -> Dict:
        """Gets specific sample list by ID."""
        return self._request('GET', f'/LH/GetSampleList/{sample_list_id}')

    def put_sample_list_validation(self, sample_list_id: str, validation_data: Dict):
        """Updates validation status for a sample list."""
        return self._request('POST', f'/LH/PutSampleListValidation/{sample_list_id}', json=validation_data)

    def put_sample_data(self, sample_data: Dict):
        """Uploads run data results."""
        return self._request('POST', '/LH/PutSampleData/', json=sample_data)

    def report_error(self, error_data: Dict):
        """Reports an error to the interface."""
        return self._request('POST', '/LH/ReportError/', json=error_data)

    def reset_error_state(self):
        """Resets the error state of the interface."""
        return self._request('POST', '/LH/ResetErrorState/')

    def resubmit_active_job(self):
        """Increments LH_ID of active job to rerun it."""
        return self._request('POST', '/LH/ResubmitActiveJob/')

    def deactivate_interface(self):
        """Deactivates the LH interface."""
        return self._request('POST', '/LH/Deactivate/')

    def get_lh_state(self) -> Dict:
        """Gets full LH interface state."""
        return self._request('GET', '/LH/GetState/')

    def pause_resume(self):
        """Toggles pause/resume state."""
        return self._request('POST', '/LH/PauseResume/')

    # =========================================================================
    # Waste Manager Endpoints
    # =========================================================================

    def get_waste_layout(self) -> Dict:
        """Gets waste layout."""
        return self._request('GET', '/Waste/GUI/GetLayout')

    def add_waste(self, volume: float, composition: Any):
        """Adds waste to the manager."""
        data = {'volume': volume, 'composition': composition}
        return self._request('POST', '/Waste/AddWaste', json=data)

    def empty_waste(self):
        """Empties the waste container."""
        return self._request('POST', '/Waste/EmptyWaste')

    def get_waste_wells(self, well_locations: Optional[List[WellLocation]] = None) -> List[Dict]:
        """Gets waste wells."""
        json_data = [w.model_dump() for w in well_locations] if well_locations else None
        return self._request('GET', '/Waste/GUI/GetWells', json=json_data)

    def update_waste_well(self, well: Well) -> Well:
        """Updates a waste well."""
        response = self._request('POST', '/Waste/GUI/UpdateWell', json=well.model_dump())
        return Well(**response)

    def remove_waste_well_definition(self, rack_id: str, well_number: int):
        """Removes a waste well definition."""
        self._request('POST', '/Waste/GUI/RemoveWellDefinition', json={'rack_id': rack_id, 'well_number': well_number})

    def get_waste_timestamp_table(self) -> List:
        """Gets waste history timestamps."""
        response = self._request('GET', '/Waste/GUI/GetTimestampTable')
        return response.get('timestamp_table', [])

    def update_waste_rack(self, rack_id: str, rack_data: Dict) -> Dict:
        """Updates a waste rack."""
        data = {'rack_id': rack_id, 'rack': rack_data}
        return self._request('POST', '/Waste/GUI/UpdateRack', json=data)

    def generate_waste_report(self, bottle_id: str) -> str:
        """Generates a text report for a waste bottle."""
        response = self._request('POST', '/Waste/GUI/GenerateWasteReport', json={'bottle_id': bottle_id})
        return response.get('report', '')

    # =========================================================================
    # Autocontrol & Logic Helper Methods
    # =========================================================================

    def get_autocontrol_status(self) -> Dict:
        """Gets Autocontrol status."""
        return self._request('GET', '/autocontrol/GetStatus')

    def get_task_status(self, task_id: str) -> Dict:
        """Gets the status of a specific task."""
        try:
            return self._request('GET', '/autocontrol/GetTaskStatus', json={'task_id': task_id})
        except Exception as e:
            return {'error': str(e)}

    def get_task_result(self, task_id: str, subtask_id: str) -> Dict:
        """Gets the result of a subtask."""
        data = {'task_id': task_id, 'subtask_id': subtask_id}
        return self._request('GET', '/autocontrol/GetTaskResult', json=data)

    def get_task_complete(self, task_id: str) -> Dict:
        """Checks if a task is complete (moved to history)."""
        response = self.get_task_status(task_id)
        if response.get('queue', '') == 'history':
            return {'success': 'complete'}
        return {}

    def monitor_task(self, task_id: str, thread_result: Dict, poll_interval: float = 5, stop_event: Event = Event()) -> str:
        """Monitors a task (helper for threading/wait_for_result)."""
        current_status = {}
        while (current_status.get('success', 'incomplete') == 'incomplete') & (not stop_event.is_set()):
            time.sleep(poll_interval)
            current_status = self.get_task_complete(task_id=task_id)
        
        thread_result['result'] = current_status

    def wait_for_result(self, sample: Sample, measure_method_id: str, stop_event: Event = Event()) -> Dict:
        """Waits for the result of a method.

        Args:
            sample (Sample): sample object containing the method
            measure_method_id (str): id of method to wait for
            stop_event (Event, optional): stop thread-safe event. Defaults to Event().

        Returns:
            dict: measurement result
        """
        measure_method: Optional[BaseMethod] = next((m for m in sample.stages['methods'].active if m.id == measure_method_id), None)
        if measure_method is None:
            logger.warning(f'Warning: no active tasks found with sample {sample.id} and method {measure_method_id}')
            return {}
        
        task = measure_method.tasks[-1]
        if not task.task.get('tasks'):
            logger.warning(f'Task {task.id} has no subtasks')
            return {}
            
        subtask_id = task.task['tasks'][-1].get('id', None)

        logger.info(f'\tSubtask id: {subtask_id}')
        thread_result = dict(result={},
                             task_id=task.id,
                             subtask_id=subtask_id)
        
        # Using executor to match original implementation style, though direct loop is also fine
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.monitor_task, task.id, thread_result, stop_event=stop_event)
            # Ensure we don't carry over old queues if that was a concern in original code
            if hasattr(concurrent.futures.thread, '_threads_queues'):
                 concurrent.futures.thread._threads_queues.clear()
            future.result()

        if thread_result['result'].get('success', None) is not None:
            return self.get_task_result(task.id, subtask_id)
        else:
            pprint(thread_result)
            return thread_result

    # =========================================================================
    # Helpers
    # =========================================================================

    def rehydrate_sample(self, sample_id: str) -> Sample:
        """Converts cached dict sample to Sample object."""
        return Sample.model_validate(self.samples[sample_id])

    def solvent_from_material(self, name: str, fraction: float) -> Solvent:
        """Gets solvent properties from material definition.

        Args:
            name (str): material name
            fraction (float): fraction

        Returns:
            Solvent: returned solvent object
        """
        material = self.materials[name]
        return Solvent(name=material.name, fraction=fraction)

    def solute_from_material(self, name: str, concentration: float, units: str | None = None) -> Solute:
        """Gets solute properties from material definition.

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