from __future__ import annotations

import logging
import os


# Create a custom formatter that includes the folder name
class CLIFormatter(logging.Formatter):
    def format(self, record):
        record.filename = os.path.join(os.path.basename(os.path.dirname(record.pathname)), os.path.basename(record.filename))
        return super().format(record)


main_commands = [{'list': 'List all enrollments',
                  'optional_arguments': [{'name': 'contract', 'help': 'contractId'},
                                         {'name': 'json', 'help': 'Output format is json', 'action': 'store_true'},
                                         {'name': 'show-expiration', 'help': 'shows expiration date of the enrollment',
                                          'action': 'store_true'}
                                         ]},
                 {'retrieve-enrollment': 'Output enrollment data to json or yaml format',
                  'optional_arguments': [{'name': 'enrollment-id', 'help': 'enrollment-id of the enrollment'},
                                         {'name': 'cn', 'help': 'Common name of the certificate'},
                                         {'name': 'contract', 'help': 'contractId'},
                                         {'name': 'network', 'help': 'Deployment detail of certificate in staging or production'},
                                         {'name': 'json', 'help': 'Output format is json', 'action': 'store_true'},
                                         {'name': 'yaml', 'help': 'Output format is yaml', 'action': 'store_true'}]},
                 {'retrieve-deployed': 'Output information about certifcate deployed on network',
                  'optional_arguments': [{'name': 'enrollment-id', 'help': 'enrollment-id of the enrollment'},
                                         {'name': 'cn', 'help': 'Common Name of certificate'},
                                         {'name': 'network', 'help': 'Deployment detail of certificate in staging or production'},
                                         {'name': 'leaf', 'help': 'Get leaf certificate in PEM format'},
                                         {'name': 'chain', 'help': 'Get complete certificate in PEM format'},
                                         {'name': 'info', 'help': 'Get details of certificate in human readable format'},
                                         {'name': 'json', 'help': 'Output format is json'}]},
                 {'status': 'Get any current change status for an enrollment',
                  'optional_arguments': [{'name': 'enrollment-id', 'help': 'enrollment-id of the enrollment'},
                                         {'name': 'cn', 'help': 'Common Name of certificate'},
                                         {'name': 'validation-type', 'help': 'Use http or dns'}]},
                 {'create': 'Create a new enrollment from a yaml or json input file',
                  'optional_arguments': [{'name': 'force', 'help': 'No value'},
                                         {'name': 'contract', 'help': 'Contract ID under which Enrollment/Certificate has to be created'},
                                         {'name': 'allow-duplicate-cn', 'help': 'Allows a new certificate to be created with the same CN as an existing certificate'},
                                         {'name': 'file', 'help': 'Input filename from templates folder to read enrollment details'}]},
                 {'update': 'Update an enrollment from a yaml or json input file',
                  'optional_arguments': [{'name': 'cn', 'help': 'Common Name of Certificate to update'},
                                         {'name': 'enrollment-id', 'help': 'enrollment-id of the enrollment'},
                                         {'name': 'file', 'help': 'Input filename from templates folder to read enrollment details',
                                          'default': 'enrollments.json'},
                                         {'name': 'force', 'help': 'Skip the stdout display and user confirmation',
                                          'action': 'store_true'},
                                         {'name': 'force-renewal', 'help': 'force certificate renewal for enrollment',
                                          'action': 'store_true'}, ]},
                 {'cancel': 'Cancel an existing change',
                  'optional_arguments': [{'name': 'cn', 'help': 'Common Name of certificate'},
                                         {'name': 'enrollment-id', 'help': 'enrollment-id of the enrollment'},
                                         {'name': 'force', 'help': 'Skip the stdout display and user confirmation',
                                          'action': 'store_true'}]},
                 {'delete': 'Delete an existing enrollment forever!',
                  'optional_arguments': [{'name': 'cn', 'help': 'Common Name of certificate'},
                                         {'name': 'enrollment-id', 'help': 'enrollment-id of the enrollment'},
                                         {'name': 'force', 'help': 'Skip the stdout display and user confirmation',
                                          'action': 'store_true'}]},
                 {'audit': 'Generate a report in csv format by default. Can also use --json/xlsx',
                  'optional_arguments': [{'name': 'contract', 'help': 'contractId'},
                                         {'name': 'concurrency', 'help': 'concurrency', 'default': 5},
                                         {'name': 'output-file', 'help': 'Name of the outputfile to be saved to'},
                                         {'name': 'json', 'help': 'Output format is json', 'action': 'store_true'},
                                         {'name': 'xlsx', 'help': 'Output format is xlsx', 'action': 'store_true'},
                                         {'name': 'csv', 'help': 'Output format is csv', 'action': 'store_true'},
                                         {'name': 'include-change-details', 'help': 'Add additional details of pending certificates'}]},
                 {'proceed': 'Proceed to deploy certificate',
                  'optional_arguments': [{'name': 'force', 'help': 'Skip the stdout display and user confirmation'},
                                         {'name': 'cert-file', 'help': 'Signed leaf certificate (Mandatory only in case of third party cert upload)'},
                                         {'name': 'trust-file', 'help': 'Signed certificate of CA (Mandatory only in case of third party cert upload)'},
                                         {'name': 'key-type', 'help': 'Either RSA or ECDSA (Mandatory only in case of third party cert upload)'},
                                         {'name': 'enrollment-id', 'help': 'enrollment-id of the enrollment'},
                                         {'name': 'cn', 'help': 'Common Name of certificate'}]}, ]
