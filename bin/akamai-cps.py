from __future__ import annotations

import logging
import sys
from time import perf_counter

from akamai_apis import cps
from akamai_apis.idm import IdentityAccessManagement
from rich.console import Console
from utils import cli_logging as lg
from utils import cps as util_cps
from utils.parser import AkamaiParser as Parser
from utils.utility import Utility


console = Console(stderr=True)
logger = logging.getLogger(__name__)


def build_class_objects(args, cps: cps.Enrollment):
    idm = IdentityAccessManagement(args)
    account_name = idm()
    util = Utility()
    cps_enrollment = cps.Enrollment(args)
    cps_change = cps.Changes(args)
    cps_deploy = cps.Deployment(args)

    return (account_name, util, cps_enrollment, cps_change, cps_deploy)


if __name__ == '__main__':
    args = Parser.get_args(args=None if sys.argv[1:] else ['--help'])
    logger = lg.setup_logger(args)
    logger.info('Starting Akamai CPS CLI')

    (account_name, util,
     cps_enrollment, cps_change, cps_deploy) = build_class_objects(args, cps)

    header_msg = f'\nAccount   : {account_name}\n'
    if args.account_switch_key:
        ask_without_type = args.account_switch_key.split(':')[0]
        header_msg = f'{header_msg}Account ID: {ask_without_type}\n'
    header_title = f'CPS CLI: [i]{args.command}[/i]'
    lg.console_panel(console, header_msg, header_title, color='magenta', align='center')

    start_time = perf_counter()
    if args.command == 'list':
        enrollments = util_cps.list_enrollment(cps_enrollment, cps_deploy, util, args)
        if args.show_expiration:
            logger.warning('Fetching list with production expiration dates. Please wait...')

        if args.json:
            json_object = {'enrollments': enrollments}
            util.write_json('setup/enrollments.json', json_object)

    if args.command == 'retrieve-enrollment':
        util_cps.retrieve_enrollment(cps_enrollment, util, args)

    if args.command == 'update':
        util_cps.update_enrollment(cps_enrollment, args)

    if args.command == 'cancel':
        util_cps.cancel_enrollment(cps_enrollment, args)

    if args.command == 'delete':
        util_cps.delete_enrollment(cps_enrollment, args)

    if args.command == 'audit':
        util_cps.audit(args, util, cps_enrollment, cps_change, cps_deploy)

    if args.command == 'proceed':
        util_cps.deploy_enrollment(cps_enrollment, cps_change, util, args)

    end_time = lg.log_cli_timing(start_time)
    console.print(f'[dim]{end_time}', highlight=False)
    logger.info(end_time)
