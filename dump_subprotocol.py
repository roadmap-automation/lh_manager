"""Dump subprotocol and method group step data from SQLite for debugging."""
import json
import sys

from lh_manager.subprotocol.db import init_db, get_subprotocol_by_name, list_subprotocols
from lh_manager.method_group.db import init_db as mg_init_db, list_method_groups, get_method_group_by_name

init_db()
mg_init_db()

name = sys.argv[1] if len(sys.argv) > 1 else "MultiInstrumentSleepGroupTest"

sp = get_subprotocol_by_name(name)
if sp:
    print(f"=== SUBPROTOCOL: {name} ===")
    print(json.dumps(json.loads(sp["steps"]), indent=2))
    print()
else:
    print(f"Subprotocol '{name}' not found.")
    print("Available subprotocols:")
    for s in list_subprotocols():
        print(f"  {s['name']}")
    print()

print("=== ALL METHOD GROUPS ===")
for mg in list_method_groups():
    full = get_method_group_by_name(mg["name"])
    print(f"--- {mg['name']} ---")
    print(json.dumps(json.loads(full["steps"]), indent=2))
    print()
