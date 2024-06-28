# Techdocs reference
# https://techdocs.akamai.com/cps/reference/api-summary
# https://techdocs.akamai.com/cps/reference/rate-limiting
# Maximum limit of 100 requests per every 2 minutes, per account.
# Short-term rate limit of 20 requests per 2 seconds, per account.
from __future__ import annotations

import logging

from akamai_apis import headers
from akamai_apis.auth import AkamaiSession
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from ratelimit import limits
from ratelimit import sleep_and_retry
from requests import Response
from requests.exceptions import ChunkedEncodingError
from rich.console import Console


console = Console(stderr=True)
logger = logging.getLogger(__name__)


TIME_PERIOD = 1
MAX_CALLS = 5


class Enrollment(AkamaiSession):
    def __init__(self, args):
        super().__init__(args)
        self.MODULE = f'{self.base_url}/cps/v2'
        self.headers = {'accept': 'application/vnd.akamai.cps.enrollments.v11+json'}
        self._params = super().params
        self._enrollment_id = None
        self._url_endpoint = None

    @property
    def enrollment_id(self) -> int:
        return self._enrollment_id

    def get_contract(self):
        url = f'{self.base_url}/contract-api/v1/contracts/identifiers?depth=TOP'
        return self.session.get(url, params=self._params)

    @sleep_and_retry
    @limits(calls=MAX_CALLS, period=TIME_PERIOD)
    def get_enrollment(self, enrollment_id: int) -> tuple[Response, int]:
        """
        Gets an enrollment.
        """
        headers = {'accept': 'application/vnd.akamai.cps.enrollment.v12+json'}
        url = f'{self.MODULE}/enrollments/{enrollment_id}'

        if 'contractId' in self._params:
            del self._params['contractId']

        resp = None
        try:
            with self.session.get(url, headers=headers, params=self._params) as resp:
                if not resp.ok:
                    logger.debug(f'{enrollment_id:<20} {resp.status_code} {resp.json()}')
                else:
                    self._enrollment_id = enrollment_id
                    logger.info(f'{enrollment_id:<20} {resp}')
        except ChunkedEncodingError as err:
            logger.error(f'{enrollment_id:<10} {err}')

        return enrollment_id, resp

    def list_enrollment(self, contract_id: str | None = None):
        """
        A list of the names of each enrollment.
        """
        if contract_id:
            self._params['contractId'] = contract_id
        url = f'{self.MODULE}/enrollments'
        resp = self.session.get(url, params=self._params, headers=self.headers)
        logger.debug(resp.url)
        return resp

    def list_active_enrollment(self, contract_id: str | None = None):
        """
        A list of the names of each enrollment.
        """
        if contract_id:
            self._params['contractId'] = contract_id
        url = f'{self.MODULE}/active-certificates'
        resp = self.session.get(url, params=self._params, headers=self.headers)
        logger.debug(resp.url)
        return resp

    def create_enrollment(self, contract_id: str, payload: dict):
        """
        Creates an enrollment that contains all the information about the process
        that your certificate goes through from the time you request it, through renewal,
        and as you obtain subsequent versions.
        """
        headers = {'accept: application/vnd.akamai.cps.enrollment-status.v1+json',
                   'content-type: application/vnd.akamai.cps.enrollment.v12+json'}

        if contract_id:
            self._params['contractId'] = contract_id
        url = f'{self.MODULE}/enrollments'

        resp = self.session.post(url, data=payload, headers=headers, params=self._params)
        return resp

    def update_enrollment(self, enrollment_id: int, payload: dict,
                          renewal: bool | None = False):
        """
        Updates an enrollment with changes.

        """
        print()
        headers = {'Content-Type': 'application/vnd.akamai.cps.enrollment.v11+json',
                   'Accept': 'application/vnd.akamai.cps.enrollment-status.v1+json'
                   }
        url = f'{self.MODULE}/enrollments/{enrollment_id}'

        self._params['allow-cancel-pending-changes'] = 'true'
        if renewal:
            self.params['force-renewal'] = 'true'

        resp = self.session.put(url, data=payload, headers=headers, params=self._params)
        return resp

    def remove_enrollment(self, enrollment_id: int, deploy_not_after, deploy_not_before,
                          allow_cancel_pending_changes: bool | None = False):
        """
        Removes an enrollment from CPS.
        """
        self._params['allow-cancel-pending-changes'] = allow_cancel_pending_changes
        if deploy_not_after:
            self._params['deploy_not_after'] = deploy_not_after
        if deploy_not_before:
            self._params['deploy_not_before'] = deploy_not_before
        headers = {'Accept': 'application/vnd.akamai.cps.enrollment-status.v1+json'}
        url = f'{self.MODULE}/enrollments/{enrollment_id}'
        resp = self.session.delete(url, headers=headers, params=self._params)
        return resp

    def get_dv_history(self, enrollment_id: int):
        """
        Domain name Validation history for the enrollment.
        """
        url = f'{self.MODULE}/enrollments/{enrollment_id}/dv-history'
        resp = self.session.get(url, params=self._params, headers=headers)
        return resp

    def get_change_status(self, enrollment_id: int, change_id: int):
        """
        Gets the status of a pending change.
        """
        headers = {'Accept': 'application/vnd.akamai.cps.change.v2+json'}
        url = f'{self.MODULE}/enrollments/{enrollment_id}/changes/{change_id}'
        resp = self.session.get(url, params=self._params, headers=headers)
        return resp

    def cancel_change(self, enrollment_id: int, change_id: int):
        """
        Cancels a pending change.
        """
        headers = {'Accept': 'application/vnd.akamai.cps.change-id.v1+json'}
        url = f'{self.MODULE}/enrollments/{enrollment_id}/changes/{change_id}'
        resp = self.session.delete(url, headers=headers, params=self._params)
        return resp


