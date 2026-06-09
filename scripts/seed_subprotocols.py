"""Seed the lh_manager subprotocol DB with the canonical ROADMAP definitions.

lh_manager is now the authoritative owner of subprotocol definitions (Phase 2
Step A).  This script replaces lh-protocol-studio/scripts/seed_subprotocols.py
as the canonical seed source.

Usage (run from the lh_manager package root or any directory):
    python scripts/seed_subprotocols.py [--dry-run] [--update]

The script is idempotent: existing subprotocols are skipped unless --update is
passed, which overwrites them.

Step node schema (type: "method", the default):
    {
        "id":          "<unique step id within this subprotocol>",
        "type":        "method",
        "method_name": "<device method name as reported via device.registered>",
        "parameters":  {
            "<param>": <literal>  |  {"$ref": "input.<name>"}  |  {"$alloc": "<handle>"}
        }
    }

Step node schema (type: "subprotocol" — nested call):
    {
        "id":               "<unique step id>",
        "type":             "subprotocol",
        "subprotocol_name": "<name of child subprotocol in lh_manager DB>",
        "parameters":       {"<child_input>": <literal> | {"$ref": "..."} | {"$alloc": "..."}},
        "output_alias":     {"<child_output_name>": "<parent_output_name>"}
    }

Subprotocol-level fields:
    execution   — "sequential" (default) | "parallel"
    allocations — list of logical resource handle names; broker mints a UUID for each.
    method_type — "prepare" | "transfer" | "measure" (parallel subprotocols only).
"""

import argparse
import json
import sys
import os

# Allow running directly from the scripts/ folder or from lh_manager root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lh_manager.subprotocol import db
from lh_manager.method_group import db as mg_db


METHOD_GROUPS = [
    {
        "name": "ROADMAP_LoadLoop_Parallel",
        "method_type": "transfer",
        "description": "Parallel LH loop load (ROADMAP_QCMD_LoadLoop) + IS loop load (LoadLoopBubbleSensor), coordinated via broker-mediated GSIOC.",
        "steps": [
            {
                "method_name": "ROADMAP_QCMD_LoadLoop",
                "parameters": {
                    "Source":                     {"$ref": "input.Source"},
                    "Volume":                     {"$ref": "input.Volume"},
                    "Aspirate_Flow_Rate":         {"$ref": "input.Aspirate_Flow_Rate"},
                    "Flow_Rate":                  {"$ref": "input.Flow_Rate"},
                    "Outside_Rinse_Volume":       {"$ref": "input.Outside_Rinse_Volume"},
                    "Extra_Volume":               {"$ref": "input.Extra_Volume"},
                    "Air_Gap":                    {"$ref": "input.Air_Gap"},
                    "Use_Liquid_Level_Detection": {"$ref": "input.Use_Liquid_Level_Detection"},
                },
                "composition_source": False,
            },
            {
                "method_name": "LoadLoopBubbleSensor",
                "parameters": {
                    "pump_volume":    {"$ref": "input.Volume"},
                    "pump_flow_rate": {"$ref": "input.Flow_Rate"},
                },
                "composition_source": False,
            },
        ],
        "exposed_fields": [],
    },
    {
        "name": "ROADMAP_DirectInject_Parallel",
        "method_type": "transfer",
        "description": "Parallel LH direct inject (ROADMAP_QCMD_DirectInject) + IS direct inject (DirectInjectBubbleSensor), coordinated via broker-mediated GSIOC.",
        "steps": [
            {
                "method_name": "ROADMAP_QCMD_DirectInject",
                "parameters": {
                    "Source":                     {"$ref": "input.Source"},
                    "Volume":                     {"$ref": "input.Volume"},
                    "Injection_Flow_Rate":        {"$ref": "input.Injection_Flow_Rate"},
                    "Aspirate_Flow_Rate":         {"$ref": "input.Aspirate_Flow_Rate"},
                    "Load_Flow_Rate":             {"$ref": "input.Load_Flow_Rate"},
                    "Outside_Rinse_Volume":       {"$ref": "input.Outside_Rinse_Volume"},
                    "Extra_Volume":               {"$ref": "input.Extra_Volume"},
                    "Air_Gap":                    {"$ref": "input.Air_Gap"},
                    "Use_Liquid_Level_Detection": {"$ref": "input.Use_Liquid_Level_Detection"},
                    "Use_Bubble_Sensors":         {"$ref": "input.Use_Bubble_Sensors"},
                },
                "composition_source": False,
            },
            {
                "method_name": "DirectInjectBubbleSensor",
                "parameters": {
                    "pump_volume":    {"$ref": "input.Volume"},
                    "pump_flow_rate": {"$ref": "input.Injection_Flow_Rate"},
                },
                "composition_source": False,
            },
        ],
        "exposed_fields": [],
    },
]


