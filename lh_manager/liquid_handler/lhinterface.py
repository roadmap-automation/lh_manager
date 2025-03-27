import os
import copy
import json
import sqlite3

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Callable, Tuple
from pydantic import BaseModel

from .job import JobBase, ResultStatus, ValidationStatus
from .methods import method_manager
from .lhmethods import BaseLHMethod
from .bedlayout import LHBedLayout
from ..app_config import config

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

#LH_JOB_HISTORY = Path(__file__).parent.parent.parent / 'persistent_state' / 'lh_jobs.sqlite'
LH_JOB_HISTORY = config.log_path / 'lh_jobs.sqlite'

class InterfaceStatus(str, Enum):
    UP = 'up'
    BUSY = 'busy'
    DOWN = 'down'
    ERROR = 'error'

class SampleList(BaseModel):
    """Class representing a sample list in JSON
        serializable format for Gilson Trilution LH Web Service """
    name: str
    id: str | None
    createdBy: str
    description: str
    createDate: str
    startDate: str
    endDate: str
    columns: List[dict] | None

class LHJob(JobBase):
    """Container for a single liquid handler sample list"""

    LH_id: int | None = None
    LH_methods: List[BaseLHMethod] | None = None
    LH_method_data: dict | None = None

    def get_validation_status(self) -> Tuple[ValidationStatus, dict | None]:
        """Returns true if validation exists """

        if not len(self.validation):
            return ValidationStatus.UNVALIDATED, None

        if self.validation['validation']['validationType'] == 'SUCCESS':
            return ValidationStatus.SUCCESS, None
        else:
            return ValidationStatus.FAIL, self.validation

    def get_result_status(self) -> ResultStatus:
        # if no results
        if not len(self.results):
            return ResultStatus.EMPTY

        results = self.get_results()

        # check for any failures in existing results
        if ResultStatus.FAIL in results:
            return ResultStatus.FAIL

        # check for incomplete results (should be one per method in columns)
        if ResultStatus.INCOMPLETE in results:
            return ResultStatus.INCOMPLETE

        # if all checks pass, we were successful
        return ResultStatus.SUCCESS

    def get_number_of_methods(self) -> int:
        if self.LH_method_data['columns'] is None:
            return 0
        else:
            return len(self.LH_method_data['columns'])

    def get_results(self) -> List[ResultStatus]:
        results = [ResultStatus.SUCCESS if ('completed successfully' in notification) else ResultStatus.FAIL
                for result in self.results
                for notification in result['sampleData']['resultNotifications']['notifications'].values()]

        results += [ResultStatus.INCOMPLETE for _ in range(self.get_number_of_methods() - len(self.results))]

        return results

    def generate_method_data(self, layout: LHBedLayout) -> None:
        """Gets the sample list formatted for Gilson LH (populates self.LH_method_data)

        Args:
            listonly (bool, optional): Only return header information. Defaults to False.
        """

        # should be a 1-dimensional list of methods (already exploded)
        sample_name = self.method_data['method_list'][0]['sample_name']
        sample_description = self.method_data['method_list'][0]['sample_description']
        print(self.method_data)
        
        createdDate = datetime.now().strftime(DATE_FORMAT)

        all_methods: List[BaseLHMethod] = [method_manager.get_method_by_name(md['method_name'])(**md['method_data']) for md in self.method_data['method_list']]

        # reconstruct methods
        method_list = [m2 
                    for m in all_methods
                    for m2 in m.render_lh_method(sample_name=sample_name,
                                            sample_description=sample_description,
                                            layout=layout)]

        # Get unique keys across all the methods
        all_columns = set.union(*(set(m.keys()) for m in method_list))

        # Ensure that all keys exist in all dictionaries
        for m in method_list:
            for column in all_columns:
                if column not in m:
                    m[column] = None

        self.LH_method_data = SampleList(
            name=sample_name,
            id=str(self.LH_id),
            createdBy='System',
            description=sample_description,
            createDate=str(createdDate),
            startDate=str(createdDate),
            endDate=str(createdDate),
            columns=method_list).model_dump()

        self.LH_methods = all_methods

    def get_method_data(self, listonly=False) -> dict:
        """Gets the sample list formatted for Gilson LH.

        Returns:
            dict: sample list prepared for Gilson LH
        """

        samplelist = copy.copy(self.LH_method_data)
        samplelist['id'] = str(self.LH_id)
        if listonly:
            samplelist['columns'] = None

        return samplelist
    
    def execute_methods(self, layout: LHBedLayout) -> None:
        """Update layout with job methods

        Args:
            layout (LHBedLayout): layout to update
        """

        for m in self.LH_methods:
            print('Executing: ', m.model_dump())
            result = m.execute(layout)
            print('Result: ', m.model_dump())

