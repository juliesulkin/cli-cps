from __future__ import annotations

import asyncio
import csv
import datetime
import json
import logging
import sys
import time
from collections import defaultdict
from concurrent.futures import as_completed
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import gmtime
from time import perf_counter
from time import strftime

from akamai_apis.cps import Changes
from akamai_apis.cps import Deployment
from akamai_apis.cps import Enrollment
from rich import print_json
from rich.console import Console
from rich.table import Table
from tabulate import tabulate
from utils import cli_logging as lg
from utils import emojis
from utils import util_async
from utils.util_async import run_in_executor
from utils.utility import Utility
from xlsxwriter.workbook import Workbook

console = Console(stderr=True)
logger = logging.getLogger(__name__)


def list_enrollment(cps: Enrollment, cps_deploy: Deployment,
                    util, args) -> None:
    enrollments = []
    resp = cps.list_enrollment(args.contract)
    if not resp.ok:
        logger.error(resp.text)
    else:
        enrollments = resp.json()['enrollments']

    lg.console_header(console, f'{len(enrollments)} enrollments found', emojis.gem)
    console.print()

    table = Table(title='Enrollments')
    table.add_column('Enrollment ID')
    table.add_column('Common Name (SAN Count)')
    table.add_column('Certificate Type')
    table.add_column('*In-Progress*')
    table.add_column('Test on Staging First')
    table.add_column('Slot')
    table.add_column('SNI')
    table.add_column('Expiry')

    # get all deployments
    all_results = {}
    cps_deploy.enrollment_id = enrollments[0]['id']

    with ThreadPoolExecutor(max_workers=10) as executor:
        chunks = list(util.split_into_chunks(enrollments, 5))
        future_to_chunk = {}
        for chunk in chunks:
            future = executor.submit(util.get_deployment_wrapper, chunk, cps_deploy)
            future_to_chunk[future] = chunk
            time.sleep(3)

        for future in as_completed(future_to_chunk):
            chunk = future_to_chunk[future]
            try:
                chunk_result = future.result()
                all_results.update(chunk_result)  # Combine results from each chunk
            except Exception as err:
                logger.error(err)

    for enrollment in enrollments:
        enrollment['certificate'] = all_results[enrollment['id']]
        row_values = util.format_enrollments_table(enrollment, True)
        table.add_row(*row_values)
    console.print(table)
    console.print('[dim][i]** means enrollment has existing pending changes')
    console.print()
    return enrollments


def retrieve_enrollment(cps: Enrollment, util: Utility, args) -> None:
    if not args.cn and not args.enrollment_id:
        msg = 'Common Name (--cn) or enrollment-id (--enrollment-id) is mandatory'
        sys.exit(logger.error(msg))

    # backward compatability
    enrollments = {}
    try:
        with open('setup/enrollments.json') as f:
            enrollments = json.load(f)
        backward = True
    except FileNotFoundError as err:
        logger.debug(err)
        backward = False

    result = {}
    result['found'] = False
    result['enrollmentId'] = 0000

    if backward:
        if args.cn and util.found_duplicate_cn(enrollments, args.cn):
            sys.exit(logger.warning('More than 1 enrollment found for same CN. Please use --enrollment-id as input'))
    else:
        enrollment_id = args.enrollment_id if args.enrollment_id else None
        if args.cn:
            cn_resp = cps.list_enrollment()
            if cn_resp.ok:
                enrollments = cn_resp.json()['enrollments']
                found = [enrl for enrl in enrollments if enrl['csr']['cn'] == args.cn or 'sans' in enrl and args.cn in enrl['csr']['sans']]

                if len(found) == 1:
                    enrollment_id = found[0]['location'].split('/')[-1]
                    lg.console_header(console, f'Found enrollment-id {enrollment_id}', emojis.gem)
                    console.print()

                elif len(found) > 1:
                    sys.exit(logger.warning('More than 1 enrollment found for same CN. Please use --enrollment-id as input'))

    if backward:
        found = [enrl for enrl in enrollments if enrl['cn'] == args.cn or 'sans' in enrl and args.cn in enrl['sans']]
        result['enrollmentId'] = found[0]['enrollmentId']
        result['cn'] = found[0]['cn']
        result['found'] = True

        enrollment_id = result['enrollmentId']
        resp = cps.get_enrollment(enrollment_id)
        if resp.ok:
            print_json(data=resp.json())
            util.write_json(lg, 'enrollments.json', resp.json())
        else:
            logger.error(resp.json()['detail'])
            logger.error('Enrollment not found. Please double check common name (CN) or enrollment-id.')

    if enrollment_id:
        print()
        logger.warning(f'Getting details for enrollment-id: {enrollment_id}')
        resp = cps.get_enrollment(enrollment_id)
        if not resp.ok:
            logger.error(resp.json())
            logger.error('Enrollment not found. Please double check common name (CN) or enrollment-id.')

        else:
            result = resp.json()
            lg.console_header(console, f'Found enrollment-id {enrollment_id}', emojis.gem)
            console.print()

            if not args.json and not args.yaml:
                print_json(data=result)
                exit(-1)

            if args.json:
                print_json(data=result)
                util.write_json(lg, f'enrollment_{enrollment_id}.json', result)

            if args.yaml:
                util.write_yaml(lg, f'enrollment_{enrollment_id}.yaml', result)


