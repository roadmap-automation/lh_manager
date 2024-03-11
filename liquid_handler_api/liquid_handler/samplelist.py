from dataclasses import asdict, field
from pydantic.v1.dataclasses import dataclass
from enum import Enum
from uuid import uuid4
from typing import Dict, List, Union
from .bedlayout import LHBedLayout
from .lhinterface import LHJob, ResultStatus, DATE_FORMAT, SampleList
from .items import StageName
from .error import MethodError
from .methods import MethodsType, BaseMethod, method_manager, Sleep, Release
from datetime import datetime

# =============== Sample list handling =================

class SampleStatus(str, Enum):
    INACTIVE = 'inactive'
    PENDING = 'pending'
    ACTIVE = 'active'
    PARTIAL = 'partially complete'
    FAILED = 'failed'
    COMPLETED = 'completed'

@dataclass
class MethodList:
    """Class representing a list of methods representing one LH job. Can be nested
        in a single stage"""
    createdDate: str | None = None
    methods: List[MethodsType] = field(default_factory=list)
    run_methods: Dict[str, LHJob] | None = None
    status: SampleStatus = SampleStatus.INACTIVE

    def __post_init__(self):

        for i, method in enumerate(self.methods):
            if isinstance(method, dict):
                self.methods[i] = method_manager.get_method_by_name(method['method_name'])(**method)

    def addMethod(self, method: MethodsType) -> None:
        """Adds new method"""
        self.methods.append(method)

    def estimated_time(self, layout: LHBedLayout) -> float:
        """Generates estimated time of all methods in list. If list has been prepared for run,
            use estimated time only from those methods that have not completed

        Returns:
            float: total estimated time in default time units
        """

        if self.run_methods is None:
            return sum(m.estimated_time(layout) for m in self.methods)
        else:
            return sum(t for job in self.run_methods.values() for t, complete in zip(job.estimated_times, job.get_results()) if (complete != ResultStatus.SUCCESS))

    def update_status(self) -> None:
        """Updates status based on run_methods
        """

        if self.run_methods is not None:
            completion_status = [(complete == ResultStatus.SUCCESS) for job in self.run_methods.values() for complete in job.get_results()]
            if all(completion_status):
                self.status = SampleStatus.COMPLETED

    def prepare_run_methods(self, layout: LHBedLayout, name: str | None = None, description: str | None = None):
        """Prepares the method list for running by populating run_methods and run_methods_complete.
            List can then be used for dry or wet runs
        """

        def make_samplelist(method_list: List[MethodsType]) -> LHJob:
            """Makes an LHJob from a list of methods"""

            createdDate = datetime.now().strftime(DATE_FORMAT)

            d = asdict(SampleList(
                name=name,
                id=None,
                createdBy='System',
                description=description,
                createDate=str(createdDate),
                startDate=str(createdDate),
                endDate=str(createdDate),
                columns=None
            ))
        
            expose_methods = []
            for m in method_list:
                expose_methods += [m2.to_dict()
                                   for m2 in m.render_lh_method(sample_name=name,
                                              sample_description=description,
                                              layout=layout)]

            # Get unique keys across all the methods
            all_columns = set.union(*(set(m.keys()) for m in expose_methods))

            # Ensure that all keys exist in all dictionaries
            for m in expose_methods:
                for column in all_columns:
                    if column not in m:
                        m[column] = None

            d.update(columns=expose_methods)

            print(d)

            return d

        # Generate real-time tasks based on layout
        all_methods: List[BaseMethod] = []
        for m in self.methods:
            all_methods += m.get_methods(layout)


        print(all_methods)

        # only create jobs if there are methods (should always be at least one)
        jobs = []
        if len(all_methods):
            # find task release points, add one to the end if none exist
            release_idxs = [i for i, m in enumerate(all_methods) if isinstance(m, Release)]
            if not len(release_idxs):
                release_idxs += [len(all_methods)]
            
            # create jobs from groups of tasks between release points
            jobs = {}
            start_idx = 0
            for idx in release_idxs:
                job_methods = all_methods[start_idx:idx]
                print(start_idx, idx, job_methods)
                if len(job_methods):
                    new_id = str(uuid4())
                    jobs[new_id] = LHJob(id=new_id,
                                         samplelist=make_samplelist(job_methods),
                                         estimated_times=[m.estimated_time(layout) for m in job_methods])

                # skip the release task
                start_idx = idx + 1
                
        self.run_methods = jobs

    def explode(self, layout: LHBedLayout):
        """Permanently replaces the original methods with "exploded" methods, i.e. rendered methods
            based on the provided layout. Cannot be undone.

        Args:
            layout (LHBedLayout): layout to use to generate exploded methods
        """

        #self.prepare_run_methods(layout)
        new_methods = [im for m in self.methods for im in m.get_methods(layout)]
        self.methods = new_methods

    def execute(self, layout: LHBedLayout) -> List[MethodError | None]:
        """Executes all methods. Used for dry running. Returns list of
            errors, one for each method, or None if no error"""

        errors = []
        for m in self.methods:
            print(f'Executing {m}')
            errors += [m.execute(layout)]

        return errors

    def undo_prepare(self):
        """Undoes the prepare steps"""

        self.run_methods = None
    
    def get_method_completion(self) -> bool:
        """Returns list of method completion status. If prepare_run_methods has not been
            run (i.e. run_methods is None), returns False

        Returns:
            bool: Method completion status, one for each method in methods
        """

        if self.run_methods is not None:
            return all((complete == ResultStatus.SUCCESS) for job in self.run_methods.values() for complete in job.get_results())
        
        return False

