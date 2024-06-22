from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from akamai_apis.cps import Enrollment
from rich.console import Console
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import TaskProgressColumn
from rich.progress import TextColumn
from utils.utility import Utility


console = Console(stderr=True)
logger = logging.getLogger(__name__)


async def run_in_executor(executor, async_function, cps, id):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(executor, async_function, id)
    return response


async def process_chunk(executor, contract: str, count_contract: int,
                        cps: Enrollment, batch_size: int, batch_no: int, ids: list):
    tmp_enrl = []
    error_ids = []
    to_be_processed = len(ids)

    # fetch enrollment ID doesn't need contractId
    if 'contractId' in cps._params:
        del cps._params['contractId']

    futures = [run_in_executor(executor, cps.get_enrollment, cps, id) for id in ids]
    enrl_responses = await asyncio.gather(*futures)

    progress_bar = Progress(TextColumn('{task.description}'),
                            BarColumn(bar_width=30, complete_style='medium_purple4', finished_style='grey53'),
                            TaskProgressColumn(show_speed=True, text_format='[green]{task.percentage:.1f}%'),
                            )

    with progress_bar as p:
        to_be_processed = len(ids)
        processed = len(enrl_responses)
        msg = f'     batch {batch_no:>3}: contract {contract:<10} {processed:>4} requests'

        task = p.add_task(f'[pink3]{msg}', processed)

        for ii, (resp, enrl_id) in enumerate(enrl_responses, 1):
            if resp is None or not resp.ok:
                logger.error(f'batch {batch_no:>3} {resp} Enrollment ID: {enrl_id}')
                error_ids.append(enrl_id)
                processed -= 1
                msg = f'     batch {batch_no:>3}: contract {contract:<10} {processed:>4} requests'
                continue

            if resp.ok:
                tmp_enrl.append(resp.json())

            percent = processed/to_be_processed * 100
            p.update(task, advance=percent, description=f'[pink3]{msg}')
            time.sleep(1)

        if to_be_processed > processed:
            error_msg = f'enrollment-id errors: [bold white on red]{error_ids}[/]'
            console.print(f'    [white]{error_msg} [white]', highlight=False)

    return {'contractId': contract,
            'batch': batch_no,
            'enrollmentId': tmp_enrl,
            'error': error_ids}


async def multiple_chunks(args,
                          cps: Enrollment,
                          util: Utility,
                          batch_size: int,
                          contract: str,
                          ids: list):
    count_cert = len(ids)
    chucks = list(util.split_into_chunks(ids, size=batch_size))
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        tasks = [process_chunk(executor, contract, count_cert,
                               cps, batch_size, batch_no, chunk)
                 for batch_no, chunk in enumerate(chucks, 1)]
        results = await asyncio.gather(*tasks)
    return results