def update_enrollment(cps: Enrollment, util: Utility, args) -> None:
    enrollment_id = args.enrollment_id
    resp = cps.get_enrollment(enrollment_id)
    if not resp.ok:
        logger.error(f'Invalid API Response: {resp.status_code}. Unable to fetch Certificate details.')
        return -1
    else:
        result = resp.json()
        pending = len(result.get('pendingChanges', []))
        cn = result.get('csr', {}).get('cn', None)
        if pending > 0:
            logger.critical(f'You are about to update enrollment-id: {enrollment_id} and CN: {cn}')
            logger.info('Would you like to override? This will cancel the existing change and apply the new update.')
            logger.info('Press (Y/N) to continue')
            decision = input()

    if decision.upper() == 'Y':
        payload = util.load_json(filepath=args.file)
        resp_upd = cps.update_enrollment(args.enrollment_id, payload, renewal=args.force_renewal)
        if not resp_upd.ok:
            logger.error('Unable to update due to the below reason')
            logger.error(resp_upd.json())

        if resp_upd.status_code == 200:
            msg = 'Update successful. This change will trigger a new certificate deployment.'
            logger.info(msg)
            msg = 'Run \'status\' to get updated progress details.'
            logger.info(msg)

        if resp_upd.status_code == 202:
            msg = 'Update successful. This change does not require a new certificate deployment'
            msg = f'{msg} and will take effect on the next deployment.'
            logger.info(msg)
            msg = 'Run \'status\' to get updated progress details.'
            logger.info(msg)


def delete_enrollment(cps: Enrollment, args) -> None:
    enrollment_id, resp = cps.get_enrollment(args.enrollment_id)
    if not resp.ok:
        msg = f'Invalid API Response: {resp.status_code} Unable to fetch Certificate details.'
        print(msg)
        logger.error(msg)
        return -1
    else:
        result = resp.json()
        pending = len(result.get('pendingChanges', []))
        cn = result.get('csr', {}).get('cn', None)

        if pending > 0:
            if not args.cancel_pending:
                msg = 'There is an active change for this certificate.'
                msg = f'{msg} Please cancel the change before deleting this enrollment'
                print(msg)
                logger.critical(msg)
                return -1
            else:
                logger.critical('You have choose to cancels all pending changes when updating an enrollment\n')
                msg = f'You are about to delete the live certificate which may impact production traffic for cn: {cn}'
                msg = f'{msg} {cn} with enrollment-id: {enrollment_id}'
                print(msg)

        if pending == 0:
            if args.force:
                decision = 'Y'
            else:
                msg = 'You are about to delete the live certificate which may impact production traffic for cn:'
                msg = f'{msg} {cn} with enrollment-id: {enrollment_id}'
                print(msg)
                logger.critical(msg)
                print()
                print('Do you wish to continue? (Y/N)')
                decision = input().upper()

    if decision != 'Y':
        print('Exiting...')

        logger.info('Exiting...')
    else:
        # place holder to validate args.deploy_not_after, args.deploy_not_before
        deploy_not_after = ''
        deploy_not_before = ''

        resp_delete = cps.remove_enrollment(enrollment_id, deploy_not_after, deploy_not_before, args.cancel_pending)
        if not resp_delete.ok:
            print_json(data=resp_delete.json())
            logger.debug(resp_delete.url)
            logger.error(f'Invalid API Response ({resp_delete.status_code}) Deletion unsuccessful')
        else:
            logger.info('Deletion successfully Initiated')
            if resp_delete.status_code == 200:
                msg = f'Success: The enrollment with enrollment-id: {enrollment_id} was deleted immediately.'
                print(msg)
                logger.info(msg)

            if resp_delete.status_code == 202:
                msg = f'Accepted: Deletion for enrollment-id: {enrollment_id} was accepted and being processed. This may take some time.'
                print(msg)
                logger.info(msg)
                msg_wait = 'Please Wait. This may take some time.'
                print(msg_wait)
                logger.info(msg_wait)


