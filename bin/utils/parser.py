#!/usr/bin/env python
from __future__ import annotations

import argparse

import rich_argparse as rap
import utils.cli as cli


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
    def all_command(cls, subparsers):
        actions = {}
        for main_cmd_info in cli.main_commands:
            command, main_cmd_help = next(iter(main_cmd_info.items()))
            try:
                sc = cli.sub_commands[command]
            except Exception:
                sc = None
            actions[command] = cls.create_main_command(subparsers,
                                                       name=command,
                                                       help=main_cmd_help,
                                                       required_arguments=main_cmd_info.get('required_arguments', []),
                                                       optional_arguments=main_cmd_info.get('optional_arguments', []),
                                                       subcommands=sc,
                                                       options=None)

    @classmethod
    def get_args(cls, args):
        parser = argparse.ArgumentParser(prog='akamai cps',
                                         formatter_class=CustomHelpFormatter,
                                         conflict_handler='resolve', add_help=False,
                                         description='Akamai CLI for CPS',
                                         epilog='Use %(prog)s {command} [-h]/[--help] to get help on individual command')

        parser._optionals.title = 'Global options'

        parser.add_argument('-a', '--accountkey',
                            metavar='', type=str, dest='account_switch_key',
                            help='account switch key (Akamai Internal Only)')
        parser.add_argument('-e', '--edgerc',
                            metavar='', type=str, dest='edgerc',
                            help='location of the credentials file [$AKAMAI_EDGERC]')
        parser.add_argument('-s', '--section',
                            metavar='', type=str, dest='section', default='default',
                            help='section of the credentials file [$AKAMAI_EDGERC_SECTION]')
        parser.add_argument('-v', '--version', action='version', version='%(prog)s v1.0.0',
                             help='show akamai cli utility version')
        parser.add_argument('-h', '--help', action='help', help='show this help message and exit')
        parser.add_argument('-l', '--log-level',
                            choices=['debug', 'info', 'warning', 'error', 'critical'],
                            default='info',
                            help='Set the log level. Too noisy, increase to warning')

        subparsers = parser.add_subparsers(title='commands', metavar='', dest='command')

        optional = parser.add_argument_group('Optional Arguments')
        optional.add_argument('-v', '--verbose', action='store_true', help=argparse.SUPPRESS)

        cls.all_command(subparsers)
        return parser.parse_args(args)

    @classmethod
    def create_main_command(cls, subparsers, name, help,
                            required_arguments=None,
                            optional_arguments=None,
                            subcommands=None,
                            options=None):

        action = subparsers.add_parser(name=name,
                                       description=help,
                                       help=help,
                                       add_help=True,
                                       usage=None,
                                       formatter_class=CustomHelpFormatter)

        if subcommands:
            subparsers = action.add_subparsers(title=name, metavar='', dest='subcommand')
            for subcommand in subcommands:
                subcommand_name = subcommand['name']
                subcommand_help = subcommand['help']
                subcommand_required = subcommand.get('required_arguments', None)
                subcommand_optional = subcommand.get('optional_arguments', None)
                cls.create_main_command(subparsers, subcommand_name, subcommand_help,
                                        subcommand_required,
                                        subcommand_optional,
                                        subcommands=subcommand.get('subcommands', None),
                                        options=None)

        cls.add_arguments(action, required_arguments, optional_arguments)

        if options:
            options_group = action.add_argument_group('Options')
            for option in options:
                option_name = option['name']
                del option['name']
                try:
                    action_value = option['action']
                    del option['action']
                    options_group.add_argument(f'--{option_name}', action=action_value, **option)
                except KeyError:
                    options_group.add_argument(f'--{option_name}', metavar='', **option)
        return action

    @classmethod
    def add_mutually_exclusive_group(cls, action, argument, conflicting_argument):

        group = action.add_mutually_exclusive_group()
        group.add_argument(argument['name'], help=argument['help'], nargs='+')

        # Add the conflicting argument to the group as a mutually exclusive argument
        conflicting_argument_help = [arg['help'] for arg in argument if arg['name'] == conflicting_argument]
        group.add_argument(conflicting_argument, help=conflicting_argument_help, nargs='+')

    @classmethod
    def add_arguments(cls, action, required_arguments=None, optional_arguments=None):

        if required_arguments:
            required = action.add_argument_group('Required Arguments')
            for arg in required_arguments:
                name = arg['name']
                del arg['name']
                try:
                    action_value = arg['action']
                    del arg['action']
                    required.add_argument(f'--{name}', action=action_value, **arg)
                except KeyError:
                    required.add_argument(f'--{name}', metavar='', **arg)

        if optional_arguments:
            optional = action.add_argument_group('Optional Arguments')
            for arg in optional_arguments:
                if arg['name'] == '--group-id':
                    cls.add_mutually_exclusive_group(action, arg, '--property-id')
                elif arg['name'] == '--property-id':
                    cls.add_mutually_exclusive_group(action, arg, '--group-id')
                else:
                    name = arg['name']
                    del arg['name']
                    try:
                        action_value = arg['action']
                        del arg['action']
                        optional.add_argument(f'--{name}', required=False, action=action_value, **arg)
                    except KeyError:
                        optional.add_argument(f'--{name}', metavar='', required=False, **arg)

            optional.add_argument('--log-level',
                                  choices=['debug', 'info', 'warning', 'error', 'critical'],
                                  default='info',
                                  help='Set the log level. Too noisy, increase to warning')
