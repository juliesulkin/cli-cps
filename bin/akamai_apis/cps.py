# Techdocs reference
# https://techdocs.akamai.com/cps/reference/api-summary
from __future__ import annotations

import asyncio
import logging
import time

from akamai_apis import headers
from akamai_apis.auth import AkamaiSession
from cryptography import x509
from cryptography.hazmat.backends import default_backend


logger = logging.getLogger(__name__)


class Cps(AkamaiSession):
    def __init__(self, args, logger: logging.Logger = None):
        super().__init__(args, logger)
        self.logger = logger


class Enrollment(AkamaiSession):
    def __init__(self, args, logger: logging.Logger = None):
        super().__init__(args, logger)
        self.MODULE = f'{self.base_url}/cps/v2'
        self.headers = {'accept': 'application/vnd.akamai.cps.enrollments.v11+json'}
        self._params = super().params
        self._enrollment_id = None
        self.logger = logger

    @property
    def enrollment_id(self) -> int:
        return self._enrollment_id

    def get_contract(self):
        url = f'{self.base_url}/contract-api/v1/contracts/identifiers?depth=TOP'
        return self.session.get(url, params=self._params)

    def get_enrollment(self, enrollment_id: int):
        """
        Gets an enrollment.
        """
        self.logger.debug(f'Getting details for enrollment-id: {enrollment_id}')
        headers = {'accept': 'application/vnd.akamai.cps.enrollment.v11+json'}
        url = f'{self.MODULE}/enrollments/{enrollment_id}'
        resp = self.session.get(url, headers=headers, params=self._params)
        if resp.ok:
            self.enrollment_id = enrollment_id
        return resp

    async def get_enrollment_async(self, enrollment_id: int, rate_limit: int):
        headers = {'accept': 'application/vnd.akamai.cps.enrollment.v11+json'}
        url = f'{self.MODULE}/enrollments/{enrollment_id}'
        async with asyncio.Semaphore(rate_limit):
            # loop = asyncio.get_running_loop()
            resp = await asyncio.to_thread(self.session.get, url, headers=headers, params=self._params)
            try:
                if not resp.ok:
                    time.sleep(40)
                else:
                    return await asyncio.to_thread(resp.json)

            finally:
                resp.close()

    async def fetch_all(self, enrollment_ids: list, rate_limit: int | None = 5):
        tasks = [self.get_enrollment_async(enrollment_id, rate_limit) for enrollment_id in enrollment_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

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

    def list_enrollment(self, contract_id: str | None = None):
        """
        A list of the names of each enrollment.
        """
        if contract_id:
            self._params['contractId'] = contract_id
        url = f'{self.MODULE}/enrollments'
        resp = self.session.get(url, params=self._params, headers=self.headers)
        self.logger.debug(resp.url)
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

    def remove_enrollment(self, enrollment_id: int):
        """
        Removes an enrollment from CPS.
        """
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
    def __init__(self, args, logger: logging.Logger = None, enrollment_id: int | None = None):
        super().__init__(args, logger)
        self.MODULE = f'{self.base_url}/cps/v2'
        self.headers = {'accept': 'application/vnd.akamai.cps.deployment.v8+json'}
        self._params = super().params
        self.logger = logger
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
        return self.session.get(url, headers=self.headers, params=self._params)

    def get_staging_deployement(self):
        """
        Gets the enrollments deployed on the staging network.
        """
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/deployments/staging'
        return self.session.get(url, params=self._params, headers=self.headers)


class Changes(Enrollment):
    def __init__(self, args, logger: logging.Logger = None, enrollment_id: int | None = None):
        super().__init__(args, logger)
        self.MODULE = f'{self.base_url}/cps/v2'
        self._params = super().params
        self._enrollment_id = enrollment_id

    @property
    def enrollment_id(self) -> int:
        return self._enrollment_id

    @enrollment_id.setter
    def enrollment_id(self, value: int):
        self._enrollment_id = value

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

    def get_change(self, change_id: int, allowedInputTypeParam):
        """
        Get detailed information of a pending change
        """
        headers = {'accept': 'application/vnd.akamai.cps.change-management-info.v1+json'}
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/changes/{change_id}'
        url = f'{url}/input/info/{allowedInputTypeParam}'
        return self.session.get(url, headers=headers, params=self._params)

    def update_change(self, change_id: int, allowedInputTypeParam):
        """
        Updates a pending change.
        """
        headers = {'accept: application/vnd.akamai.cps.change-id.v1+json',
                   'content-type: application/vnd.akamai.cps.certificate-and-trust-chain.v2+json'}
        url = f'{self.MODULE}/enrollments/{self.enrollment_id}/changes/{change_id}'
        url = f'{url}/input/update/{allowedInputTypeParam}'
        return self.session.post(url, headers=headers, params=self._params)

    def get_staging_deployement(self, change_id):
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