@dataclass
class Sample:
    """Class representing a sample to be created by Gilson LH"""
    name: str
    description: str
    id: str | None = None
    channel: int = 0
    stages: Dict[StageName, MethodList] = field(default_factory=lambda: {StageName.PREP: MethodList(), StageName.INJECT: MethodList()})
    NICE_uuid: str | None = None
    NICE_slotID: int | None = None
    current_contents: str = ''

    def __post_init__(self) -> None:

        if self.id is None:
            self.generate_new_id()

        # back compatibility
        if not hasattr(self, 'channel'):
            setattr(self, 'channel', 0)

    def generate_new_id(self) -> None:

        self.id = str(uuid4())

    def get_created_dates(self) -> list[datetime]:
        """Returns list of MethodList.createdDates from the sample"""

        return [datetime.strptime(methodlist.createdDate, DATE_FORMAT) for methodlist in self.stages.values() if methodlist.createdDate is not None]

    def get_earliest_date(self) -> datetime | None:
        """Gets earliest createdDate in the sample"""

        datelist = self.get_created_dates()

        return None if len(datelist) < 1 else min(datelist)

    def get_status(self) -> SampleStatus:

        method_status = [methodlist.status for methodlist in self.stages.values()]

        # all are inactive
        if all(ms == SampleStatus.INACTIVE for ms in method_status):

            return SampleStatus.INACTIVE

        # any are active
        elif any(ms == SampleStatus.ACTIVE for ms in method_status):

            return SampleStatus.ACTIVE

        # any are pending
        elif any(ms == SampleStatus.PENDING for ms in method_status):

            return SampleStatus.PENDING

        # all are completed
        elif all(ms == SampleStatus.COMPLETED for ms in method_status):

            return SampleStatus.COMPLETED

        elif any(ms == SampleStatus.COMPLETED for ms in method_status) & any(ms == SampleStatus.INACTIVE for ms in method_status):

            return SampleStatus.PARTIAL

        else:

            print('Warning: undefined sample status. This should never happen!')
            return None

#example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
Sample.__pydantic_model__.update_forward_refs()  # type: ignore
example_method = Sleep(Time=0.1)
example_sample_list: List[Sample] = []
for i in range(10):
    example_sample = Sample(name=f'testsample{i}', description='test sample description')
    example_sample.stages[StageName.PREP].addMethod(Sleep(Time=0.01*float(i)))
    example_sample.stages[StageName.INJECT].addMethod(Sleep(Time=0.011*float(i)))
    example_sample_list.append(example_sample)

# throw some new statuses in the mix:
example_sample_list[0].stages[StageName.PREP].status = SampleStatus.INACTIVE
example_sample_list[1].stages[StageName.PREP].status = SampleStatus.COMPLETED
example_sample_list[1].stages[StageName.INJECT].status = SampleStatus.COMPLETED
example_sample_list[2].stages[StageName.PREP].status = SampleStatus.COMPLETED
example_sample_list[2].stages[StageName.INJECT].status = SampleStatus.INACTIVE
#example_sample = Sample('12', 'testsample12', 'test sample description')
#example_sample.methods.append(example_method)
#print(methods)

