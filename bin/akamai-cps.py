from __future__ import annotations

import asyncio
import json
import sys

from akamai_apis import cps
from utils import cli_logging as lg
from utils import cps as util_cps
from utils import utility as util
from utils.parser import AkamaiParser as Parser


if __name__ == '__main__':
    args = Parser.get_args(args=None if sys.argv[1:] else ['--help'])
    account_switch_key, section, edgerc = args.account_switch_key, args.section, args.edgerc
    logger = lg.setup_logger(args)

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
