#!/usr/bin/env python3
"""Build in a fresh ASCII path; retain HAP, content audit and source/tool record."""
import argparse
import datetime
import json
import os
import pathlib
import platform
import shutil
import subprocess
import tempfile
import zipfile

from release_tools import (ReleaseError, audit_hap, file_hash, fingerprint, install_prepared,
                           prepare_runtime, require, source_files, stage_app, write_json)


def command_output(command, cwd=None):
    try:
        result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unavailable'


def cli_command(path, arguments):
    # Avoid cmd.exe interpolation of device names or paths containing metacharacters.
    if os.name == 'nt' and pathlib.Path(path).suffix.lower() in {'.cmd', '.bat'}:
        package = pathlib.Path(path).parent / 'node_modules/@deveco/deveco-cli'
        metadata = json.loads((package / 'package.json').read_text(encoding='utf-8'))
        binary = metadata.get('bin')
        entry = binary.get('devecocli') if isinstance(binary, dict) else binary
        require(isinstance(entry, str), 'npm package has no devecocli entry')
        target = (package / entry).resolve()
        require(target.is_file() and package.resolve() in target.parents, 'invalid CLI package entry')
        node = shutil.which('node')
        require(node is not None, 'Node.js is required for the Windows npm CLI shim')
        return [node, str(target), *arguments]
    return [str(path), *arguments]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-mode', choices=['debug', 'release'], default='debug')
    parser.add_argument('--check', action='store_true', help='Run ArkTS checks before building')
    parser.add_argument('--device', help='Install/run the built HAP without uninstalling user data')
    parser.add_argument('--stage-root', type=pathlib.Path, default=pathlib.Path(tempfile.gettempdir()),
                        help='Existing writable ASCII directory (defaults to OS temp directory)')
    parser.add_argument('--output-dir', type=pathlib.Path, help='New directory for reproducible build evidence')
    parser.add_argument('--cli', help='Explicit DevEco CLI executable')
    parser.add_argument('--runtime-manifest', type=pathlib.Path)
    parser.add_argument('--runtime-payload', type=pathlib.Path)
    parser.add_argument('--audit-mode', choices=['development', 'release'], default='development')
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[1]
    try:
        require(bool(args.runtime_manifest) == bool(args.runtime_payload),
                '--runtime-manifest and --runtime-payload must be supplied together')
        require(args.audit_mode != 'release' or args.runtime_manifest is not None,
                'release audit requires B-provided runtime; use development for the file-service HAP')
        if args.output_dir:
            require(not args.output_dir.exists() and not args.output_dir.is_symlink(),
                    'output directory exists; choose a new output directory')
            destination = args.output_dir.resolve()
            app_root = (repo / 'app').resolve()
            require(app_root not in destination.parents or (app_root / 'build') in destination.parents,
                    'output under app must be inside the ignored app/build directory')
        stage_root = args.stage_root.resolve()
        require(str(stage_root).isascii() and stage_root.is_dir(),
                'stage root must be an existing ASCII directory; set --stage-root')
        cli = args.cli or shutil.which('devecocli')
        if not cli:
            installed = pathlib.Path.home() / '.npm-global/bin/devecocli'
            cli = str(installed) if installed.is_file() else None
        require(bool(cli), 'devecocli is not installed; add it to PATH or use --cli')
        stage_base = pathlib.Path(tempfile.mkdtemp(prefix='gsaspc-', dir=stage_root))
        stage = stage_base / 'app'
        files = stage_app(repo / 'app', stage)
        source_commit = command_output(['git', 'rev-parse', 'HEAD'], repo)
        dirty = command_output(['git', 'status', '--porcelain'], repo)
        tooling = []
        for folder in ('scripts', 'packaging'):
            for item in source_files(repo / folder):
                tooling.append({'path': folder + '/' + item['path'], 'sha256': item['sha256']})
        manifest = None
        if args.runtime_manifest:
            prepared = stage_base / 'prepared-runtime'
            manifest = prepare_runtime(args.runtime_manifest, args.runtime_payload, prepared)
            install_prepared(prepared, stage)
        build_inputs = source_files(stage)
        print(f'Build directory: {stage}', flush=True)
        if args.check:
            subprocess.run(cli_command(cli, ['check', 'arkts']), cwd=stage, check=True)
        subprocess.run(cli_command(cli, ['build', '--modules', 'entry', '--build-mode', args.build_mode]),
                       cwd=stage, check=True)
        require(source_files(stage) == build_inputs, 'build mutated source inputs; no artifact archived')
        outputs = stage / 'entry/build/default/outputs/default'
        haps = sorted(outputs.glob('*.hap'))
        require(bool(haps), 'build succeeded without an entry HAP')
        reports = [audit_hap(hap, manifest, args.audit_mode) for hap in haps]
        if args.audit_mode == 'release':
            require(args.build_mode == 'release', 'release audit needs --build-mode release')
        output = args.output_dir or (repo / 'app/build/deliverables' / stage_base.name)
        require(not output.exists(), 'output directory exists; choose a new output directory')
        output.mkdir(parents=True)
        artifacts = []
        for hap, report in zip(haps, reports):
            dest = output / hap.name
            shutil.copyfile(hap, dest)
            require(file_hash(dest) == report['hapSha256'], 'HAP changed while archiving')
            audit_name = hap.name + '.inventory.json'
            write_json(output / audit_name, report)
            artifacts.append({'path': hap.name, 'sha256': report['hapSha256'],
                              'size': report['hapSize'], 'inventory': audit_name,
                              'inventorySha256': file_hash(output / audit_name),
                              'app': report['app'], 'signingVerified': False})
        if manifest:
            write_json(output / 'runtime-manifest.json', manifest)
        tools = {'python': platform.python_version(), 'platform': platform.platform(),
                 'devecocli': command_output(cli_command(cli, ['--version'])),
                 'node': command_output(['node', '--version']),
                 'git': command_output(['git', '--version'])}
        record = {'schemaVersion': 1, 'kind': 'development-build-record',
                  'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'sourceCommit': source_commit, 'workingTreeDirty': None if dirty == 'unavailable' else bool(dirty),
                  'sourceFiles': files, 'sourceFingerprintSha256': fingerprint(files),
                  'buildInputFiles': build_inputs, 'buildInputFingerprintSha256': fingerprint(build_inputs),
                  'toolingFiles': tooling, 'toolingFingerprintSha256': fingerprint(tooling),
                  'toolVersions': tools, 'buildMode': args.build_mode,
                  'runtimeId': manifest['runtimeId'] if manifest else None,
                  'runtimeManifestSha256': file_hash(output / 'runtime-manifest.json') if manifest else None,
                  'auditMode': args.audit_mode, 'releaseCandidateApproved': False,
                  'artifacts': artifacts, 'deviceRun': 'not-requested' if not args.device else 'pending'}
        write_json(output / 'build-record.json', record)
        print(f'Build record: {output / "build-record.json"}', flush=True)
        if args.device:
            try:
                subprocess.run(cli_command(cli, ['run', '--module', 'entry', '--build-mode', args.build_mode,
                                                '--device', args.device, '--skip-build']), cwd=stage, check=True)
                record['deviceRun'] = 'cli-run-and-smoke-passed'
            except subprocess.CalledProcessError:
                record['deviceRun'] = 'failed'
                write_json(output / 'build-record.json', record)
                raise
            write_json(output / 'build-record.json', record)
        print(f'Artifacts: {output}', flush=True)
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Build failed: {error}\n')


if __name__ == '__main__':
    main()
