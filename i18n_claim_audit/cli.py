"""Command line interface."""
import argparse
import json
import sys
from . import __version__
from .core import audit


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, self.prog + ': error: ' + message + '\n')


def main(argv=None):
    parser = Parser(prog='i18n-claim-audit')
    parser.add_argument('root', nargs='?', default='.')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--ignore', nargs='+', action='extend', default=[])
    parser.add_argument('--fail-on', choices=['HIGH', 'MEDIUM'], default='MEDIUM')
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args(argv)
    try:
        result = audit(args.root, args.ignore)
    except (OSError, ValueError, SyntaxError, UnicodeError) as exc:
        print('Input error: ' + str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(result['status'])
        for finding in result['findings']:
            fields = [finding['rule'], finding['severity']]
            if args.verbose:
                fields.append(finding['path'])
            print(' '.join(fields))
    return 2 if any(args.fail_on == 'MEDIUM' or f['severity'] == 'HIGH' for f in result['findings']) else 0