def cancel_enrollment(cps: Enrollment, args) -> None:

    enrollment_id, resp = cps.get_enrollment(args.enrollment_id)

    if not resp.ok:
        logger.error(f'Invalid API Response: {resp.status_code}. Unable to fetch Certificate details.')
    else:
        result = resp.json()

        pending = len(result.get('pendingChanges', []))
        cn = result.get('csr', {}).get('cn', None)

        if pending == 0:
            logger.critical('There is NO active change for this certificate.')
        else:
            change_id = int(result['pendingChanges'][0]['location'].split('/')[-1])
            logger.info(f'{change_id}')
            change_status_response = cps.get_change_status(enrollment_id, change_id)
            if not change_status_response.ok:
                logger.critical('Unable to fetch changes related to Certificate.')
            else:
                print_json(data=change_status_response.json())
                pending_detail = change_status_response.json()
                if not ('pendingChanges' in pending_detail):
                    logger.info(f'Unable to determine change status for enrollment ID: {enrollment_id}')
                    return -1
                else:
                    pending_detail = pending_detail['statusInfo']['description']

                    msg = f'There is an active change for this certificate. Details: {pending_detail}\n'
                    logger.critical(msg)

                    msg = f'Cancelling the request with change ID: {change_id} for CN: {cn}\n'
                    logger.critical(msg)

                    logger.critical('Do you wish to continue? (Y/N)')
                    decision = input().upper()

    if decision != 'Y':
        logger.info('Exiting...')
    else:
        resp_cancel = cps.cancel_change(enrollment_id, change_id)
        if not resp_cancel.ok:
            print_json(data=resp_cancel.json())
            logger.debug(resp_cancel.url)
            logger.error(f'Invalid API Response ({resp_cancel.status_code})  Deletion unsuccessful')
        else:
            msg = f'Success: The change ID: {change_id} was deleted successfully.'
            logger.info(msg)


def deploy_enrollment(cps: Enrollment,  cps_change: Changes, util: Utility, args) -> None:
    enrollment_id = args.enrollment_id
    resp = cps.get_enrollment(enrollment_id)
    if resp.ok:
        result = resp.json()
        pending = result.get('pendingChanges', [])
        if len(pending) > 0:
            change_id = pending[0]['location'].split('/')[-1]
            cps_change.enrollment_id = enrollment_id
            status_resp = cps_change.get_change_status(change_id)
            if status_resp.ok:
                change_status = status_resp.json()['statusInfo']['status']

                allowedInputs = status_resp.json()['allowedInput']
                change_output = [(index, input) for index, input in enumerate(allowedInputs) if input['requiredToProceed'] is True][0]

                selected_index = change_output[0]
                cps_type = change_output[1]['type']
                payload = change_output[1]

                logger.warning(f'{selected_index} {cps_type} {change_status}')
                cps_change.enrollment_id = enrollment_id
                cps_change.url_endpoint = payload['info']
                info_change_resp = cps_change.get_change(cps_type)
                if info_change_resp.ok:
                    hash_value = info_change_resp.json()['validationResultHash']
                    cps_change.url_endpoint = payload['update']
                    update_change_resp = cps_change.update_change(cps_type, hash_value)
                    logger.warning(f'{update_change_resp} {update_change_resp.url}')


