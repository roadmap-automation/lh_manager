from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--noload', action='store_true')
parser.add_argument('--channels', type=int, default=2)
