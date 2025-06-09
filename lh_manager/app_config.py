import datetime

from argparse import ArgumentParser
from logging.config import dictConfig
from pathlib import Path

parser = ArgumentParser()
parser.add_argument('--noload_samples', action='store_true')
parser.add_argument('--noload_layout', action='store_true')
parser.add_argument('--channels', type=int, default=2)

LOG_PATH = Path(__file__).parent.parent / 'logs'
PERSISTENT_PATH = Path(__file__).parent.parent / 'persistent_state'
NOTIFICATION_SETTINGS = PERSISTENT_PATH / 'notification_settings.json'
LAYOUT_LOG = PERSISTENT_PATH / 'layout.json'
SAMPLES_LOG = PERSISTENT_PATH / 'samples.json'
DEVICES_LOG = PERSISTENT_PATH / 'devices.json'
HISTORY_LOG = PERSISTENT_PATH / 'completed_samples.sqlite'

class Config:

    log_path: str = LOG_PATH
    persistent_path: str = PERSISTENT_PATH
    layout_path: str = LAYOUT_LOG
    samples_path: str = SAMPLES_LOG
    devices_path: str = DEVICES_LOG
    history_path: str = HISTORY_LOG
    notify_path: str = NOTIFICATION_SETTINGS

    stage_names: list[str] = ['prep', 'inject']

config = Config()

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'stream': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://sys.stdout',
        'level': 'INFO',
        'formatter': 'default'
    },
    'file': {
        'class': 'logging.FileHandler',
        'filename': config.log_path / (datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '_manager_log.txt'),
        'level': 'INFO',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['stream', 'file']
    }
})