class Deployment(Enrollment):
    def __init__(self, args, enrollment_id: int | None = None):
        super().__init__(args)
        self.MODULE = f'{self.base_url}/cps/v2'
        self.headers = {'accept': 'application/vnd.akamai.cps.deployment.v8+json'}
        self._params = super().params
        self._enrollment_id = enrollment_id

    @property
    def enrollment_id(self) -> int:
        return self._enrollment_id

    @enrollment_id.setter
    def enrollment_id(self, value: int):
        self._enrollment_id = value

    def list_deployments(self):
        """
        Lists the deployments for an enrollment.
        """
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/deployments'
        resp = self.session.get(url, headers=self.headers, params=self._params)
        return resp

    def get_production_deployment(self, override_enrollment_id=False):
        """
        Gets the enrollments deployed on the production network.
        """
        enrollment_id = self.enrollment_id
        if override_enrollment_id:
            enrollment_id = override_enrollment_id

        url = f'{self.MODULE}/enrollments/{enrollment_id}/deployments/production'
        logger.debug(url)
        return self.session.get(url, headers=self.headers, params=self._params)

    def get_staging_deployement(self):
        """
        Gets the enrollments deployed on the staging network.
        """
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/deployments/staging'
        logger.debug(url)
        return self.session.get(url, params=self._params, headers=self.headers)


class Changes(Enrollment):
    custom_headers = headers.category

    def __init__(self, args, enrollment_id: int | None = None):
        super().__init__(args)
        self.MODULE = f'{self.base_url}/cps/v2'
        self._params = super().params
        self._enrollment_id = enrollment_id
        self._url_endpoint = None

    @property
    def enrollment_id(self) -> int:
        return self._enrollment_id

    @enrollment_id.setter
    def enrollment_id(self, value: int):
        self._enrollment_id = value

    @property
    def url_endpoint(self) -> str:
        return self._url_endpoint

    @url_endpoint.setter
    def url_endpoint(self, value: str):
        self._url_endpoint = value

    def get_change_history(self):
        """
        Change history of an enrollment.
        """
        headers = {'accept': 'application/vnd.akamai.cps.change-history.v5+json'}
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/history/changes'
        return self.session.get(url, headers=headers, params=self._params)

    def get_change_status(self, change_id: int):
        """
        Gets the status of a pending change.
        """
        headers = {'accept': 'application/vnd.akamai.cps.change.v2+json'}
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/changes/{change_id}'
        return self.session.get(url, headers=headers, params=self._params)

    def cancel_change_status(self, change_id: int):
        """
        Gets the status of a pending change.
        """
        headers = {'accept': 'application/vnd.akamai.cps.change-id.v1+json'}
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/changes/{change_id}'
        return self.session.delete(url,  headers=headers, params=self._params)

    def get_change(self, change_type: str, change_id: int | None = 0):
        """
        Get detailed information of a pending change
        Currently supported values include
           change-management-info,
           lets-encrypt-challenges,
           post-verification-warnings,
           pre-verification-warnings,
           third-party-csr.
        """

        custom_header = [item[change_type]['info'] for item in self.custom_headers
                         if change_type in item][0]
        url = f'{self.base_url}{self._url_endpoint}'
        logger.critical(url)
        return self.session.get(url, headers=custom_header, params=self._params)

    def update_change(self, change_type: str, hash_value: str, change_id: int | None = 0):
        """
        Updates a pending change.
        Currently supported values include
           change-management-ack,
           lets-encrypt-challenges-completed,
           post-verification-warnings-ack,
           pre-verification-warnings-ack,
           third-party-cert-and-trust-chain
        """
        custom_header = [item[change_type]['update'] for item in self.custom_headers
                         if change_type in item][0]
        url = f'{self.base_url}{self._url_endpoint}xxx'

        payload = {'acknowledgement': 'acknowledge'}
        payload['hash'] = hash_value

        return self.session.post(url, headers=custom_header, params=self._params)

    def get_deployement_schedule(self, change_id):
        """
        Gets the current deployment schedule settings describing
        when a change deploys to the network.
        """
        headers = {'accept': 'application/vnd.akamai.cps.deployment-schedule.v1+json'}
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/changes/{change_id}/deployment-schedule'
        return self.session.get(url, headers=headers, params=self._params)


class Certificate:
    """
    Below class encapsulates the certificate members, this is done to
    decode a certificate into its members or fields
    """
    def __init__(self, certificate):
        self.cert = x509.load_pem_x509_certificate(certificate.encode(), default_backend())

        self.oids = x509.oid.ExtensionOID()
        try:
            self.ext = self.cert.extensions.get_extension_for_oid(self.oids.SUBJECT_ALTERNATIVE_NAME)
            self.sanList = []
            self.sanList = (str(self.ext.value.get_values_for_type(x509.DNSName)).replace(',', '').replace('[',  '').replace(']', ''))
        except Exception:
            pass  # Not every certificate will have SAN

        self.expiration = str(self.cert.not_valid_after.date()) + ' ' + str(self.cert.not_valid_after.time()) + ' UTC'

        for attribute in self.cert.subject:
            self.subject = attribute.value

        self.not_valid_before = str(self.cert.not_valid_before.date()) + ' ' + str(self.cert.not_valid_before.time()) + ' UTC'

        for attribute in self.cert.issuer:
            self.issuer = attribute.value
