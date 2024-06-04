from __future__ import annotations

import asyncio
import sys

from akamai_apis import cps
from akamai_apis.idm import IdentityAccessManagement
from rich.console import Console
from utils import cli_logging as lg
from utils import cps as util_cps
from utils.parser import AkamaiParser as Parser
from utils.utility import Utility

console = Console(stderr=True)


def build_class_objects(args, logger, cps: cps.Enrollment):
    idm = IdentityAccessManagement(args, logger)
    account_name = idm()
    util = Utility(logger)
    cps_enrollment = cps.Enrollment(args, logger)
    cps_change = cps.Changes(args, logger)
    cps_deploy = cps.Deployment(args, logger)

    return (account_name, util, cps_enrollment, cps_change, cps_deploy)


if __name__ == '__main__':
    args = Parser.get_args(args=None if sys.argv[1:] else ['--help'])
    logger = lg.setup_logger(args)
    (account_name, util,
     cps_enrollment, cps_change, cps_deploy) = build_class_objects(args, logger, cps)

    header_msg = f'\nAccount: {account_name}\n'
    header_title = f'CPS CLI: [i]{args.command}[/i]'
    lg.console_panel(console, header_msg, header_title, align='center')
    console.print()

    if args.command == 'list':
        enrollments = util_cps.list_enrollment(cps_enrollment, util, args, logger)
        if args.show_expiration:
            logger.warning('Fetching list with production expiration dates. Please wait...')

        if args.json:
            json_object = {'enrollments': enrollments}
            util.write_json(logger, 'setup/enrollments.json', json_object)

    if args.command == 'retrieve-enrollment':
        util_cps.retrieve_enrollment(cps_enrollment, util, args, logger)

    if args.command == 'update':
        util_cps.update_enrollment(cps_enrollment, args, logger)

    if args.command == 'cancel':
        util_cps.cancel_enrollment(cps_enrollment, args, logger)

    if args.command == 'delete':
        util_cps.delete_enrollment(cps_enrollment, args, logger)

    if args.command == 'audit':
        asyncio.run(util_cps.audit(args, logger, util,
                                   cps_enrollment,
                                   cps_change,
                                   cps_deploy))

    if args.command == 'proceed':
        pass
