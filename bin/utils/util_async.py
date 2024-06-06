from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from time import gmtime
from time import perf_counter
from time import strftime

from akamai_apis.cps import Enrollment
from rich.console import Console
from utils.utility import Utility


console = Console(stderr=True)

logger = logging.getLogger(__name__)


async def run_in_executor(executor, async_function, cps, id):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(executor, async_function, id)
    return response


async def process_chunk(executor, logger, contract: str, count_contract: int,
                        cps: Enrollment, batch_size: int, batch_no: int, ids: list):
    error = 0
    tmp_enrl = []
    error_ids = []
    t0 = perf_counter()

    log_t0 = strftime('%I:%M:%S %p', gmtime(time()))
    to_be_processed = len(ids)
    if batch_size < count_contract:
        msg = f'batch {batch_no:>3}: {to_be_processed:>4} requests, started    {log_t0} '
        console.print(f'[dim]    {msg}', highlight=False)
        logger.info(msg)

    if 'contractId' in cps._params:
        del cps._params['contractId']

    futures = [run_in_executor(executor, cps.get_enrollment, cps, id) for id in ids]
    responses = await asyncio.gather(*futures)

    for response in responses:
        if isinstance(response, tuple):
            error_enrollment_id = response[1]
            error += 1
            error_ids.append(error_enrollment_id)
        elif not response.ok:
            logger.error(response)
        else:
            tmp_enrl.append(response.json())

    t1 = perf_counter()
    processed = len(ids) - error
    log_t1 = strftime('%I:%M:%S %p', gmtime(time()))
    msg = f'batch {batch_no:>3}: {processed:>4} requests, [dim]completed  {log_t1}[/dim]'
    elapse_time = str(strftime('%H:%M:%S', gmtime(t1 - t0)))
    ttp = 'total requested time'
    msg = f'{msg} {ttp} [bold green on blue]{elapse_time}[/]'

    if to_be_processed > processed:
        error_msg = f'{msg}  enrollment-id errors: [bold white on red]{error_ids}[/]'
        console.print(f'    [magenta]{error_msg} [magenta]', highlight=False)
        logger.critical(error_msg)
    else:
        if batch_size < count_contract:
            console.print(f'    [white]{msg} [white]', highlight=False)
            logger.info(msg)

    return {'contractId': contract,
            'batch': batch_no,
            'enrollmentId': tmp_enrl,
            'error': error_ids}


async def multiple_chunks(logger, args,
                          cps: Enrollment,
                          util: Utility,
                          batch_size: int,
                          contract: str,
                          ids: list):
    count_contract = len(ids)
    chucks = list(util.split_into_chunks(ids, size=batch_size))
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        tasks = [process_chunk(executor, logger, contract, count_contract,
                               cps, batch_size, batch_no, chunk)
                 for batch_no, chunk in enumerate(chucks, 1)]
        results = await asyncio.gather(*tasks)
    return results