def create_output_file(lg: lg, args) -> str:
    if args.output_file:
        output_file = args.output_file
    else:
        Path('audit').mkdir(parents=True, exist_ok=True)
        timestamp = f'{datetime.datetime.now():%Y%m%d_%H%M%S}'
        ext = '.csv'
        if args.json:
            ext = '.json'
        if args.xlsx:
            ext = '.xlsx'
        output_file_name = f'CPSAudit_{timestamp}{ext}'
        output_file = Path(f'audit/{output_file_name}')

        print()
        msg = f"Preparing {ext.upper().lstrip('.')} output file"
        logger.critical(msg)
        if args.json:
            lg.console_header(console, msg, emojis.construction, font_color='blue')
        else:
            lg.console_header(console, msg, emojis.construction, font_color='green')
    return output_file


def extract_cert_detail(contract_id: str, enrl: dict) -> list:

    detail = []
    try:
        enrollment_id = enrl['id']
        try:
            slot = enrl.get('productionSlots', []).pop(0)
        except IndexError:
            slot = enrl.get('staggingSlots', 0)

    except TypeError:
        enrollment_id = 0
        logger.critical('enrollment-id fetch error')

    cn = enrl['csr']['cn']
    san = enrl['csr'].get('sans', [])

    total_san = len(san)
    cn = cn if total_san == 0 else f'{cn} [{total_san}]'
    san_str = ' '.join(f"'{hostname}'" for hostname in san)
    detail.extend([contract_id, enrollment_id, slot, cn, san_str])

    pending = enrl['pendingChanges']
    if len(pending) <= 0:
        status = 'ACTIVE'
    else:
        status = 'IN-PROGRESS'
    detail.extend([status])

    val_type = enrl['validationType']
    cert_type = enrl['certificateType']
    change_mgmt = 'Yes' if enrl['changeManagement'] else ' '
    detail.extend([val_type, cert_type, change_mgmt])

    sniOnly = 'Yes' if enrl['networkConfiguration']['sniOnly'] else ' '
    secureNetwork = enrl['networkConfiguration']['secureNetwork']
    preferredCiphers = enrl['networkConfiguration']['preferredCiphers']
    mustHaveCiphers = enrl['networkConfiguration']['mustHaveCiphers']
    tls = enrl['networkConfiguration']['disallowedTlsVersions']
    geo = enrl['networkConfiguration']['geography']
    country = enrl['csr'].get('c', ' ')
    state = enrl['csr'].get('st', ' ')
    org = f"'{enrl['org']['name']}'"
    ou = enrl['csr'].get('ou', ' ')

    detail.extend([sniOnly, secureNetwork, preferredCiphers,
                   mustHaveCiphers, tls,
                   geo, country, state,
                   org, ou])

    adminContact = enrl['adminContact']
    admin_fn = adminContact['firstName'].strip()
    admin_ln = adminContact['lastName'].strip()
    admin_em = adminContact['email']
    admin_ph = adminContact['phone']
    admin_dtl = f'{admin_fn} {admin_ln} | {admin_em} | {admin_ph}'
    techContact = enrl['techContact']
    tech_fn = techContact['firstName'].strip()
    tech_ln = techContact['lastName'].strip()
    tech_em = techContact['email']
    tech_ph = techContact['phone']
    tech_dtl = f'{tech_fn} {tech_ln} | {tech_em} | {tech_ph}'
    detail.extend([admin_dtl, tech_dtl])

    return detail


