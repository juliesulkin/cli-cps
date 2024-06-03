from __future__ import annotations

import asyncio
import sys

from akamai_apis import cps
from akamai_apis.cps import Cps
from akamai_apis.idm import IdentityAccessManagement
from rich.console import Console
from utils import cli_logging as lg
from utils import cps as util_cps
from utils.parser import AkamaiParser as Parser
from utils.utility import Utility


console = Console(stderr=True)


def build_class_objects(logger, args):
    idm = IdentityAccessManagement(logger, args)
    account_name = idm()
    cps = Cps(logger, args)
    util = Utility(logger)
    return (account_name, cps, util)


def list(logger, args):
    account_name, cps, util = build_class_objects(logger, args)
    header_msg = f'\nAccount: {account_name}\n'
    header_title = 'CPS CLI: [i]List Enrollments[/i]'
    lg.console_panel(console, header_msg, header_title, align='center')
    console.print()


if __name__ == '__main__':
    args = Parser.get_args(args=None if sys.argv[1:] else ['--help'])
    account_switch_key, section, edgerc = args.account_switch_key, args.section, args.edgerc
    logger = lg.setup_logger(args)
    cps_api = cps.Enrollment(account_switch_key, section, edgerc, logger)

    if args.command == 'list':
        done = list(args, logger)

    if args.command == 'retrieve-enrollment':
        util_cps.retrieve_enrollment(cps_api, args, logger)

    if args.command == 'update':
        util_cps.update_enrollment(cps_api, args, logger)

    if args.command == 'cancel':
        util_cps.cancel_enrollment(cps_api, args, logger)

    if args.command == 'delete':
        util_cps.delete_enrollment(cps_api, args, logger)

    if args.command == 'audit':
        asyncio.run(util_cps.audit(cps_api, args, logger))

    if args.command == 'proceed':
        pass
