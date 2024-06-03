from __future__ import annotations

import csv
import datetime
import json
import sys
from pathlib import Path

import yaml
from akamai_apis.cps import Enrollment
from rich import print_json
from rich.console import Console
from rich.table import Table
from utils import cli_logging as lg
from utils import emojis
from utils import utility as util
from xlsxwriter.workbook import Workbook


console = Console(stderr=True)


def list_enrollment(cps: Enrollment, args, logger) -> None:
    enrollments = []
    resp = cps.list_enrollment(args.contract)
    if not resp.ok:
        logger.error(resp.text)
        exit(1)
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

    for enrollment in enrollments:
        (enrollment_id, common_name, certificate_type,
         in_progress, change_management, slot, sni) = util.format_enrollments_table(logger, enrollment)
        table.add_row(str(enrollment_id), common_name, certificate_type, in_progress, change_management, str(slot), sni)
    console.print(table)
    console.print('[dim][i]** means enrollment has existing pending changes')

    console.print()
    return enrollments


def retrieve_enrollment(cps: Enrollment, args, logger) -> None:
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
            enrollments = list_enrollment(cps, args, logger)
            found = [enrl for enrl in enrollments if enrl['csr']['cn'] == args.cn or 'sans' in enrl and args.cn in enrl['csr']['sans']]

            if len(found) == 1:
                enrollment_id = found[0]['location'].split('/')[-1]
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
            util.write_json(logger, 'enrollments.json', resp.json())
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
            if args.json:
                print_json(data=result)
                util.write_json(logger, f'enrollment_{enrollment_id}.json', result)

            if args.yaml:
                yaml_file = f'enrollment_{enrollment_id}.yaml'
                with open(yaml_file, 'w') as f:
                    yaml.dump(result, f, default_flow_style=False, indent=4)

                print()
                with open(yaml_file) as f:
                    print(f.read())

            if not args.json and not args.yaml:
                print_json(data=result)


def update_enrollment(cps: Enrollment, args, logger) -> None:
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


def create_output_file(args) -> str:
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
    return output_file


def build_csv_rows(logger, data_json: dict) -> list:
    contract_id = data_json['contractId']
    try:
        enrls = data_json['enrollmentId']
    except KeyError:
        print_json(data=data_json)
    rows = []

    for i, enrl in enumerate(enrls, 1):
        enrollment_id = enrl['id']
        cn = enrl['csr']['cn']
        """
        san = enrl['csr'].get('sans', [])

        adminContact = enrl['adminContact']
        admin_fn = adminContact['firstName'].strip()
        admin_ln = adminContact['lastName'].strip()
        admin_em = adminContact['email']
        admin_ph = adminContact['phone']
        admin = f'{admin_fn} {admin_ln} | {admin_em} | {admin_ph}'


        techContact = enrl['techContact']
        tech_fn =  techContact['firstName'].strip()
        tech_ln = techContact['lastName'].strip()
        tech_em = techContact['email']
        tech_ph = techContact['phone']
        tech_dtl = f'{tech_fn} {tech_ln} | {tech_em} | {tech_ph}'

        cert_type = enrl['certificateType']
        val_type = enrl['validationType']
        org = enrl['org']['name']
        sniOnly = enrl['networkConfiguration']['sniOnly']
        secureNetwork = enrl['networkConfiguration']['secureNetwork']
        tls = enrl['networkConfiguration']['disallowedTlsVersions']
        mustHaveCiphers = enrl['networkConfiguration']['mustHaveCiphers']
        preferredCiphers = enrl['networkConfiguration']['preferredCiphers']
        """
        rows.append([contract_id, enrollment_id, cn])

    return rows


async def audit(cps: Enrollment, args, logger) -> None:
    output_file = create_output_file(args)
    contracts = cps.get_contract().json()
    all_enrl = []
    account_enrollments = []
    for contract_id in contracts:
        enrl_resp = cps.list_enrollment(contract_id)
        if not enrl_resp.ok:
            logger.info(f'{contract_id:<10} no    enrollments')
        else:
            enrollments = enrl_resp.json()['enrollments']
            ids = [enrl['id'] for enrl in enrollments]
            if len(ids) == 0:
                logger.info(f'{contract_id:<10} no    enrollments')
            else:
                logger.warning(f'{contract_id:<10} {len(ids):<5} enrollments')
                all_enrl = await cps.fetch_all(ids, int(args.concurrency))
                account_enrollments.append({'contractId': contract_id,
                                            'enrollmentId': all_enrl})

    if args.json:
        util.write_json(logger, filepath=output_file, json_object={'results': account_enrollments})
        exit(-1)

    csv_rows = []
    for contract in account_enrollments:
        csv_rows.extend(build_csv_rows(logger, contract))

    if not args.xlsx:
        with open(output_file, 'w', newline='') as csvfile:
            headers = ['contractId', 'enrollment_id', 'cn']
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(headers)
            csvwriter.writerows(csv_rows)
    else:
        temp_csv = str(output_file).replace('.xlsx', '.csv')
        logger.critical(temp_csv)
        logger.critical(output_file)
        with open(temp_csv, 'w', newline='') as csvfile:
            headers = ['contractId', 'enrollment_id', 'cn']
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(headers)
            csvwriter.writerows(csv_rows)

        workbook = Workbook(output_file,  {'constant_memory': True})
        worksheet = workbook.add_worksheet('Certificate')

        with open(temp_csv, encoding='utf8') as f:
            reader = csv.reader(f)
            for r, row in enumerate(reader):
                for c, col in enumerate(row):
                    worksheet.write(r, c, col)
        workbook.close()

        file_path = Path(temp_csv)
        if file_path.exists():
            file_path.unlink()

    logger.critical(f'Done! Output file written here: {output_file}')

if __name__ == '__main__':
    pass
