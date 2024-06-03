from __future__ import annotations

import asyncio
import json
import sys

from akamai_apis import cps
from akamai_apis.cps import Cps
from akamai_apis.idm import IdentityAccessManagement
from rich.console import Console
from utils import cli_logging as lg
from utils import cps as util_cps
from utils import utility as util
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

    cps_api = cps.Enrollment(account_switch_key, section, edgerc, logger)
    with open('setup/tesla.json') as f:
        enrollments = json.load(f)['enrollments']

    if args.command == 'list':
        enrollments = util_cps.list_enrollment(cps_api, args, logger)
        print()

        if args.show_expiration:
            logger.warning('Fetching list with production expiration dates. Please wait...')
        util.show_enrollments_table(logger, enrollments, args.show_expiration, account_switch_key)
        if args.json:
            json_object = {'enrollments': enrollments}
            util.write_json(logger, 'setup/enrollments.json', json_object)

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
