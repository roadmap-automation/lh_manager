from enum import Enum
from .items import Item

from pydantic.v1.dataclasses import dataclass

from dataclasses import field
from typing import List, Tuple

class ValidationStatus(str, Enum):
    UNVALIDATED = 'unvalidated',
    SUCCESS = 'success',
    FAIL = 'failed'


class ResultStatus(str, Enum):
    EMPTY = 'empty',
    INCOMPLETE = 'incomplete',
    SUCCESS = 'success',
    FAIL = 'failed'

@dataclass
class JobBase:
    """Container for a single job list"""
    id: str | None = None
    method_data: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    results: list = field(default_factory=list)
    parent: Item | None = None

    def __post_init__(self):

        if isinstance(self.parent, dict):
            self.parent = Item(**self.parent)

    def get_validation_status(self) -> Tuple[ValidationStatus, dict | None]:
        """Returns true if validation exists """

        raise NotImplementedError
    
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

    def get_results(self) -> List[ResultStatus]:
        
        raise NotImplementedError

    def get_method_data(self) -> dict:
        """Gets the method data, possibly with formatting

        Returns:
            dict: formatted method data
        """

        raise NotImplementedError
