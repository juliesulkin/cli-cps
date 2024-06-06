from __future__ import annotations

import json
import logging
import os
import shutil
import time
from logging.config import dictConfig
from pathlib import Path
from time import gmtime
from time import perf_counter
from time import strftime

from rich import print
from rich.console import Console
from rich.panel import Panel
from utils import emojis
# import coloredlogs

custom_level_styles = {
    'debug': {'color': 'black'},
    'info': {'color': 'white'},
    'warning': {'color': 'yellow'},
    'error': {'color': 'red'},
    'critical': {'color': 'magenta'},
}


def setup_logger(args):
    """
    Create folders and copy config json when running via Akamai CLI
    """
    Path('logs').mkdir(parents=True, exist_ok=True)
    Path('config').mkdir(parents=True, exist_ok=True)
    origin_config = load_local_config_file(config_file='logging.json')

    with open(origin_config) as f:
        log_cfg = json.load(f)
    log_cfg['formatters']['long']['()'] = 'utils.cli.CLIFormatter'

    dictConfig(log_cfg)
    logging.Formatter.converter = time.gmtime
    logger = logging.getLogger()

    log_level = logging.getLevelName(args.log_level.upper())

    logger.setLevel(log_level)
    logger.info(f'{args.log_level.upper()} level: {log_level}')

    # Set up colored console logs using coloredlogs library
    '''
    coloredlogs.install(
        logger=logger,
        level=args.log_level.upper(),
        level_styles=custom_level_styles,
        fmt='%(levelname)-8s: %(message)s',
        field_styles={
            'asctime': {'color': 'black'},
            'levelname': {'color': 'black', 'bold': True},
        },
    )
    '''

    return logger


def load_local_config_file(config_file: str) -> str:
    docker_path = os.path.expanduser(Path('/cli'))
    local_home_path = os.path.expanduser(Path('~/.akamai-cli/src/cli-cps'))

    if Path(docker_path).exists():
        origin_config = f'{docker_path}/.akamai-cli/src/cli-cps/bin/config/{config_file}'
    elif Path(local_home_path).exists():
        origin_config = f'{local_home_path}/bin/config/{config_file}'
        origin_config = os.path.expanduser(origin_config)
    else:
        origin_config = f'{os.getcwd()}/bin/config/{config_file}'

    try:
        shutil.copy2(origin_config, f'config/{config_file}')
    except FileNotFoundError:
        origin_config = f'{os.getcwd()}/bin/config/{config_file}'
        shutil.copy2(origin_config, f'config/{config_file}')

    return origin_config


def console_panel(console: Console, header: str, title: str,
                  align: str | None = 'left',
                  color: str | None = 'white',
                  emoji_name: emojis | None = emojis.star):
    print()
    console.print(Panel(header,
                        width=150,
                        title_align=align,
                        title=f'{emoji_name}[bold {color}]  {title}  [/bold {color}]{emoji_name}'))


def console_header(console: Console, msg: str, emoji_name: emojis, sandwiches: bool | None = False,
                   font_color: str | None = 'white',
                   font_style: str | None = None):
    print()
    if sandwiches:
        if font_style:
            console.print(f'{emoji_name}[{font_style} {font_color}] {msg} [/{font_style} {font_color}]{emoji_name}', highlight=False)
        else:
            console.print(f'{emoji_name}[{font_color}] {msg} [{font_color}]{emoji_name}', highlight=False)

    else:
        if font_style:
            console.print(f'{emoji_name}[{font_style} {font_color}] {msg} [/{font_style} {font_color}]', highlight=False)
        else:
            console.print(f'{emoji_name}[{font_color}] {msg} [{font_color}]', highlight=False)


def console_complete(console: Console):
    print('\n\n')
    console.print(Panel.fit(emojis.all_done,
                            title=f'{emojis.tada * 35}',
                            title_align='center',
                            subtitle=f'{emojis.tada * 35}',
                            ))
    print()


def log_cli_timing(start_time) -> None:
    print()
    end_time = perf_counter()
    elapse_time = str(strftime('%H:%M:%S', gmtime(end_time - start_time)))
    msg = f'End Akamai CPS CLI, TOTAL DURATION: {elapse_time}'
    return msg
