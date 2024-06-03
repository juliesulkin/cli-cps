from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import time
from pathlib import Path
from time import perf_counter

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


def call_api(logger, cps: cps.Enrollment, chunk: list, contract_id: str | None = None):
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


def foo(logger, cps: cps.Enrollment, args,
        contract_id: str | None = None,
        enrollments: list | None = []):
    # thread processing
    concurrency = 3
    chunk_size = 5

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        logger.info(f'Contract {contract_id:<10}')
        t0 = perf_counter()
        all_results = []
        total_size = len(enrollments)
        if total_size == 0:
            enrl_resp = cps.list_enrollment(contract_id)
        if not enrl_resp.ok:
            logger.warning(f'Contract {contract_id:<10}     invalid   contract')
            print()
        else:
            enrollments = enrl_resp.json().get('enrollments', [])
            chunks = list(split_into_chunks(enrollments, chunk_size))
            future_to_chunk = {}
            for chunk in chunks:
                future = executor.submit(call_api, logger, cps, chunk, contract_id)
                future_to_chunk[future] = chunk
                time.sleep(3)

            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    chunk_result = future.result()
                    all_results.extend(chunk_result)  # Combine results from each chunk
                except Exception as err:
                    logger.error(err)
            t1 = perf_counter()

            total_size = len(all_results)
            if total_size == 0:
                logger.warning(f'Contract {contract_id:<10}     no     enrollments')
            else:
                logger.warning(f'Contract {contract_id:<10}     {total_size:>3} enrollments    {t1 - t0:.2f} seconds')
            print()

    return all_results


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


def show_enrollments_table(logger, enrollments: list,
                           show_expiration: bool | None = False,
                           account_switch_key: str | None = None):
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
            deploy = cps.Deployment(enrollment_id, account_switch_key)
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
    headers = ['Enrollment ID', 'Common Name (SAN Count)', 'Certificate Type', '*In-Progress*', 'Test on Staging First', 'Expiration']
    print(tabulate(sorted_output, headers=headers, tablefmt='psql'))
    logger.warning('** means enrollment has existing pending changes')
