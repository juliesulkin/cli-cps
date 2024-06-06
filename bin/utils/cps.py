from __future__ import annotations

import asyncio
import csv
import datetime
import json
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
from utils.utility import Utility
from xlsxwriter.workbook import Workbook


console = Console(stderr=True)


def list_enrollment(cps: Enrollment, cps_deploy: Deployment,
                    util, args, logger) -> None:
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
            future = executor.submit(util.get_deployment_wrapper, logger, chunk, cps_deploy)
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
        row_values = util.format_enrollments_table(logger, enrollment, True)
        table.add_row(*row_values)
    console.print(table)
    console.print('[dim][i]** means enrollment has existing pending changes')
    console.print()
    return enrollments


def retrieve_enrollment(cps: Enrollment, util: Utility, args, logger) -> None:
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
        if args.cn and util.found_duplicate_cn(logger, enrollments, args.cn):
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


def update_enrollment(cps: Enrollment, util: Utility, args, logger) -> None:
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
        payload = util.load_json(logger, filepath=args.file)
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


def delete_enrollment(cps: Enrollment, args, logger) -> None:
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
            msg = 'There is an active change for this certificate. Please cancel the change before deleting this enrollment'
            logger.critical(msg)
            return -1

        if pending == 0:
            if args.force:
                decision = 'Y'
            else:
                msg = 'You are about to delete the live certificate which may impact production traffic for cn:'
                msg = f'{msg} {cn} with enrollment-id: {enrollment_id}'
                logger.critical(msg)
                print()
                logger.info('Do you wish to continue? (Y/N)')
                decision = input().upper()

    if decision != 'Y':
        logger.info('Exiting...')
    else:
        resp_delete = cps.delete_enrollment(enrollment_id)
        if not resp_delete.ok:
            print_json(data=resp_delete.json())
            logger.info(resp_delete.url)
            logger.error(f'Invalid API Response ({resp_delete.status_code}) Deletion unsuccessful')
        else:
            logger.info('Deletion successful')


def deploy_enrollment(cps: Enrollment,  cps_change: Changes, util: Utility, args, logger) -> None:
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


def create_output_file(logger, lg: lg, args) -> str:
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

        msg = 'Preparing output file'
        logger.critical(msg)
        if args.json:
            lg.console_header(console, msg, emojis.construction, font_color='blue')
        else:
            lg.console_header(console, msg, emojis.construction, font_color='green')
    return output_file


def extract_cert_detail(logger, contract_id: str, enrl: dict) -> list:

    detail = []
    try:
        enrollment_id = enrl['id']
    except TypeError:
        enrollment_id = 0
        logger.critical('enrollment-id fetch error')

    cn = enrl['csr']['cn']
    san = enrl['csr'].get('sans', [])

    total_san = len(san)
    cn = cn if total_san == 0 else f'{cn} [{total_san}]'
    san_str = ' '.join(f"'{hostname}'" for hostname in san)
    detail.extend([contract_id, enrollment_id, cn, san_str])

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


