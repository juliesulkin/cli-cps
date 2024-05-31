from __future__ import annotations

import sys

from akamai_apis.cps import Cps
from akamai_apis.idm import IdentityAccessManagement
from rich.console import Console
from utils import cli_logging as lg
from utils.parser import AkamaiParser as Parser
from utils.utility import utility

console = Console(stderr=True)


def build_class_objects(logger, args):
    idm = IdentityAccessManagement(logger, args)
    account_name = idm()
    cps = Cps(logger, args)
    util = utility(logger)
    return (account_name, cps, util)


def list(args, logger):
    account_name, cps, util = build_class_objects(logger, args)
    header_msg = f'\nAccount: {account_name}\n'
    header_title = 'CPS CLI: [i]List Enrollments[/i]'
    lg.console_panel(console, header_msg, header_title, align='center')


if __name__ == '__main__':
    args = Parser.get_args(args=None if sys.argv[1:] else ['--help'])
    account_switch_key, section, edgerc = args.account_switch_key, args.section, args.edgerc

    logger = lg.setup_logger(args)

    if args.command == 'list':
        done = list(args, logger)
