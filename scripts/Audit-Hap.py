#!/usr/bin/env python3
"""Inventory actual HAP bytes and enforce payload policy; not release approval."""
import argparse
from pathlib import Path
import zipfile
from release_tools import audit_hap, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hap')
    parser.add_argument('--manifest')
    parser.add_argument('--mode', choices=['development', 'release'], default='development')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if Path(args.output).exists():
            raise ValueError('output already exists; select a new report path')
        manifest = read_json(args.manifest) if args.manifest else None
        report = audit_hap(args.hap, manifest, args.mode)
        write_json(args.output, report)
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, f'HAP audit failed: {error}\n')
    print(f'PASS HAP content audit ({args.mode}); {len(report["files"])} files; not release approval')


if __name__ == '__main__':
    main()
