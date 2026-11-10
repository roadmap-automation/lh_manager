import os
import sqlite3

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, fields

@dataclass
class Material:
    name: str
    pubchem_cid: Optional[int] = None
    full_name: Optional[str] = None
    iupac_name: Optional[str] = None
    molecular_weight: Optional[float] = None
    metadata: Optional[dict] = None
    type: Optional[str] = None
    density: Optional[float] = None
    concentration_units: Optional[str] = None
    hidden: int = 0
    formula: Optional[str] = None
    sld: Optional[float] = None

MATERIAL_DB = Path(__file__).parent.parent.parent / 'persistent_state' / 'materials.sqlite'

class MaterialDB:
    table_name = 'materials'
    table_definition = f"""\
        CREATE TABLE IF NOT EXISTS {table_name}(
            name TEXT PRIMARY KEY,
            pubchem_cid INTEGER,
            full_name TEXT,
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
        self._migrate()

    def _migrate(self) -> None:
        migrations = [
            "ALTER TABLE materials ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE materials ADD COLUMN formula TEXT",
            "ALTER TABLE materials ADD COLUMN sld REAL",
        ]
        for sql in migrations:
            try:
                self.db.execute(sql)
            except sqlite3.OperationalError:
                pass
        self.db.commit()

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
        material.formula = compound.molecular_formula
        self.smart_insert(material)
        return material
    
    def query_pubchem(self, pubchem_cid: int) -> Material:
        import pubchempy as pcp
        compound = pcp.Compound.from_cid(pubchem_cid)
        material = Material(
            name=compound.synonyms[0],
            pubchem_cid=compound.cid,
            full_name=compound.synonyms[0],
            iupac_name=compound.iupac_name,
            molecular_weight=compound.molecular_weight,
            metadata={},
            type='compound',
            density=None,
            concentration_units=None
        )
        return material


    def search_name(self, name: str, case_sensitive: bool = False, show_hidden: bool = False) -> List[Material]:
        hidden_clause = "" if show_hidden else " AND hidden = 0"
        like_op = "LIKE" if case_sensitive else "LIKE"
        res = self.db.execute(
            f"SELECT * FROM {self.table_name} WHERE name {like_op} ?{hidden_clause}",
            (f'%{name}%',)
        )
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
    
    def get_all_materials(self, show_hidden: bool = False) -> List[Material]:
        hidden_clause = "" if show_hidden else " WHERE hidden = 0"
        res = self.db.execute(f"SELECT * FROM {self.table_name}{hidden_clause}")
        materials = res.fetchall()
        return [Material(*m) for m in materials]

    def set_hidden(self, name: str, hidden: bool) -> None:
        self.db.execute(
            f"UPDATE {self.table_name} SET hidden=? WHERE name=?",
            (1 if hidden else 0, name)
        )
        self.db.commit()
    
    def delete_material(self, material: Material) -> None:
        self.db.execute(f"DELETE FROM {self.table_name} WHERE name=?", (material.name,))
        self.db.commit()

