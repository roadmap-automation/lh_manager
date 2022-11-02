"""Utilities for web server"""

def reinstantiate(obj, target_class):
    """Used in dataclass.__post_init__ to reinstantiate nested dataclasses"""
    if isinstance(obj, dict):
        obj = target_class(**obj)

    return obj

def reinstantiate_list(obj_list, target_class):
    """Used in dataclass.__post_init__ to reinstantiate lists of nested dataclasses"""
    for i, obj in enumerate(obj_list):
        obj_list[i] = reinstantiate(obj, target_class)

    return obj_list
