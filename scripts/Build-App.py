#!/usr/bin/env python3
"""Stage the app in an ASCII path, then use the installed DevEco CLI.

Hvigor rejects the Chinese SeaDrive workspace path. Source stays in this
repository; dependencies, local profiles and generated packages stay outside
it. A fresh stage also prevents removed source files surviving a rebuild.
"""
import argparse
import pathlib
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-mode', choices=['debug', 'release'], default='debug')
    parser.add_argument('--check', action='store_true', help='Run ArkTS checks before building')
    parser.add_argument('--device', help='Also install and run on this device after building')
    args = parser.parse_args()
    source = pathlib.Path(__file__).resolve().parents[1] / 'app'
    cli = shutil.which('devecocli')
    if not cli:
        installed = pathlib.Path.home() / '.npm-global/bin/devecocli'
        if installed.is_file():
            cli = str(installed)
    if not cli:
        parser.error('devecocli is not installed or not on PATH')
    stage = pathlib.Path(tempfile.mkdtemp(prefix='gsaspc-', dir='/private/tmp')) / 'app'
    shutil.copytree(source, stage, ignore=shutil.ignore_patterns(
        'build', '.cxx', '.cache', '*.tsbuildinfo', '.hvigor', '.hvigor-user', 'oh_modules', 'node_modules',
        '.idea', 'local.properties', '*.hap', '*.app', '*.hqf'))
    print(f'Build directory: {stage}', flush=True)
    if args.check:
        subprocess.run([cli, 'check', 'arkts'], cwd=stage, check=True)
    subprocess.run([cli, 'build', '--modules', 'entry', '--build-mode', args.build_mode], cwd=stage, check=True)
    if args.device:
        subprocess.run([cli, 'run', '--module', 'entry', '--build-mode', args.build_mode,
                        '--device', args.device, '--skip-build'], cwd=stage, check=True)
    print(f'Artifacts: {stage / "entry/build/default/outputs/default"}', flush=True)


if __name__ == '__main__':
    main()
