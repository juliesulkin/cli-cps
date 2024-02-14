from akamai.edgegrid import EdgeGridAuth, EdgeRc
import requests, json, argparse, sys, operator
from pathlib import Path
import sys
from rich.live import Live
from rich.table import Table
from rich.console import Console
import time
import utils.cli_logging as log


logger = log.setup_logger()


class AkamaiSession:

    def __init__(self, args):
        # https://techdocs.akamai.com/property-mgr/reference/api
        self.headers = {'PAPI-Use-Prefixes': 'true',
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'}
        self.edgerc = EdgeRc(f'{str(Path.home())}/.edgerc')
        self.section = args.section if args.section else 'default'
        self.host = self.edgerc.get(self.section, 'host')
        self.baseurl = f'https://{self.host}'
        self.s = requests.Session()
        self.s.auth = EdgeGridAuth.from_edgerc(self.edgerc, self.section)
        self.account_switch_key = args.account_switch_key