SUBPROTOCOLS = [
    # =========================================================================
    # Tier-1: atomic single-device or parallel compound operations
    # =========================================================================

    {
        "name": "MultiInstrumentSleep",
        "execution": "parallel",
        "method_type": "prepare",
        "steps": [
            {
                "id": "step_lh_sleep",
                "method_name": "NCNR_Sleep",
                "parameters": {
                    "Time": {"$ref": "input.lh_sleep_time"},
                },
            },
            {
                "id": "step_is_sleep",
                "method_name": "RoadmapChannelSleep",
                "parameters": {
                    "sleep_time": {"$ref": "input.is_sleep_time"},
                },
            },
        ],
        "inputs": {
            "lh_sleep_time": "float",
            "is_sleep_time": "float",
        },
        "outputs": {},
    },

    {
        "name": "ROADMAP_RinseDirectInjecttoQCMD",
        "steps": [
            {
                "id": "step_rinse_inject",
                "method_name": "RinseDirectInject",
                "parameters": {
                    "composition":        {"$ref": "input.composition"},
                    "pump_volume":        {"$ref": "input.volume"},
                    "inject_flow_rate":   {"$ref": "input.flow_rate"},
                    "flow_rate":          1.0,
                    "aspirate_flow_rate": 1.0,
                    "rinse_volume":       0.5,
                    "excess_volume":      0.1,
                    "air_gap":            0.1,
                },
            },
            {
                "id": "step_accept",
                "method_name": "QCMDAcceptTransfer",
                "parameters": {
                    "contents": {"$ref": "input.composition"},
                },
            },
        ],
        "inputs": {
            "composition": "Composition",
            "volume": "float",
            "flow_rate": "float",
        },
        "outputs": {},
    },

    {
        "name": "ROADMAP_DirectInjectPrime",
        "steps": [
            {
                "id": "step_prime",
                "method_name": "DirectInjectPrime",
                "parameters": {
                    "pump_volume":    {"$ref": "input.volume"},
                    "pump_flow_rate": {"$ref": "input.flow_rate"},
                },
            },
        ],
        "inputs": {
            "volume": "float",
            "flow_rate": "float",
        },
        "outputs": {},
    },

    # =========================================================================
    # Tier-2: sequential measurement workflows
    # =========================================================================

    {
        "name": "ROADMAP_QCMD_DirectInjectandMeasure",
        "allocations": ["well_id"],
        "steps": [
            {
                "id": "step_locate",
                "method_name": "Formulation",
                "parameters": {
                    "target_composition": {"$ref": "input.composition"},
                    "target_volume":      {"$ref": "input.volume"},
                    "Target":             {"id": {"$alloc": "well_id"}},
                },
            },
            {
                "id": "step_inject",
                "type": "method_group",
                "method_group_name": "ROADMAP_DirectInject_Parallel",
                "parameters": {
                    "Source":                     {"id": {"$alloc": "well_id"}},
                    "Volume":                     {"$ref": "input.volume"},
                    "Injection_Flow_Rate":        {"$ref": "input.injection_flow_rate"},
                    "Aspirate_Flow_Rate":         1.0,
                    "Load_Flow_Rate":             2.0,
                    "Outside_Rinse_Volume":       0.5,
                    "Extra_Volume":               0.1,
                    "Air_Gap":                    0.15,
                    "Use_Liquid_Level_Detection": False,
                    "Use_Bubble_Sensors":         True,
                },
            },
            {
                "id": "step_accept",
                "method_name": "QCMDAcceptTransfer",
                "parameters": {
                    "contents": {"$ref": "input.composition"},
                },
            },
            {
                "id": "step_record",
                "method_name": "QCMDRecord",
                "parameters": {
                    "record_time": {"$ref": "input.measurement_time"},
                    "sleep_time":  {"$ref": "input.equilibration_time"},
                },
            },
        ],
        "inputs": {
            "composition": "Composition",
            "volume": "float",
            "injection_flow_rate": "float",
            "measurement_time": "float",
            "equilibration_time": "float",
        },
        "outputs": {
            "qcmd_data": {"step_id": "step_record", "type": "QCMDData"},
        },
    },

    {
        "name": "ROADMAP_QCMD_RinseDirectInjectandMeasure",
        "steps": [
            {
                "id": "step_rinse_inject",
                "method_name": "RinseDirectInject",
                "parameters": {
                    "composition":        {"$ref": "input.composition"},
                    "pump_volume":        {"$ref": "input.volume"},
                    "inject_flow_rate":   {"$ref": "input.flow_rate"},
                    "flow_rate":          1.0,
                    "aspirate_flow_rate": 1.0,
                    "rinse_volume":       0.5,
                    "excess_volume":      0.1,
                    "air_gap":            0.1,
                },
            },
            {
                "id": "step_accept",
                "method_name": "QCMDAcceptTransfer",
                "parameters": {
                    "contents": {"$ref": "input.composition"},
                },
            },
            {
                "id": "step_record",
                "method_name": "QCMDRecord",
                "parameters": {
                    "record_time": {"$ref": "input.measurement_time"},
                    "sleep_time":  {"$ref": "input.equilibration_time"},
                },
            },
        ],
        "inputs": {
            "composition": "Composition",
            "volume": "float",
            "flow_rate": "float",
            "measurement_time": "float",
            "equilibration_time": "float",
        },
        "outputs": {
            "qcmd_data": {"step_id": "step_record", "type": "QCMDData"},
        },
    },

    {
        "name": "ROADMAP_DirectInjecttoQCMD",
        "allocations": ["well_id"],
        "steps": [
            {
                "id": "step_formulate",
                "method_name": "SoluteFormulation",
                "parameters": {
                    "target_composition": {"$ref": "input.target_composition"},
                    "target_volume":      {"$ref": "input.volume"},
                    "Target":             {"id": {"$alloc": "well_id"}},
                },
            },
            {
                "id": "step_inject",
                "type": "method_group",
                "method_group_name": "ROADMAP_DirectInject_Parallel",
                "parameters": {
                    "Source":                     {"id": {"$alloc": "well_id"}},
                    "Volume":                     {"$ref": "input.volume"},
                    "Injection_Flow_Rate":        {"$ref": "input.injection_flow_rate"},
                    "Aspirate_Flow_Rate":         1.0,
                    "Load_Flow_Rate":             2.0,
                    "Outside_Rinse_Volume":       0.5,
                    "Extra_Volume":               0.1,
                    "Air_Gap":                    0.15,
                    "Use_Liquid_Level_Detection": False,
                    "Use_Bubble_Sensors":         True,
                },
            },
            {
                "id": "step_accept",
                "method_name": "QCMDAcceptTransfer",
                "parameters": {
                    "contents": {"$ref": "input.target_composition"},
                },
            },
            {
                "id": "step_record",
                "method_name": "QCMDRecord",
                "parameters": {
                    "record_time": {"$ref": "input.measurement_time"},
                    "sleep_time":  {"$ref": "input.equilibration_time"},
                },
            },
        ],
        "inputs": {
            "target_composition": "Composition",
            "volume": "float",
            "injection_flow_rate": "float",
            "measurement_time": "float",
            "equilibration_time": "float",
        },
        "outputs": {
            "qcmd_data": {"step_id": "step_record", "type": "QCMDData"},
        },
    },

    {
        "name": "ROADMAP_QCMD_RinseLoopInjectandMeasure",
        "steps": [
            {
                "id": "step_rinse_load",
                "method_name": "RinseLoadLoopBubbleSensor",
                "parameters": {
                    "composition":        {"$ref": "input.target_composition"},
                    "pump_volume":        {"$ref": "input.volume"},
                    "aspirate_flow_rate": 6.0,
                    "flow_rate":          3.0,
                    "rinse_volume":       0.5,
                    "excess_volume":      0.1,
                    "air_gap":            0.2,
                },
            },
            {
                "id": "step_inject",
                "method_name": "InjectLoopBubbleSensor",
                "parameters": {
                    "pump_volume":    {"$ref": "input.volume"},
                    "pump_flow_rate": {"$ref": "input.injection_flow_rate"},
                },
            },
            {
                "id": "step_accept",
                "method_name": "QCMDAcceptTransfer",
                "parameters": {
                    "contents": {"$ref": "input.target_composition"},
                },
            },
            {
                "id": "step_record",
                "method_name": "QCMDRecord",
                "parameters": {
                    "record_time": {"$ref": "input.measurement_time"},
                    "sleep_time":  {"$ref": "input.equilibration_time"},
                },
            },
        ],
        "inputs": {
            "target_composition": "Composition",
            "volume": "float",
            "injection_flow_rate": "float",
            "measurement_time": "float",
            "equilibration_time": "float",
        },
        "outputs": {
            "qcmd_data": {"step_id": "step_record", "type": "QCMDData"},
        },
    },

    {
        "name": "ROADMAP_QCMD_LoopInjectandMeasure",
        "allocations": ["well_id"],
        "steps": [
            {
                "id": "step_locate",
                "method_name": "Formulation",
                "parameters": {
                    "target_composition": {"$ref": "input.target_composition"},
                    "target_volume":      {"$ref": "input.volume"},
                    "Target":             {"id": {"$alloc": "well_id"}},
                },
            },
            {
                "id": "step_load_loop",
                "type": "method_group",
                "method_group_name": "ROADMAP_LoadLoop_Parallel",
                "parameters": {
                    "Source":                     {"id": {"$alloc": "well_id"}},
                    "Volume":                     {"$ref": "input.volume"},
                    "Aspirate_Flow_Rate":         2.5,
                    "Flow_Rate":                  2.0,
                    "Outside_Rinse_Volume":       0.5,
                    "Extra_Volume":               0.1,
                    "Air_Gap":                    0.15,
                    "Use_Liquid_Level_Detection": True,
                },
            },
            {
                "id": "step_inject",
                "method_name": "InjectLoopBubbleSensor",
                "parameters": {
                    "pump_volume":    {"$ref": "input.volume"},
                    "pump_flow_rate": {"$ref": "input.injection_flow_rate"},
                },
            },
            {
                "id": "step_accept",
                "method_name": "QCMDAcceptTransfer",
                "parameters": {
                    "contents": {"$ref": "input.target_composition"},
                },
            },
            {
                "id": "step_record",
                "method_name": "QCMDRecord",
                "parameters": {
                    "record_time": {"$ref": "input.measurement_time"},
                    "sleep_time":  {"$ref": "input.equilibration_time"},
                },
            },
        ],
        "inputs": {
            "target_composition": "Composition",
            "volume": "float",
            "injection_flow_rate": "float",
            "measurement_time": "float",
            "equilibration_time": "float",
        },
        "outputs": {
            "qcmd_data": {"step_id": "step_record", "type": "QCMDData"},
        },
    },

    # =========================================================================
    # Tier-3: bilayer assembly workflows (compose Tier-2 subprotocols)
    # =========================================================================

    {
        "name": "ROADMAP_QCMD_MakeBilayer_AllRinse",
        "steps": [
            {
                "type": "subprotocol",
                "id": "solvent_phase",
                "subprotocol_name": "ROADMAP_QCMD_RinseLoopInjectandMeasure",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_solvent"},
                    "volume":              {"$ref": "input.rinse_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    60.0,
                    "equilibration_time":  60.0,
                },
                "output_alias": {"qcmd_data": "qcmd_solvent"},
            },
            {
                "type": "subprotocol",
                "id": "lipid_phase",
                "subprotocol_name": "ROADMAP_DirectInjecttoQCMD",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_composition"},
                    "volume":              {"$ref": "input.lipid_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_lipid"},
            },
            {
                "type": "subprotocol",
                "id": "buffer_phase",
                "subprotocol_name": "ROADMAP_QCMD_RinseLoopInjectandMeasure",
                "parameters": {
                    "target_composition":  {"$ref": "input.buffer_composition"},
                    "volume":              {"$ref": "input.buffer_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.exchange_flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_buffer"},
            },
        ],
        "inputs": {
            "bilayer_solvent": "Composition",
            "bilayer_composition": "Composition",
            "buffer_composition": "Composition",
            "rinse_volume": "float",
            "lipid_injection_volume": "float",
            "buffer_injection_volume": "float",
            "flow_rate": "float",
            "exchange_flow_rate": "float",
            "equilibration_time": "float",
            "measurement_time": "float",
        },
        "outputs": {
            "qcmd_solvent": {"step_id": "solvent_phase", "type": "QCMDData"},
            "qcmd_lipid":   {"step_id": "lipid_phase",   "type": "QCMDData"},
            "qcmd_buffer":  {"step_id": "buffer_phase",  "type": "QCMDData"},
        },
    },

    {
        "name": "ROADMAP_QCMD_MakeBilayer_DirectSolvent_RinseBuffer",
        "steps": [
            {
                "type": "subprotocol",
                "id": "solvent_phase",
                "subprotocol_name": "ROADMAP_QCMD_LoopInjectandMeasure",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_solvent"},
                    "volume":              {"$ref": "input.rinse_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    60.0,
                    "equilibration_time":  60.0,
                },
                "output_alias": {"qcmd_data": "qcmd_solvent"},
            },
            {
                "type": "subprotocol",
                "id": "lipid_phase",
                "subprotocol_name": "ROADMAP_DirectInjecttoQCMD",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_composition"},
                    "volume":              {"$ref": "input.lipid_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_lipid"},
            },
            {
                "type": "subprotocol",
                "id": "buffer_phase",
                "subprotocol_name": "ROADMAP_QCMD_RinseLoopInjectandMeasure",
                "parameters": {
                    "target_composition":  {"$ref": "input.buffer_composition"},
                    "volume":              {"$ref": "input.buffer_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.exchange_flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_buffer"},
            },
        ],
        "inputs": {
            "bilayer_solvent": "Composition",
            "bilayer_composition": "Composition",
            "buffer_composition": "Composition",
            "rinse_volume": "float",
            "lipid_injection_volume": "float",
            "buffer_injection_volume": "float",
            "flow_rate": "float",
            "exchange_flow_rate": "float",
            "equilibration_time": "float",
            "measurement_time": "float",
        },
        "outputs": {
            "qcmd_solvent": {"step_id": "solvent_phase", "type": "QCMDData"},
            "qcmd_lipid":   {"step_id": "lipid_phase",   "type": "QCMDData"},
            "qcmd_buffer":  {"step_id": "buffer_phase",  "type": "QCMDData"},
        },
    },

    {
        "name": "ROADMAP_QCMD_MakeBilayer_RinseSolvent_DirectBuffer",
        "steps": [
            {
                "type": "subprotocol",
                "id": "solvent_phase",
                "subprotocol_name": "ROADMAP_QCMD_RinseLoopInjectandMeasure",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_solvent"},
                    "volume":              {"$ref": "input.rinse_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    60.0,
                    "equilibration_time":  60.0,
                },
                "output_alias": {"qcmd_data": "qcmd_solvent"},
            },
            {
                "type": "subprotocol",
                "id": "lipid_phase",
                "subprotocol_name": "ROADMAP_DirectInjecttoQCMD",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_composition"},
                    "volume":              {"$ref": "input.lipid_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_lipid"},
            },
            {
                "type": "subprotocol",
                "id": "buffer_phase",
                "subprotocol_name": "ROADMAP_DirectInjecttoQCMD",
                "parameters": {
                    "target_composition":  {"$ref": "input.buffer_composition"},
                    "volume":              {"$ref": "input.buffer_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.exchange_flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_buffer"},
            },
        ],
        "inputs": {
            "bilayer_solvent": "Composition",
            "bilayer_composition": "Composition",
            "buffer_composition": "Composition",
            "rinse_volume": "float",
            "lipid_injection_volume": "float",
            "buffer_injection_volume": "float",
            "flow_rate": "float",
            "exchange_flow_rate": "float",
            "equilibration_time": "float",
            "measurement_time": "float",
        },
        "outputs": {
            "qcmd_solvent": {"step_id": "solvent_phase", "type": "QCMDData"},
            "qcmd_lipid":   {"step_id": "lipid_phase",   "type": "QCMDData"},
            "qcmd_buffer":  {"step_id": "buffer_phase",  "type": "QCMDData"},
        },
    },

    {
        "name": "ROADMAP_QCMD_MakeBilayer_AllDirect",
        "steps": [
            {
                "type": "subprotocol",
                "id": "solvent_phase",
                "subprotocol_name": "ROADMAP_QCMD_LoopInjectandMeasure",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_solvent"},
                    "volume":              {"$ref": "input.rinse_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    60.0,
                    "equilibration_time":  60.0,
                },
                "output_alias": {"qcmd_data": "qcmd_solvent"},
            },
            {
                "type": "subprotocol",
                "id": "lipid_phase",
                "subprotocol_name": "ROADMAP_DirectInjecttoQCMD",
                "parameters": {
                    "target_composition":  {"$ref": "input.bilayer_composition"},
                    "volume":              {"$ref": "input.lipid_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_lipid"},
            },
            {
                "type": "subprotocol",
                "id": "buffer_phase",
                "subprotocol_name": "ROADMAP_DirectInjecttoQCMD",
                "parameters": {
                    "target_composition":  {"$ref": "input.buffer_composition"},
                    "volume":              {"$ref": "input.buffer_injection_volume"},
                    "injection_flow_rate": {"$ref": "input.exchange_flow_rate"},
                    "measurement_time":    {"$ref": "input.measurement_time"},
                    "equilibration_time":  {"$ref": "input.equilibration_time"},
                },
                "output_alias": {"qcmd_data": "qcmd_buffer"},
            },
        ],
        "inputs": {
            "bilayer_solvent": "Composition",
            "bilayer_composition": "Composition",
            "buffer_composition": "Composition",
            "rinse_volume": "float",
            "lipid_injection_volume": "float",
            "buffer_injection_volume": "float",
            "flow_rate": "float",
            "exchange_flow_rate": "float",
            "equilibration_time": "float",
            "measurement_time": "float",
        },
        "outputs": {
            "qcmd_solvent": {"step_id": "solvent_phase", "type": "QCMDData"},
            "qcmd_lipid":   {"step_id": "lipid_phase",   "type": "QCMDData"},
            "qcmd_buffer":  {"step_id": "buffer_phase",  "type": "QCMDData"},
        },
    },
]


def seed_method_groups(dry_run: bool = False, update: bool = False) -> None:
    mg_db.init_db()
    existing = {row["name"]: row["id"] for row in mg_db.list_method_groups()}

    inserted = updated = skipped = 0
    for defn in METHOD_GROUPS:
        name = defn["name"]
        steps = defn["steps"]
        description = defn.get("description")
        exposed_fields = defn.get("exposed_fields", [])
        method_type = defn.get("method_type")

        if name in existing:
            if update:
                if dry_run:
                    print(f"  DRY UPDATE  {name}")
                    print(json.dumps({"steps": steps, "method_type": method_type}, indent=2))
                else:
                    mg_db.update_method_group(
                        existing[name], name, steps,
                        description=description,
                        exposed_fields=exposed_fields,
                        method_type=method_type,
                    )
                    print(f"  UPDATE {name}  id={existing[name]}")
                updated += 1
            else:
                print(f"  SKIP  {name}  (use --update to overwrite)")
                skipped += 1
            continue

        if dry_run:
            print(f"  DRY   {name}")
            print(json.dumps({"steps": steps, "method_type": method_type}, indent=2))
        else:
            mg_id = mg_db.create_method_group(
                name, steps,
                description=description,
                exposed_fields=exposed_fields,
                method_type=method_type,
            )
            print(f"  INSERT {name}  id={mg_id}")
        inserted += 1

    print(f"\nMethod groups done: {inserted} inserted, {updated} updated, {skipped} skipped.")


def seed(dry_run: bool = False, update: bool = False) -> None:
    db.init_db()
    existing = {row["name"]: row["id"] for row in db.list_subprotocols()}

    inserted = updated = skipped = 0
    for defn in SUBPROTOCOLS:
        name = defn["name"]
        steps = defn["steps"]
        inputs = defn.get("inputs", {})
        outputs = defn.get("outputs", {})
        execution = defn.get("execution")
        allocations = defn.get("allocations", [])
        method_type = defn.get("method_type")

        if name in existing:
            if update:
                if dry_run:
                    print(f"  DRY UPDATE  {name}")
                    _print_defn(defn)
                else:
                    db.update_subprotocol(
                        existing[name], name, steps,
                        parameter_wiring=[],
                        inputs=inputs, outputs=outputs,
                        execution=execution, allocations=allocations,
                        method_type=method_type,
                    )
                    print(f"  UPDATE {name}  id={existing[name]}")
                updated += 1
            else:
                print(f"  SKIP  {name}  (use --update to overwrite)")
                skipped += 1
            continue

        if dry_run:
            print(f"  DRY   {name}")
            _print_defn(defn)
        else:
            sub_id = db.create_subprotocol(
                name, steps,
                parameter_wiring=[],
                inputs=inputs, outputs=outputs,
                execution=execution, allocations=allocations,
                method_type=method_type,
            )
            print(f"  INSERT {name}  id={sub_id}")
        inserted += 1

    print(f"\nDone: {inserted} inserted, {updated} updated, {skipped} skipped.")


def _print_defn(defn: dict) -> None:
    keys = ("steps", "execution", "allocations", "method_type", "inputs", "outputs")
    print(json.dumps({k: defn[k] for k in keys if k in defn}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print definitions without inserting.")
    parser.add_argument("--update", action="store_true",
                        help="Overwrite existing subprotocols.")
    args = parser.parse_args()
    seed_method_groups(dry_run=args.dry_run, update=args.update)
    seed(dry_run=args.dry_run, update=args.update)
