from typing import List
from dataclasses import field
from pydantic import BaseModel
from .items import Item

class DryRunQueue(BaseModel):
    """Container for dry run objects. Unrelated to queue.Queue"""

    # Ordered list of tuples (uuid, stage name) to dry run
    stages: List[Item] = field(default_factory=list)

    def clear(self) -> None:
        """Removes everything from queue
        """

        self.stages = []
    
    def add_item(self, item: Item) -> None:
        """Add a stage to the dry run queue. If item already exists, do nothing. Note
            that no validation is performed

        Args:
            item (DryRunItem): uuid, stage name of sample stage to add
        """

        if item not in self.stages:
            self.stages.append(item)

    def clear_item(self, item: Item) -> None:
        """Removes an item from the dry run queue. Error if not present

        Args:
            item (DryRunItem): (id, stage_name) to remove
        """

        self.stages.pop(self.stages.index(item))

    def move_item_up(self, item: Item) -> None:
        """Moves a stage item up (lower index) in the queue. Error if item not present

        Args:
            item (DryRunItem): item to move up
        """

        idx = self.stages.index(item)
        self.stages.insert(max(0, idx - 1), self.stages.pop(idx))

    def move_item_down(self, item: Item) -> None:
        """Moves a stage item down (higher index) in the queue. Error if item not present

        Args:
            item (Item): item to move down
        """

        idx = self.stages.index(item)
        self.stages.insert(idx + 1, self.stages.pop(idx))

