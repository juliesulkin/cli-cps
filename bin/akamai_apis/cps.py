from __future__ import annotations

import logging

from akamai_apis.auth import AkamaiSession
from utils import utility

logger = logging.getLogger(__name__)


class Cps(AkamaiSession):

    def __init__(self, logger: logging.Logger, args):
        super().__init__(args)
        utility()
