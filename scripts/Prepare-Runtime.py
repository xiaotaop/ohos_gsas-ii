#!/usr/bin/env python3
"""Verify an expanded B-provided payload and prepare a new host-side revision."""
import argparse
import json
from release_tools import prepare_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--payload', required=True)
    parser.add_argument('--output', required=True, help='New directory outside payload; never replace a previous revision')
    args = parser.parse_args()
    try:
        manifest = prepare_runtime(args.manifest, args.payload, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Runtime preparation failed: {error}\n')
    print(json.dumps({'runtimeId': manifest['runtimeId'], 'status': 'prepared-not-device-validated'}))


if __name__ == '__main__':
    main()
