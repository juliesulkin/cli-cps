from akamai_apis.auth import AkamaiSession
import json
import utils.cli_logging as log
logger = log.setup_logger()

class IdentityAccessManagement(AkamaiSession):
    def __init__(self,
                 args):
        super().__init__(args)
        

    def search_account(self, _auth):

        url = f'{self.baseurl}/identity-management/v3/api-clients/self/account-switch-keys'
        params = {}
        if _auth.account_switch_key:
            params['search'] = _auth.account_switch_key.split(':')[0]
            
        search_account_resp = self.s.get(url, params=params, headers=self.headers)
                
        logger.debug(search_account_resp.json())
        if search_account_resp.ok:
            try:
                account_name = search_account_resp.json()[0]['accountName']
                return(account_name)
            except IndexError:
                logger.error('Error looking up account name')
                logger.debug(json.dumps(search_account_resp))
                return (False)
        
        else:
            logger.error('Error looking up account name')
            logger.debug(search_account_resp)
            return(False)



