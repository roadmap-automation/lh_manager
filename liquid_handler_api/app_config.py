from argparse import ArgumentParser
from pathlib import Path

parser = ArgumentParser()
parser.add_argument('--noload', action='store_true')
parser.add_argument('--channels', type=int, default=2)

LOG_PATH = Path(__file__).parent.parent / 'persistent_state'
LAYOUT_LOG = LOG_PATH / 'layout.json'
SAMPLES_LOG = LOG_PATH / 'samples.json'

class Config:

    log_path: str = LOG_PATH
    layout_path: str = LAYOUT_LOG
    samples_path: str = SAMPLES_LOG

    stage_names: list[str] = ['prep', 'inject']

config = Config()