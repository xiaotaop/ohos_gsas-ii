#!/usr/bin/env python3
"""Bind the API23 HAP's carried-forward material review to new device evidence.

Extract the immutable C delivery ZIP first. This script only assembles the
review input; Finalize-HapSbom.py independently audits the actual HAP and
rejects incomplete or mismatched evidence. It never authorizes store release.
"""
import argparse
import json
from pathlib import Path
import shutil

import release_tools as rt


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def canonical_hash(value):
    return rt.digest(json.dumps(value, sort_keys=True).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--delivery', type=Path, required=True,
                        help='Extracted c-api23-c47b610-d65a64a9 directory')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    delivery = args.delivery.resolve()
    output = args.output.resolve()
    if output.exists():
        parser.error('output already exists')

    physical = repo / 'packaging/reviews/c-api23-final/physical-acceptance.json'
    material_path = repo / 'packaging/reviews/c-api23-c47b610/material-review.json'
    binding_path = repo / 'packaging/reviews/c-api23-c47b610/runtime-sbom-license-binding.json'
    old_path = repo / 'packaging/reviews/70588bde-final/review-decisions.json'
    acceptance = load(physical)
    material = load(material_path)
    old = load(old_path)
    draft = load(delivery / 'sbom/hap-sbom.draft.cdx.json')
    report = load(delivery / 'third-party-observations/third-party-review.json')
    hap_hash = rt.file_hash(delivery / 'GSAS-II-0.1.1-c47b610-api23-signed.hap')
    if (hap_hash != acceptance['hapSha256'] or hap_hash != material['hapSha256']
            or material['referenceReviewSha256'] != rt.file_hash(old_path)
            or material['runtimeSbomLicenseBindingSha256'] != rt.file_hash(binding_path)
            or not material['materialReviewComplete']
            or not all(acceptance.get(key) is True for key in (
                'installationPassed', 'coreReadyPassed', 'realFiveStagePassed',
                'gpxJsonLogSystemPickerExportPassed',
                'completedJobProcessRestartRecoveryPassed'))
            or acceptance['independentWindowsBaselineChecksPassed'] != 12):
        raise ValueError('material, HAP, reference review or physical evidence mismatch')
    components = material['componentDispositions']
    if {item['ref'] for item in components} != {item['ref'] for item in old['components']}:
        raise ValueError('carried-forward component set changed')
    if {item['id'] for item in material['automaticFindingDisposition']} != {
            item['id'] for item in report['findings']}:
        raise ValueError('new automatic findings lack explicit material disposition')
    if {item['id'] for item in old['findingDispositions']} != {
            item['id'] for item in report['findings']}:
        raise ValueError('reference finding decisions cannot be carried forward')

    copied = delivery / 'physical-acceptance.json'
    if copied.exists() and rt.file_hash(copied) != rt.file_hash(physical):
        raise ValueError('different physical acceptance file already exists in delivery')
    shutil.copyfile(physical, copied)

    evidence_names = [
        'physical-acceptance.json', 'THIRD-PARTY-NOTICES.txt', 'SHA256SUMS',
        'BUILD-RECEIPT.json', 'build-profile-source-match.json',
        'exact-source-validation.json', 'hap-config-diff.json',
        'material-review.json', 'runtime-sbom-license-binding.json',
        'signature-native-verification.json', 'scientific-elf.json',
        'gsas-port-source-companion.tar.gz',
        'gsas-controlled-cpython-source-20261020.tar.gz',
        'sbom/hap-inventory.json', 'sbom/hap-native-dependencies.json',
        'third-party-observations/third-party-review.json',
    ]
    evidence = [{'file': name, 'sha256': rt.file_hash(delivery / name)}
                for name in evidence_names]
    decision = {
        'schemaVersion': 1,
        'kind': 'C-hash-bound-engineering-review',
        'reviewer': 'Codex technical review at group leader request; not a forged human signature',
        'date': '2026-10-21',
        'hapSha256': hap_hash,
        'scope': ('Exact c47b610 API23-minimum release/internaltesting HAP on HAD-W32/API23 '
                  'with complete C source, runtime and notices; no API20/API24 or public-store approval'),
        'draftCanonicalSha256': canonical_hash(draft),
        'reportCanonicalSha256': canonical_hash(report),
        'acceptanceRecord': 'physical-acceptance.json',
        'evidence': evidence,
        'findingDispositions': old['findingDispositions'],
        'components': components,
        'excludedCode': old['excludedCode'],
        'retainedNoticeOnly': old['retainedNoticeOnly'],
        'nonBlockingProvenanceLimits': material['nonBlockingProvenanceLimits'],
        'step2EngineeringDeliveryComplete': True,
        'publicDistributionApproved': False,
        'releaseApproved': False,
        'nativeDependencyRecord': 'sbom/hap-native-dependencies.json',
        'externalNotices': {
            'filename': 'THIRD-PARTY-NOTICES.txt',
            'sha256': rt.file_hash(delivery / 'THIRD-PARTY-NOTICES.txt'),
            'scope': 'Complete notices from the exact API23 candidate delivery ZIP',
        },
        'carriedForwardReview': {
            'fromHapSha256': old['hapSha256'],
            'basis': ('C verified unchanged runtime, native and license bytes and supplied '
                      'new HAP/source binding; API23 same-HAP device acceptance is separately bound'),
            'proofFile': 'hap-config-diff.json',
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(decision, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'hapSha256': hap_hash, 'components': len(components),
                      'evidence': len(evidence), 'reviewSha256': rt.file_hash(output)}))


if __name__ == '__main__':
    main()
