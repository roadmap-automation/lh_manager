import os
import json
import sqlite3
import time

from pathlib import Path
from typing import List
from dataclasses import asdict

from .samplelist import Sample

SAMPLE_HISTORY = Path(__file__).parent.parent.parent / 'persistent_state' / 'completed_samples.sqlite'

class History:
    table_name = 'completed_samples'
    table_definition = f'CREATE TABLE {table_name}(uuid TEXT PRIMARY KEY, NICE_uuid TEXT, sample JSON)'

    def __init__(self, database_path: str = SAMPLE_HISTORY) -> None:
        self.db_path = database_path
        self.db = None
        self.open()

    def open(self) -> None:
        db_exists = os.path.exists(self.db_path)
        self.db = sqlite3.connect(self.db_path)
        if not db_exists:
            self.db.execute(self.table_definition)

    def close(self) -> None:
        self.db.close()

    def smart_insert(self, sample: Sample) -> None:
        """Inserts or, if sample already exists, updates a sample. Uses sample ID as unique identifier

        Args:
            sample (Sample): Sample to update or insert into the history
        """

        insert_start_time = time.time()
        res = self.db.execute(f"""\
            INSERT INTO {self.table_name}(uuid, NICE_uuid, sample) VALUES (?, ?, ?)
            ON CONFLICT(uuid) DO UPDATE SET 
              NICE_uuid=excluded.NICE_uuid,
              sample=excluded.sample;
        """, (sample.id, sample.NICE_uuid, json.dumps(asdict(sample))))
        
        self.db.commit()

        print(f'Total insertion time: {time.time() - insert_start_time} seconds')

    def _get_samples(self, field: str, value: str) -> List[Sample]:
        """Basic selection operation using WHERE

        Args:
            field (str): field name for selection
            value (str): value that field should have for selection

        Returns:
            List[Sample]: list of samples found, empty if not found
        """

        res = self.db.execute(f"SELECT sample FROM {self.table_name} WHERE {field}={value}")
        samples = res.fetchall()
        return [Sample(**json.loads(s[0])) for s in samples]


    def get_samples_by_NICE_uuid(self, NICE_uuid: str) -> List[Sample] | None:
        """Queries database and returns sample based on NICE UUID

        Args:
            NICE_uuid (str): NICE uuid

        Returns:
            List[Sample]: returned samples, empty if not found
        """

        return self._get_samples("NICE_uuid", f"'{NICE_uuid}'")

    def get_samples_by_uuid(self, uuid: str) -> Sample | None:
        """Queries database and returns sample based on internal UUID. There should only
            ever be one entry.

        Args:
            uuid (str): uuid

        Returns:
            Sample: returned sample, empty if not found
        """

        samples = self._get_samples("uuid", f"'{uuid}'")
        return None if not len(samples) else Sample(**json.loads(samples[0][0]))
