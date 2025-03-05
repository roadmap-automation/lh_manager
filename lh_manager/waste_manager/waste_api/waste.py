"""Waste manager initialization"""
import json
import os
import sqlite3

from uuid import uuid4

from ..liquid_handler.bedlayout import LHBedLayout, Rack, Well, Composition
from ..app_config import config
from .wastedata import WasteItem

WASTE_LOG = config.log_path / 'waste.json'
WASTE_HISTORY = config.log_path / 'waste.sqlite'
WASTE_RACK = 'waste'

class WasteLayout(LHBedLayout):
    """Specialized layout class for waste handling. Has a single carboy well
    """

    _database_path: str = WASTE_HISTORY

    def save_waste(self):
        with open(WASTE_LOG, 'w') as f:
            f.write(self.model_dump_json(indent=2))

    def empty_waste(self):
        new_carboy = Well(rack_id=WASTE_RACK,
                    well_number=1,
                    composition=Composition(),
                    volume=0.0,
                    id=str(uuid4()))
        
        self.update_well(new_carboy)
        self.save_waste()

    @property
    def carboy(self):
        return self.racks[WASTE_RACK].wells[0]

    def add_waste(self, new_waste: WasteItem):
        self.carboy.mix_with(new_waste.volume, new_waste.composition)
        self.save_waste()
        self.update_history(new_waste=new_waste)

    def update_history(self, new_waste: WasteItem):
        with WasteHistory(self._database_path) as waste_history:
            waste_history.insert(bottle_id=self.carboy.id,
                                 new_waste=new_waste)

def load_waste():

    layout = None

    if os.path.exists(WASTE_LOG):
        layout = WasteLayout(**json.load(open(WASTE_LOG, 'r')))
    else:

        print('Creating new waste layout...')

        # Single 10L waste bottle for now
        waste_rack = Rack(columns=1,
                        rows=1,
                        max_volume=10e3,
                        wells=[])

        layout = WasteLayout(racks={WASTE_RACK: waste_rack})
        layout.empty_waste()

    return layout

 ## ======= Initialize bed layout =========
waste_layout = load_waste()

class WasteHistory:
    table_name = 'waste_history'
    table_definition = f"""\
        CREATE TABLE IF NOT EXISTS {table_name}(
            bottle_id TEXT,
            waste JSON,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
    
    def __init__(self, database_path: str = WASTE_HISTORY) -> None:
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

    def insert(self, bottle_id: str, new_waste: WasteItem) -> None:
        """Inserts a waste entry.

        Args:
            bottle_id (str): id of waste bottle
            new_waste (WasteItem): waste item to insert
        """
        res = self.db.execute(f"""\
            INSERT INTO {self.table_name}(bottle_id, waste) VALUES (?, ?);
        """, (bottle_id, new_waste.model_dump_json()))
        
        self.db.commit()

    def get_waste_by_bottle_id(self, bottle_id: str) -> list[WasteItem]:
        """Queries database and returns all waste entires based on bottle ID.

        Args:
            uuid (str): uuid

        Returns:
            List[WasteItem]: list of returned jobs, empty if not found
        """

        res = self.db.execute(f"SELECT waste FROM {self.table_name} WHERE bottle_id='{bottle_id}'")
        results = res.fetchall()
        return [WasteItem(**json.loads(res[0])) for res in results]