def build_csv_rows(logger, args,
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
        detail = extract_cert_detail(logger, contract_id, enrl)
        enrollment_id = detail[1]

        cps_deploy.enrollment_id = enrollment_id
        prod_resp = cps_deploy.get_production_deployment()
        expiry = ' '
        if prod_resp.ok:
            expiry = prod_resp.json()['primaryCertificate']['expiry']
        detail.insert(5, expiry)
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
        rows.append(detail)
        console_data = detail[:3] + detail[4:10] + [detail[-1]]
        console_rows.append(console_data)

    return (rows, console_rows)


def combined(logger, args, account_enrollments, cps_change, cps_deploy) -> list:
    rows = []
    console_rows = []
    for enrl_in_contract in account_enrollments:
        output, console_output = build_csv_rows(logger, args,
                                                cps_change, cps_deploy,
                                                enrl_in_contract)
        rows.extend(output)
        console_rows.extend(console_output)

    headers = ['contractId', 'enrollment_id', 'CN', 'SAN(S)',
               'status', 'Expiry', 'Validation', 'Type', 'Test on Staging', 'SNI Only',
               'Secure Network', 'preferredCiphers', 'mustHaveCiphers', 'disallowedTlsVersions',
               'Geography', 'Country', 'State',
               'Organization', 'Organization Unit',
               'Admin Contact', 'Tech Contact']
    console_headers = ['contractId', 'enrollment_id', 'CN SAN(S)', 'status', 'Expiry', 'Validation', 'Type',
                       'Test on Staging', 'SNI Only']

    if args.include_change_details:
        change_detail_headers = ['Change Status Details', 'OrderId']
        headers.extend(change_detail_headers)
        console_headers.append('OrderId')

    csv_data = {'headers': headers, 'output': rows}
    console_data = {'headers': console_headers, 'output': console_rows}
    result = [csv_data, console_data]
    return result


def build_output_xlsx(logger, util: Utility, output_file: str, headers: list, data_rows: list):
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


def collect_certs_with_contract(logger, cps: Enrollment, contracts: list) -> tuple[list, int]:
    account_enrollments = []
    enrl_count = 0
    for contract_id in contracts:
        enrl_resp = cps.list_enrollment(contract_id)
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


def initial_processing(logger, lg, args, cps, util,
                       account_enrollments: list,
                       batch_size: int):
    all_enrollments = []
    t0 = perf_counter()

    for account in account_enrollments:
        contract = account['contractId']
        ids = account['enrollmentId']
        msg_stat = f'{contract:<10}: {len(ids):>5}'
        msg = f'Collecting enrollment detail for contract {msg_stat} enrollments'
        logger.warning(msg)
        lg.console_header(console, msg, emojis.bow, font_color='yellow')
        print()

        enrollments = asyncio.run(util_async.multiple_chunks(logger, args, cps, util, batch_size, contract, ids))
        all_enrollments.append(enrollments)
    ttp = 'Total requests time (1st)'
    t1 = perf_counter()
    elapse_time = str(strftime('%H:%M:%S', gmtime(t1 - t0)))
    logger.critical(f'{ttp} {elapse_time}')
    return all_enrollments


def retry_processing(logger, lg, args, cps, util,
                     account_enrollments: list,
                     batch_size: int):
    all_enrollments = []
    t0 = perf_counter()

    for account in account_enrollments:
        contract = account['contractId']
        ids = account['error']
        msg_stat = f'{contract:<10}: {len(ids):>5}'
        if len(ids) > 0:
            msg = f'RETRY      enrollment detail for contract {msg_stat} enrollments'
            logger.warning(msg)
            lg.console_header(console, msg, emojis.blush, font_color='yellow')
            enrollments = asyncio.run(util_async.multiple_chunks(logger, args, cps, util, batch_size, contract, ids))
            all_enrollments.append(enrollments)

    if len(all_enrollments) > 0:
        ttp = 'Total requests time RETRY'
        t1 = perf_counter()
        elapse_time = str(strftime('%H:%M:%S', gmtime(t1 - t0)))
        logger.critical(f'{ttp} {elapse_time}')
        return all_enrollments


def combined_result(logger, all_enrollments, retry: bool | None = False) -> list:

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


def audit(args, logger, util: Utility,
          cps: Enrollment,
          cps_change: Changes,
          cps_deploy: Deployment) -> None:

    """
    To view orderId
    https://tools.gss.akamai.com/monitor/certs/DigiCert/index.pl?type=orderid
    """
    contracts = args.contract if args.contract else cps.get_contract().json()
    account_enrollments, enrl_count = collect_certs_with_contract(logger, cps, contracts)

    lg.console_header(console, f'{enrl_count} enrollments found', emojis.gem, font_color='blue', font_style='bold')
    logger.critical(f'{enrl_count} enrollments found')

    good_enrollments = initial_processing(logger, lg, args, cps, util, account_enrollments, batch_size=20)

    new_enrollments = combined_result(logger, good_enrollments)

    retry_enrollments = retry_processing(logger, lg, args, cps, util, new_enrollments, batch_size=10)

    if retry_enrollments:
        fixed_enrollments = combined_result(logger, retry_enrollments, retry=True)
        util.write_json(lg, console, filepath='3.json', json_object={'results': fixed_enrollments})

    output_file = create_output_file(logger, lg, args)
    if args.json:
        print()
        util.write_json(lg, console, filepath=output_file, json_object={'results': new_enrollments})
        msg = f'Done! Output file written here: {output_file}'
        lg.console_header(console, msg, emojis.tada, sandwiches=True)
        logger.critical(msg)

        return 1

    result = combined(logger, args, new_enrollments, cps_change, cps_deploy)
    if not args.xlsx:
        with open(output_file, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(result[0]['headers'])
            csvwriter.writerows(result[0]['output'])
    else:
        build_output_xlsx(logger, util, output_file, result[0]['headers'], result[0]['output'])

    print(tabulate(result[1]['output'], headers=result[1]['headers'], tablefmt='psql'))
    msg = f'Done! Output file written here: {output_file}'
    lg.console_header(console, msg, emojis.tada, sandwiches=True)
    logger.critical(msg)


if __name__ == '__main__':
    pass
