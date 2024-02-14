from __future__ import annotations

import sys

from utils import cli_logging as lg
from utils.parser import AkamaiParser as Parser

if __name__ == '__main__':
    args = Parser.get_args(args=None if sys.argv[1:] else ['--help'])
    account_switch_key, section, edgerc = args.account_switch_key, args.section, args.edgerc

    logger = lg.setup_logger(args)