def build_csv_rows(args,
                   cps_change: Changes,
                   cps_deploy: Deployment,
                   data_json: dict) -> list:

    contract_id = data_json['contractId']
    try:
        enrls = data_json['enrollmentId']
    except KeyError:
        print_json(data=data_json)
    rows = []
    console_rows = []
    for i, enrl in enumerate(enrls, 1):
        detail = extract_cert_detail(contract_id, enrl)
        enrollment_id = detail[1]

        cps_deploy.enrollment_id = enrollment_id
        prod_resp = cps_deploy.get_production_deployment()
        expiry = ' '
        algorithm = ' '

        if prod_resp.ok:
            '''
            slot_id = detail[2]
            if slot_id in [5009, 7389]:
                print_json(data=prod_resp.json())
                breakpoint()
            '''

            algorithm = prod_resp.json()['primaryCertificate']['keyAlgorithm']
            multi = prod_resp.json()['multiStackedCertificates']
            if len(multi) > 0:
                algorithm = multi[0]['keyAlgorithm']
                logger.debug(f'{enrollment_id} {algorithm}')

            expiry = prod_resp.json()['primaryCertificate']['expiry']
        logger.debug(f'{enrollment_id:<10} {algorithm:<5} {expiry}')

        detail.insert(6, expiry)
        detail.insert(6, algorithm)
        status = detail[4]

        pending = enrl['pendingChanges']
        pending_detail = ' '
        order_id = ' '

        if status == 'IN-PROGRESS':
            if args.include_change_details:
                change_id = pending[0]['location'].split('/')[-1]
                cps_change.enrollment_id = enrollment_id
                change_resp = cps_change.get_change_status(change_id)
                if not change_resp.ok:
                    msg = f'Unable to determine change status for enrollment {enrollment_id} '
                    msg = f'{msg} with change Id {change_id}'
                    logger.warning(msg)
                    pending_detail = 'unknown change change status'
                else:
                    cn = detail[2]
                    val_type = detail[6]
                    if val_type in ['ov', 'ev']:
                        logger.debug(f'{cn} {val_type}')
                        pending_detail = change_resp.json().get('statusInfo').get('description', '')
                        history_resp = cps_change.get_change_history()
                        if history_resp.ok:
                            changes = history_resp.json()['changes']
                            for i, ch in enumerate(changes, 1):
                                ch_dtl = f"{ch['actionDescription']} - {ch['status']}"
                                order_id = 0
                                if ch['status'] == 'incomplete':
                                    cert = ch.get('primaryCertificateOrderDetails', 0)
                                    try:
                                        order_id = cert.get('orderId', 0)
                                        logger.debug(f'{ch_dtl} OrderId: {order_id}')
                                        break
                                    except Exception:
                                        print_json(data=cert)

        detail.extend([pending_detail, order_id])
        logger.info(detail[:4])
        rows.append(detail)
        console_data = detail[:4] + detail[5:10] + [detail[-1]]
        console_rows.append(console_data)

    return (rows, console_rows)


async def build_csv_rows_async(executor, args, cps_change, cps_deploy, account_enrollments):

    futures = [run_in_executor(executor, build_csv_rows, args, cps_change, cps_deploy, id) for id in account_enrollments]
    certs = await asyncio.gather(*futures)
    # return await asyncio.to_thread(build_csv_rows, args, cps_change, cps_deploy, enrl_in_contract)
    return certs


async def combined(args, account_enrollments, cps_change, cps_deploy) -> list:
    rows = []
    console_rows = []
    print()
    logger.critical('START ... ')

    with ThreadPoolExecutor(max_workers=int(args.concurrency)) as executor:
        tasks = [
            build_csv_rows_async(executor, args, cps_change, cps_deploy, account_enrollments)

        ]
        results = await asyncio.gather(*tasks)

    for result in results:
        for xlsx, console_output in result:
            rows.extend(xlsx)
            console_rows.extend(console_output)

    logger.critical('COMPLETE ...')
    headers = ['contractId', 'enrollment_id', 'slot', 'CN', 'SAN(S)', 'status',
               'keyAlgorithm', 'Expiry', 'Validation', 'Type', 'Test on Staging', 'SNI Only',
               'Secure Network', 'preferredCiphers', 'mustHaveCiphers', 'disallowedTlsVersions',
               'Geography', 'Country', 'State',
               'Organization', 'Organization Unit',
               'Admin Contact', 'Tech Contact']
    console_headers = ['contractId', 'enrollment_id', 'slot', 'CN SAN(S)', 'status', 'keyAlgorithm', 'Expiry', 'Validation', 'Type',
                       'Test on Staging', 'SNI Only']

    if args.include_change_details:
        change_detail_headers = ['Change Status Details', 'OrderId']
        headers.extend(change_detail_headers)
        console_headers.append('OrderId')

    csv_data = {'headers': headers, 'output': rows}
    console_data = {'headers': console_headers, 'output': console_rows}
    result = [csv_data, console_data]

    return result


