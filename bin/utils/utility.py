from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import requests
import utils.emojis as emoji
from akamai_apis import cps
from tabulate import tabulate


class Utility():
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.hostnames = []
        self.waiting = f'{emoji.clock} waiting'
        self.s = requests.Session()
        self.max_column_width = 20
        self.column_width = 30

    def call_api(self, logger, cps: cps.Enrollment, chunk: list, contract_id: str | None = None):
        if contract_id:
            cps._params['contractId'] = contract_id

        api_result = []
        for x in chunk:
            enrollment_id = x['location'].split('/')[-1]
            resp = cps.get_enrollment(enrollment_id)
            count = 1
            if not resp.ok:
                msg = f'{contract_id:<10} {enrollment_id:<10}'
                logger.error(f'{count}   {resp.status_code}    {msg}')

                while resp.status_code in [429, 500]:
                    count += 1
                    resp = cps.get_enrollment(enrollment_id)
                    if resp.ok:
                        logger.info(f'{count}   {resp.status_code}    {msg}')
                    elif resp.status_code == 429:
                        detail = resp.json()['Detail']
                        logger.info(f'{detail}    {msg}')
                        pattern = r'(Retry after: )(\d+)( seconds\.)'
                        match = re.search(pattern, detail)
                        if match:
                            detail = f'{match.group(1)} {match.group(2)} {match.group(3)}'
                            logger.warning(detail)
                            sleep_time = int(match.group(2)) + 3
                            logger.warning(sleep_time)
                            time.sleep(sleep_time)
                        else:
                            logger.error('No match found')
                        logger.warning(f'{count}   {detail}    {msg} {match}')

                    else:
                        resp = cps.get_enrollment(enrollment_id)
                        logger.error(f'{count}   {resp.status_code}    {msg}')

            api_result.append(resp.json())
        return api_result

    def split_into_chunks(self, lst, chunk_size):
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]

    def load_json(self, logger, filepath: str) -> dict:
        with open(filepath) as user_file:
            file_contents = user_file.read()
        filepath = Path(f'{filepath}').absolute()
        logger.debug(f'Found JSON file at {str(filepath)}')
        content_str = json.loads(file_contents)
        content_json = json.dumps(content_str, indent=2)
        return content_json

    def write_json(self, logger, filepath: str, json_object: dict) -> None:
        with open(filepath, 'w') as f:
            json.dump(dict(json_object), f, indent=4)
        filepath = Path(f'{filepath}').absolute()
        print()
        logger.info(f'JSON file is saved locally at {filepath}')

    def found_duplicate_cn(self, logger, enrollment: dict, common_name: str) -> bool:
        found = False
        for x in enrollment:
            if x['cn'] == common_name and 'sans' in x and common_name in x['sans']:
                found = True
                logger.debug(x)
        return found

    def show_enrollments_table(self, logger, args, enrollments: list):
        show_expiration = args.show_expiration
        enrls = [x for x in enrollments]
        enrls_output = []
        i = 1
        for enrl in enrls:
            enrollment_id = enrl['location'].split('/')[-1]
            try:
                san_count = len(enrl['csr']['sans'])
            except KeyError:
                san_count = 0

            cn = enrl['csr']['cn']
            if san_count > 0:
                cn = f'{cn} ({san_count})'

            if enrl['certificateType'] == 'third-party':
                cert_type = 'third-party'
            else:
                cert_type = f"{enrl['validationType']} {enrl['certificateType']}"
            pendingChanges = '*Yes*' if len(enrl['pendingChanges']) != 0 else ' No'
            enrollment_id = f'**{enrollment_id}' if len(enrl['pendingChanges']) != 0 else enrollment_id
            changeManagement = 'Yes' if enrl['changeManagement'] else 'No'

            if show_expiration:
                deploy = cps.Deployment(args, logger, enrollment_id)
                expired_resp = deploy.get_product_deployement()
                expiration = ' '
                if expired_resp.ok:
                    pem = expired_resp.json()['certificate']
                    expiration = cps.Certificate(pem).expiration
                    logger.debug(f'{enrollment_id} {expiration}')

                enrls_output.append([i, enrollment_id, cn, cert_type, pendingChanges, changeManagement, expiration])

            if not show_expiration:
                enrls_output.append([i, enrollment_id, cn, cert_type, pendingChanges, changeManagement])

            i += 1

        sorted_output = sorted(enrls_output, key=lambda x: x[4].strip())
        # reset index column
        for i, row in enumerate(sorted_output):
            row[0] = i + 1

        if show_expiration:
            headers = ['Enrollment ID', 'Common Name (SAN Count)', 'Certificate Type',
                       '*In-Progress*', 'Test on Staging First', 'Expiration']
        else:
            headers = ['Enrollment ID', 'Common Name (SAN Count)', 'Certificate Type',
                       '*In-Progress*', 'Test on Staging First']

        print(tabulate(sorted_output, headers=headers, tablefmt='psql'))
        logger.warning('** means enrollment has existing pending changes')


def format_enrollments_table(logger, enrollment: list, show_expiration: bool | None = False):

    enrollment_id = f'*{enrollment["id"]}*' if len(enrollment['pendingChanges']) != 0 else enrollment['id']
    san_count = len(enrollment['csr']['sans']) if len(enrollment['csr']['sans']) > 0 else 1
    common_name = f'{enrollment["csr"]["cn"]} ({san_count})'
    certificate_type = f'{enrollment["validationType"]} {enrollment["certificateType"]}'
    in_progress = '*Yes*' if len(enrollment['pendingChanges']) != 0 else ' No'
    change_management = 'Yes' if enrollment['changeManagement'] else 'No'
    slot = (','.join([str(item) for item in enrollment['assignedSlots']])
            if (len(enrollment['assignedSlots']) > 0) else '[dim] no slot assigned')
    sni = 'Yes' if enrollment['networkConfiguration']['sniOnly'] else 'No'

    return enrollment_id, common_name, certificate_type, in_progress, change_management, slot, sni
