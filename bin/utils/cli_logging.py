from __future__ import annotations

import json
import logging
import os
import shutil
import time
from logging.config import dictConfig
from pathlib import Path

import coloredlogs

custom_level_styles = {
    'debug': {'color': 'cyan'},
    'info': {'color': 'white'},
    'warning': {'color': 'yellow'},
    'error': {'color': 'red'},
    'critical': {'color': 'magenta'},
}


def setup_logger(args):
    # Create folders and copy config json when running via Akamai CLI
    Path('logs').mkdir(parents=True, exist_ok=True)
    Path('config').mkdir(parents=True, exist_ok=True)
    origin_config = load_local_config_file(config_file='logging.json')

    with open(origin_config) as f:
        log_cfg = json.load(f)
    log_cfg['formatters']['long']['()'] = 'utils.cli.CLIFormatter'

    dictConfig(log_cfg)
    logging.Formatter.converter = time.gmtime

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Set up colored console logs using coloredlogs library
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
        origin_config = f'config/{config_file}'

    return origin_config


def countdown(time_sec: int, msg: str, logger=None):
    time_min = int(time_sec / 60)
    msg = f'{msg} {time_min} minutes count down'
    logger.critical(msg)
    while time_sec:
        mins, secs = divmod(time_sec, 60)
        timeformat = f'{mins:02d}:{secs:02d}'
        print(f'\t\t\t\t{timeformat}', end='\r')
        time.sleep(1)
        time_sec -= 1
