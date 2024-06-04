from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import requests
import utils.emojis as emoji
from akamai_apis.cps import Deployment
# import concurrent.futures
# from time import perf_counter
# from tabulate import tabulate


class Utility():
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.hostnames = []
        self.waiting = f'{emoji.clock} waiting'
        self.s = requests.Session()
        self.max_column_width = 20
        self.column_width = 30


def call_api(logger, cps, chunk: list, contract_id: str | None = None):
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


def split_into_chunks(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def load_json(logger, filepath: str) -> dict:
    with open(filepath) as user_file:
        file_contents = user_file.read()
    filepath = Path(f'{filepath}').absolute()
    logger.debug(f'Found JSON file at {str(filepath)}')
    content_str = json.loads(file_contents)
    content_json = json.dumps(content_str, indent=2)
    return content_json


def write_json(logger, filepath: str, json_object: dict) -> None:
    with open(filepath, 'w') as f:
        json.dump(dict(json_object), f, indent=4)
    filepath = Path(f'{filepath}').absolute()
    print()
    logger.info(f'JSON file is saved locally at {filepath}')


def found_duplicate_cn(logger, enrollment: dict, common_name: str) -> bool:
    found = False
    for x in enrollment:
        if x['cn'] == common_name and 'sans' in x and common_name in x['sans']:
            found = True
            logger.debug(x)
    return found


def get_deployment_wrapper(logger, enrollments, cps_deployment: Deployment):
    api_result = {}
    for enrollment in enrollments:
        resp = cps_deployment.get_production_deployment(override_enrollment_id=enrollment['id'])
        if not resp.ok:
            logger.error(resp.text)
            deployment = False
        else:
            deployment = resp.json()['primaryCertificate']
        api_result[enrollment['id']] = deployment

    return (api_result)


def format_enrollments_table(logger, enrollment: list, show_expiration: bool | None = False):
    enrollment_id = f'*{enrollment["id"]}*' if len(enrollment['pendingChanges']) != 0 else str(enrollment['id'])
    san_count = len(enrollment['csr']['sans']) if len(enrollment['csr']['sans']) > 0 else 1
    common_name = f'{enrollment["csr"]["cn"]} ({san_count})'
    certificate_type = f'{enrollment["validationType"]} {enrollment["certificateType"]}'
    in_progress = '*Yes*' if len(enrollment['pendingChanges']) != 0 else ' No'
    change_management = 'Yes' if enrollment['changeManagement'] else 'No'
    slot = (','.join([str(item) for item in enrollment['assignedSlots']])
            if (len(enrollment['assignedSlots']) > 0) else '[dim] no slot assigned')
    sni = 'Yes' if enrollment['networkConfiguration']['sniOnly'] else 'No'

    rows = [enrollment_id, common_name, certificate_type, in_progress, change_management, slot, sni]
    if show_expiration:
        rows.append(enrollment['certificate']['expiry'])

    return rows
