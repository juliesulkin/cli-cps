#!/usr/bin/env python

import argparse
import sys
import rich_argparse as rap
import utils.cli_logging as log


logger = log.setup_logger()

class OnelineArgumentFormatter(rap.ArgumentDefaultsRichHelpFormatter, rap.RichHelpFormatter):
    def __init__(self, prog, max_help_position=30, **kwargs):
        super().__init__(prog, **kwargs)
        self._max_help_position = max_help_position


class CustomHelpFormatter(rap.ArgumentDefaultsRichHelpFormatter, rap.RichHelpFormatter):
    def __init__(self, prog, indent_increment=2, max_help_position=30, width=None):
        super().__init__(prog, indent_increment, max_help_position, width)
        rap.RichHelpFormatter.styles['argparse.text'] = 'italic'
        rap.RichHelpFormatter.styles['argparse.prog'] = '#D65E76'
        rap.RichHelpFormatter.styles['argparse.args'] = '#67BEE3'
        rap.RichHelpFormatter.styles['argparse.groups'] = '#B576BC'
        rap.RichHelpFormatter.styles['argparse.metavar'] = 'grey50'
        rap.RichHelpFormatter.group_name_formatter = str.upper
        rap.RichHelpFormatter.usage_markup = True


class AkamaiParser(argparse.ArgumentParser):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=30)
        self.usage = 'akamai cps [options] [command] [subcommand] [arguments] -h'

    @classmethod
    def get_args(self, args):
        parser = argparse.ArgumentParser(prog='cps', formatter_class=CustomHelpFormatter)
        parser.add_argument('-a', '--account-key',
                                metavar='', type=str, dest='account_switch_key',
                                help='account switch key (Akamai Internal Only)')
        parser.add_argument('-e', '--edgerc',
                            metavar='', type=str, dest='edgerc',
                            help='location of the credentials file [$AKAMAI_EDGERC]')
        parser.add_argument('-s', '--section',
                            metavar='', type=str, dest='section', default='default',
                            help='section of the credentials file [$AKAMAI_EDGERC_SECTION]')

        sub_parsers = parser.add_subparsers(help='sub-command help', dest='command')

        # create the parser for the "prerequisites" sub-command
        _list = sub_parsers.add_parser('list', help='list all enrollments',formatter_class=CustomHelpFormatter)
        _list.add_argument('--show-expiration', 
                                    metavar='', action='store_true', default = False, help='shows expiration date of the enrollment')
       
        
         # create the parser for the "prerequisites" sub-command
        _retrieve_enrollment = sub_parsers.add_parser('retrieve-enrollment', help='Output enrollment data to json or yaml format',formatter_class=CustomHelpFormatter)
        _retrieve_enrollment.add_argument('-id','--enrollment-id', 
                                    metavar='',type=str, help='enrollment-id of the enrollment', required=False)
        _retrieve_enrollment.add_argument('-cn','--common-name', 
                                    metavar='',type=str, help='Common name of the certificate', required=False)
        _retrieve_enrollment.add_argument('--json', 
                                    metavar='',action='store_true', default=False,
                                    help='Output format is json', required=False)
        _retrieve_enrollment.add_argument('--yaml', 
                                    metavar='',action='store_true', default=False,
                                    help='Output format is yaml', required=False)
        _retrieve_enrollment.add_argument('--network', 
                                    metavar='',type=str, help='Deployment detail of certificate in staging or production', required=False)


        # create the parser for the "prerequisites" sub-command
        _retrieve_deployed = sub_parsers.add_parser('retrieve-deployed', help='Output information about certifcate deployed on network',formatter_class=CustomHelpFormatter)
        _retrieve_deployed.add_argument('-id','--enrollment-id', 
                                    metavar='',type=str, help='enrollment-id of the enrollment', required=False)
        _retrieve_deployed.add_argument('-cn','--common-name', 
                                    metavar='',type=str, help='Common name of the certificate', required=False)
        _retrieve_deployed.add_argument('--json', 
                                    metavar='',action='store_true', default=False,
                                    help='Output format is json', required=False)
        _retrieve_deployed.add_argument('--network', 
                                    metavar='',type=str, help='Deployment detail of certificate in staging or production', required=False)
        _retrieve_deployed.add_argument('--leaf', 
                                    metavar='',action='store_true', default=False,
                                    help='Get leaf certificate in PEM format', required=False)
        _retrieve_deployed.add_argument('--chain', 
                                    metavar='',action='store_true', default=False,
                                    help='Get complete certificate in PEM format', required=False)
        _retrieve_deployed.add_argument('--info', 
                                    metavar='',action='store_true', default=False,
                                    help='Get details of certificate in human readable format', required=False)
    

        _retrieve_deployed.add_argument('-cn','--common-name', 
                                    metavar='',type=str, help='Common name of the certificate', required=False)
        #_prework.add_argument('--group-id', type=str, help='group id of hostname bucket')
        
        # create the parser for the "onboard-host" sub-command
        _status = sub_parsers.add_parser('status', help='Get any current change status for an enrollment',formatter_class=CustomHelpFormatter)
        _status.add_argument('-id','--enrollment-id', 
                                    metavar='',type=str, help='enrollment-id of the enrollment', required=False)
        _status.add_argument('-cn','--common-name', 
                                    metavar='',type=str, help='Common name of the certificate', required=False)
        _status.add_argument('--validation-type', 
                                    metavar='',type=str, help='Use http or dns', required=False)
        
       

        return parser.parse_args(args)

    