def combined_x(args, account_enrollments, cps_change, cps_deploy) -> list:
    rows = []
    console_rows = []
    for enrl_in_contract in account_enrollments:
        output, console_output = build_csv_rows(args,
                                                cps_change, cps_deploy,
                                                enrl_in_contract)
        rows.extend(output)
        console_rows.extend(console_output)

    shared_headers = ['contractId', 'enrollment_id', 'slot', 'CN', 'SAN(S)', 'status',
                      'keyAlgorithm', 'Expiry', 'Validation', 'Type', 'Test on Staging', 'SNI Only']
    console_headers = shared_headers
    csv_headers = shared_headers.extend(['Secure Network', 'preferredCiphers', 'mustHaveCiphers', 'disallowedTlsVersions',
                                         'Geography', 'Country', 'State',
                                         'Organization', 'Organization Unit',
                                         'Admin Contact', 'Tech Contact'])

    if args.include_change_details:
        change_detail_headers = ['Change Status Details', 'OrderId']
        csv_headers.extend(change_detail_headers)
        console_headers.append('OrderId')

    csv_data = {'headers': csv_headers, 'output': rows}
    console_data = {'headers': console_headers, 'output': console_rows}
    result = [csv_data, console_data]
    return result


def build_output_xlsx(util: Utility, output_file: str, headers: list, data_rows: list):
    temp_csv = str(output_file).replace('.xlsx', '.csv')
    with open(temp_csv, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(headers)
        csvwriter.writerows(data_rows)

    workbook = Workbook(output_file,  {'constant_memory': True})
    worksheet = workbook.add_worksheet('Certificate')

    with open(temp_csv, encoding='utf8') as f:
        reader = csv.reader(f)
        for r, row in enumerate(reader):
            for c, col in enumerate(row):
                worksheet.write(r, c, col)
    workbook.close()
    util.open_excel_application(filepath=output_file)

    file_path = Path(temp_csv)
    if file_path.exists():
        file_path.unlink()


def collect_certs_with_contract(cps: Enrollment, contracts: list) -> tuple[list, int]:
    account_enrollments = []
    enrl_count = 0
    logger.debug(contracts)

    for contract_id in contracts:
        enrl_resp = cps.list_enrollment(contract_id)
        enrl_resp.url
        if not enrl_resp.ok:
            logger.debug(f'{contract_id:<10} no    enrollments')
        else:
            enrollments = enrl_resp.json()['enrollments']
            ids = [enrl['id'] for enrl in enrollments]
            if len(ids) == 0:
                logger.debug(f'{contract_id:<10} no    enrollments')
            else:
                enrl_count = enrl_count + len(ids)
                account_enrollments.append({'contractId': contract_id,
                                            'enrollmentId': ids})
                logger.debug(f'{contract_id:<10} {len(ids):<5} enrollments')
    return account_enrollments, enrl_count


def initial_processing(lg, args, cps, util,
                       account_enrollments: list,
                       batch_size: int):
    all_enrollments = []
    t0 = perf_counter()
    print()
    msg = 'Collecting enrollment detail'
    logger.critical(msg)
    lg.console_header(console, msg, emojis.bow, font_color='medium_violet_red')

    for account in account_enrollments:
        contract = account['contractId']
        ids = account['enrollmentId']
        msg_stat = f'{contract:<10}: {len(ids):>5}'
        msg = f'contract {msg_stat} enrollments'
        logger.warning(msg)
        # lg.console_header(console, msg, emojis.heavy_check_mark, font_color='pink3')

        enrollments = asyncio.run(util_async.multiple_chunks(args, cps, util, batch_size, contract, ids))
        all_enrollments.append(enrollments)
    ttp = 'Total requests time (1st)'
    t1 = perf_counter()
    elapse_time = str(strftime('%H:%M:%S', gmtime(t1 - t0)))
    logger.debug(f'{ttp} {elapse_time}')
    return all_enrollments


def retry_processing(lg, args, cps, util,
                     account_enrollments: list,
                     batch_size: int):
    all_enrollments = []
    t0 = perf_counter()
    print()

    for account in account_enrollments:
        contract = account['contractId']
        ids = account['error']
        msg_stat = f'{contract:<10}: {len(ids):>5}'
        if len(ids) > 0:
            msg = f'RETRY      enrollment detail for contract {msg_stat} enrollments'
            logger.critical(msg)
            lg.console_header(console, msg, emojis.retry, font_color='yellow')
            enrollments = asyncio.run(util_async.multiple_chunks(args, cps, util, batch_size, contract, ids))
            all_enrollments.append(enrollments)

    if len(all_enrollments) > 0:
        ttp = 'Total requests time RETRY'
        t1 = perf_counter()
        elapse_time = str(strftime('%H:%M:%S', gmtime(t1 - t0)))
        logger.critical(f'{ttp} {elapse_time}')
        return all_enrollments


def combined_result(all_enrollments, retry: bool | None = False) -> list:

    new_enrollments = []

    for results in all_enrollments:
        enrollments_by_contract = defaultdict(lambda: {'enrollmentId': [], 'error': []})

        for result in results:
            contract = result['contractId']
            enrollments_by_contract[contract]['enrollmentId'].extend(result['enrollmentId'])
            if not retry:
                if result['error']:
                    enrollments_by_contract[contract]['error'].extend(result['error'])

        for contract, enrollment_info in enrollments_by_contract.items():
            new_enrollments.append({
                'contractId': contract,
                'enrollmentId': enrollment_info['enrollmentId'],
                'error': enrollment_info['error']
            })
    return new_enrollments


def audit(args, util: Utility,
          cps: Enrollment,
          cps_change: Changes,
          cps_deploy: Deployment) -> None:
    """
    To view orderId
    https://tools.gss.akamai.com/monitor/certs/DigiCert/index.pl?type=orderid
    """

    if args.contract:
        contracts = args.contract
    else:
        contract_resp = cps.get_contract()
        if not contract_resp.ok:
            logger.error(contract_resp.json()['detail'])
        else:
            contracts = contract_resp.json()

    account_enrollments, enrl_count = collect_certs_with_contract(cps, contracts)
    lg.console_header(console, f'{enrl_count} enrollments found', emojis.gem, font_color='blue', font_style='bold')
    logger.critical(f'{enrl_count} enrollments found')

    if enrl_count == 0:
        exit(-1)

    first_audit = initial_processing(lg, args, cps, util, account_enrollments, batch_size=20)

    new_enrollments = combined_result(first_audit)

    if len(new_enrollments) == 0:
        logger.info('found nothing')
        exit(-1)

    retry_enrollments = retry_processing(lg, args, cps, util, new_enrollments, batch_size=10)

    if retry_enrollments:
        second_audit = combined_result(retry_enrollments, retry=True)
        # util.write_json(filepath='logs/1st_audit.json', json_object={'results': new_enrollments})
        new_enrollments.extend(second_audit)
        # util.write_json(filepath='logs/2nd_audit.json', json_object={'results': new_enrollments})
        # util.write_json(filepath='logs/retry_audit.json', json_object={'results': second_audit})

    output_file = create_output_file(lg, args)
    if args.json:
        print()
        util.write_json(filepath=output_file, json_object={'results': new_enrollments})

    if args.xlsx or args.tbl:
        result = asyncio.run(combined(args, new_enrollments, cps_change, cps_deploy))
        r = list(result)

    if not args.xlsx:
        print()
        with open(output_file, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(r[0]['headers'])
            csvwriter.writerows(r[0]['output'])
    else:
        build_output_xlsx(util, output_file, r[0]['headers'], r[0]['output'])

    msg = f'Done! Output file written here: {output_file}'
    lg.console_header(console, msg, emojis.tada, sandwiches=True)
    logger.critical(msg)

    if len(r[1]['output']) > 0 and args.tbl:
        print(tabulate(r[1]['output'], headers=r[1]['headers'], tablefmt='psql', numalign='center'))


if __name__ == '__main__':
    pass
