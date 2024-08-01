import os
import json
import sqlite3
import time

from pathlib import Path
from typing import List, Optional
from dataclasses import asdict, dataclass, fields

@dataclass
class Material:
    name: str
    pubchem_cid: Optional[int] = None
    iupac_name: Optional[str] = None
    molecular_weight: Optional[float] = None
    metadata: Optional[dict] = None
    type: Optional[str] = None
    density: Optional[float] = None
    concentration_units: Optional[str] = None

MATERIAL_DB = Path(__file__).parent.parent.parent / 'persistent_state' / 'materials.sqlite'

class MaterialDB:
    table_name = 'materials'
    table_definition = f"""\
        CREATE TABLE IF NOT EXISTS {table_name}(
            name TEXT PRIMARY KEY,
            pubchem_cid INTEGER,
            iupac_name TEXT,
            molecular_weight REAL,
            metadata JSON,
            type TEXT,
            density REAL,
            concentration_units TEXT
        );"""
    columns = [f.name for f in fields(Material)]

    def __init__(self, database_path: str = MATERIAL_DB) -> None:
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def smart_insert(self, material: Material) -> None:
        """Inserts or, if material already exists, updates a material. Uses name as unique identifier

        Args:
            material (Material): material to update or insert into the db
        """

        res = self.db.execute(f"""\
            INSERT INTO {self.table_name}({','.join(self.columns)}) VALUES ({','.join(['?']*len(self.columns))})
            ON CONFLICT(name) DO UPDATE SET 
                {','.join([f'{c}=excluded.{c}' for c in self.columns if c != 'name'])};
        """, [getattr(material, c) for c in self.columns])
        self.db.commit()

    def populate_from_pubchem(self, name: str) -> Material:
        import pubchempy as pcp
        material = self.get_material_by_name(name)
        pubchem_cid = material.pubchem_cid
        compound = pcp.Compound.from_cid(pubchem_cid)
        material.molecular_weight = compound.molecular_weight
        material.iupac_name = compound.iupac_name
        self.smart_insert(material)
        return material
    
    def query_pubchem(self, pubchem_cid: int) -> Material:
        import pubchempy as pcp
        compound = pcp.Compound.from_cid(pubchem_cid)
        material = Material(
            name=compound.synonyms[0],
            pubchem_cid=compound.cid,
            iupac_name=compound.iupac_name,
            molecular_weight=compound.molecular_weight,
            metadata={},
            type='compound',
            density=None,
            concentration_units=None
        )
        return material


    def search_name(self, name: str, case_sensitive: bool = False) -> List[Material]:
        res = self.db.execute(f"SELECT * FROM {self.table_name} WHERE name {'LIKE' if case_sensitive else 'ILIKE'} ?", (f'%{name}%',))
        materials = res.fetchall()
        return [Material(*m) for m in materials]
    
    def get_material_by_uuid(self, uuid: str) -> Material | None:
        res = self.db.execute(f"SELECT * FROM {self.table_name} WHERE uuid=?", (uuid,))
        material = res.fetchone()
        return None if not material else Material(*material)
    
    def get_material_by_name(self, name: str) -> Material | None:
        res = self.db.execute(f"SELECT * FROM {self.table_name} WHERE name=?", (name,))
        material = res.fetchone()
        return None if not material else Material(*material)
    
    def get_material_by_pubchem_cid(self, pubchem_cid: int) -> Material | None:
        res = self.db.execute(f"SELECT * FROM {self.table_name} WHERE pubchem_cid=?", (pubchem_cid,))
        material = res.fetchone()
        return None if not material else Material(*material)
    
    def get_all_materials(self) -> List[Material]:
        res = self.db.execute(f"SELECT * FROM {self.table_name}")
        materials = res.fetchall()
        return [Material(*m) for m in materials]
    
    def delete_material(self, material: Material) -> None:
        self.db.execute(f"DELETE FROM {self.table_name} WHERE name=?", (material.name,))
        self.db.commit()

