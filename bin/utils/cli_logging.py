from __future__ import annotations

import json
import logging
import os
import time
from logging.config import dictConfig
from pathlib import Path

import coloredlogs
import utils.emojis as emoji
from rich import print
from rich.console import Console
from rich.panel import Panel

custom_level_styles = {
    'debug': {'color': 'cyan'},
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
    origin_config = filepath_logging_config(config_file='logging.json')

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


def filepath_logging_config(config_file: str) -> str:
    docker_path = os.path.expanduser(Path('/cli'))
    local_home_path = os.path.expanduser(Path('~/.akamai-cli/src/cli-cps'))

    if Path(docker_path).exists():  # docker
        return f'{docker_path}/.akamai-cli/src/cli-cps/bin/config/{config_file}'
    elif Path(local_home_path).exists():  # local OS cli
        env_path = f'{local_home_path}/bin/config/{config_file}'
        return os.path.expanduser(env_path)
    else:  # local python development
        return f'{os.getcwd()}/bin/config/{config_file}'


def console_panel(console: Console, header: str, title: str,
                  align: str | None = 'left',
                  emoji_name: emoji | None = emoji.star):
    print()
    console.print(Panel(header,
                        width=150,
                        title_align=align,
                        title=f'{emoji_name}[bold white]{title}[/bold white]{emoji_name}'))
    print()


def console_header(console: Console, msg: str, emoji_name: emoji, sandwiches: bool | None = False):
    print()
    if sandwiches:
        console.print(f'{emoji_name}[bold white] {msg} [/bold white]{emoji_name}')
    else:
        console.print(f'{emoji_name}[bold white] {msg} [/bold white]')
    print()


def console_complete(console: Console):
    print()
    print()
    console.print(Panel.fit(emoji.all_done,
                            title=f'{emoji.tada * 35}',
                            title_align='center',
                            subtitle=f'{emoji.tada * 35}',
                            )
                  )
    print()