class LHJobHistory:
    table_name = 'lh_job_record'
    table_definition = f"""\
        CREATE TABLE IF NOT EXISTS {table_name}(
            uuid TEXT PRIMARY KEY,
            LH_id INTEGER,
            job JSON,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) WITHOUT ROWID;"""
    
    def __init__(self, database_path: str = LH_JOB_HISTORY) -> None:
        self.db_path: str = database_path
        self.db: sqlite3.Connection | None = None

    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self) -> None:
        db_exists = os.path.exists(self.db_path)
        self.db = sqlite3.connect(self.db_path)
        if not db_exists:
            self.db.execute(self.table_definition)

    def close(self) -> None:
        self.db.close()

    def smart_insert(self, job: LHJob) -> None:
        """Inserts or, if job already exists, updates a liquid handler job. Uses id as unique identifier

        Args:
            job (LHJob): liquid handler job to update or insert into the history
        """
        res = self.db.execute(f"""\
            INSERT INTO {self.table_name}(uuid, LH_id, job) VALUES (?, ?, ?)
            ON CONFLICT(uuid) DO UPDATE SET 
              LH_id=excluded.LH_id,
              job=excluded.job;
        """, (job.id, job.LH_id, job.model_dump_json()))
        
        self.db.commit()

    def get_job_by_uuid(self, uuid: str) -> LHJob | None:
        """Queries database and returns job based on internal UUID. There should only
            ever be one entry.

        Args:
            uuid (str): uuid

        Returns:
            LHJob: returned job, None if not found
        """

        res = self.db.execute(f"SELECT job FROM {self.table_name} WHERE uuid='{uuid}'")
        results = res.fetchall()
        return None if not len(results) else LHJob(**json.loads(results[0][0]))

    def get_job_by_LH_id(self, LH_id: str) -> LHJob | None:
        """Queries database and returns sample based on LH_id (should be unique)

        Args:
            LH_id (int): LH_id

        Returns:
            List[Sample]: returned samples, empty if not found
        """
        res = self.db.execute(f"SELECT job FROM {self.table_name} WHERE LH_id='{LH_id}'")
        results = res.fetchall()
        return None if not len(results) else LHJob(**json.loads(results[0][0]))
    
    def get_max_LH_id(self) -> int:
        """Gets maximum LH_id from database"""

        res = self.db.execute(f"SELECT MAX(LH_id) FROM {self.table_name}")
        maxval = res.fetchone()
        return maxval[0]


class LHInterface:
    """Basic interface for the liquid handler. Accepts only one job at a time."""
    def __init__(self) -> None:
        self._active_job: LHJob | None = None
        self.running: bool = True
        self.has_error: bool = False
        self.activation_callbacks: List[Callable] = []
        self.validation_callbacks: List[Callable] = []
        self.results_callbacks: List[Callable] = []

    def update_history(self) -> None:
        """Updates the active job in history
        """

        if self._active_job is not None:
            with LHJobHistory() as history:
                history.smart_insert(self._active_job)

    def get_status(self) -> InterfaceStatus:
        """Gets status of the interface"""

        if not self.running:
            return InterfaceStatus.DOWN

        if self.has_error:
            return InterfaceStatus.ERROR

        if self._active_job is not None:
            return InterfaceStatus.BUSY

        return InterfaceStatus.UP

    def get_active_job(self) -> LHJob | None:
        """Gets LHJob"""

        return self._active_job

    def update_job(self, job: LHJob):
        """Updates the active job. Active job must exist and have
            same id as the updated job"""

        # check that we're updating the right job
        if self._active_job is not None:
            if job.id != self._active_job.id:
                raise RuntimeError(f'Received update for job {job.id} but active job is {self._active_job.id}')
        else:
            raise RuntimeError(f'Received update for job {job.id} but no active job exists')
    
        self._active_job = job
        self.update_history()

    def update_job_result(self, job: LHJob, *args, **kwargs):
        """Handles updates specifically to job results. Triggers callbacks, which
            must have syntax f(job, *args, **kwargs)

        Args:
            job (LHJob): updated job
        """

        self.update_job(job)
        if job.get_result_status() == ResultStatus.SUCCESS:
            self.deactivate()
                    
        for callback in self.results_callbacks:
            callback(job, *args, **kwargs)

    def update_job_validation(self, job: LHJob, *args, **kwargs):
        """Handles updates specifically to job validation. Triggers callbacks, which
            must have syntax f(job, *args, **kwargs)
        Args:
            job (LHJob): updated job
        """

        self.update_job(job)
        for callback in self.validation_callbacks:
            callback(job, *args, **kwargs)

    def activate_job(self, job: LHJob, layout: LHBedLayout, *args, **kwargs):
        """Activates an LHJob"""

        # check that interface is idle
        if self.get_status() != InterfaceStatus.UP:

            raise RuntimeError('Attempted to activate job but LHInterface is not idle')

        with LHJobHistory() as history:
            """get max existing ID"""
            max_LH_id = history.get_max_LH_id()

        # set to zero if no records yet
        if max_LH_id is None:
            max_LH_id = 0
        
        # assign new ID
        job.LH_id = max_LH_id + 1
        job.generate_method_data(layout)
        
        # activate job
        self._active_job = job

        self.update_history()
        
        # run callbacks
        for callback in self.activation_callbacks:
            callback(job, *args, **kwargs)
        
    def deactivate(self):
        """Removes current job and goes idle
        """

        self.update_history()
        self._active_job = None

lh_interface = LHInterface()

if __name__ == '__main__':

    with LHJobHistory() as history:
        print(history.get_max_LH_id())
