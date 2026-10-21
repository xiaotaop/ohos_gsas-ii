#!/usr/bin/env python3
"""Assemble explicit, hash-bound reviews for the 0.1.2 store HAPs.

The physical test was on the signed device counterpart, not the public APP.
Finalize-HapSbom independently compares their actual ZIP members and keeps
platform/public-distribution approval false.
"""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

import release_tools as rt


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def canonical_hash(value):
    return rt.digest(json.dumps(value, sort_keys=True).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--delivery', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    repo, delivery, output = (p.resolve() for p in (args.repo, args.delivery, args.output))
    if output.exists():
        parser.error('output must be new')
    material_path = repo / 'packaging/reviews/c-store-0.1.2/material-review.json'
    binding_path = repo / 'packaging/reviews/c-store-0.1.2/runtime-sbom-license-binding.json'
    physical_path = repo / 'packaging/reviews/c-store-0.1.2/physical-acceptance.json'
    old_path = repo / 'packaging/reviews/c-api23-final/review-decisions.json'
    material, physical, old = (load(p) for p in (material_path, physical_path, old_path))
    if (not material['materialCompletenessReviewPassed']
            or material['referenceReviewSha256'] != rt.file_hash(old_path)
            or material['materialBindingSha256'] != rt.file_hash(binding_path)
            or physical['result'] != 'critical-device-retest-passed-with-startup-warning'):
        raise ValueError('C material or device evidence is not ready')
    if {row['ref'] for row in material['componentDispositions']} != {
            row['ref'] for row in old['components']}:
        raise ValueError('reviewed component set differs from accepted predecessor')

    counterpart = {
        'deviceHapFile': 'GSAS-II-0.1.2-device-internaltesting.hap',
        'publicHapFile': 'GSAS-II-0.1.2-app-gallery.hap',
        'storeAppFile': 'GSAS-II-0.1.2-app-gallery.app',
        'deviceHapSha256': physical['deviceHapSha256'],
        'publicHapSha256': material['publicHapSha256'],
        'storeAppSha256': material['storeAppSha256'],
        'embeddedHapSha256': load(delivery / 'store-app-verification.json')['storeAppContainedHapSha256'],
    }
    for key in ('deviceHap', 'publicHap', 'storeApp'):
        if rt.file_hash(delivery / counterpart[key + 'File']) != counterpart[key + 'Sha256']:
            raise ValueError('C package hash mismatch: ' + key)
    copy = delivery / 'physical-acceptance.json'
    if copy.exists() and rt.file_hash(copy) != rt.file_hash(physical_path):
        raise ValueError('different physical acceptance already staged')
    shutil.copyfile(physical_path, copy)
    embedded_path = delivery / 'embedded-entry-default.hap'
    with zipfile.ZipFile(delivery / counterpart['storeAppFile']) as archive:
        embedded_bytes = archive.read('entry-default.hap')
    if rt.digest(embedded_bytes) != counterpart['embeddedHapSha256']:
        raise ValueError('APP embedded HAP hash changed')
    if embedded_path.exists() and rt.file_hash(embedded_path) != counterpart['embeddedHapSha256']:
        raise ValueError('different embedded HAP already staged')
    embedded_path.write_bytes(embedded_bytes)

    common_evidence = [
        'physical-acceptance.json', 'THIRD-PARTY-NOTICES.txt', 'SHA256SUMS',
        'BUILD-RECEIPT.json', 'material-review.json', 'runtime-sbom-license-binding.json',
        'signature-native-verification.json', 'store-app-verification.json',
        'device-counterpart-verification.json', 'exact-source-validation.json',
        'runtime-manifest.json', 'gsas-port-source-companion.tar.gz',
        'gsas-controlled-cpython-source.tar.gz',
        *[counterpart[key + 'File'] for key in ('deviceHap', 'publicHap', 'storeApp')],
    ]
    configs = [
        ('public-hap', 'public-standalone-hap', 'GSAS-II-0.1.2-app-gallery.hap',
         'sbom', 'third-party'),
        ('store-app-embedded-hap', 'store-embedded-hap', 'embedded-entry-default.hap',
         'app-sbom', 'app-third-party'),
    ]
    output.mkdir(parents=True)
    for label, kind, hap_name, sbom_dir, report_dir in configs:
        draft = load(delivery / sbom_dir / 'hap-sbom.draft.cdx.json')
        report = load(delivery / report_dir / 'third-party-review.json')
        inventory = load(delivery / sbom_dir / 'hap-inventory.json')
        hap_hash = rt.file_hash(delivery / hap_name)
        if (inventory['hapSha256'] != hap_hash or report['hapSha256'] != hap_hash
                or {row['id'] for row in old['findingDispositions']} != {
                    row['id'] for row in report['findings']}
                or {row['ref'] for row in material['componentDispositions']} != {
                    row['bom-ref'] for row in draft['components'] if row['type'] != 'file'}):
            raise ValueError('target draft, report or reviewed components differ: ' + label)
        evidence_names = common_evidence + [
            sbom_dir + '/hap-inventory.json', sbom_dir + '/hap-native-dependencies.json',
            report_dir + '/third-party-review.json',
        ]
        review = {
            'schemaVersion': 1,
            'kind': 'C-hash-bound-engineering-review',
            'reviewer': 'Codex technical review at group leader request; not a forged human signature',
            'date': '2026-10-21',
            'hapSha256': hap_hash,
            'scope': ('GSAS-II 0.1.2 release/app_gallery candidate, HAD-W32/API23 '
                      'equivalent-payload device evidence; no API20/API24 or platform approval'),
            'acceptanceMode': 'equivalent-device-counterpart',
            'counterpart': {**counterpart, 'kind': kind},
            'draftCanonicalSha256': canonical_hash(draft),
            'reportCanonicalSha256': canonical_hash(report),
            'acceptanceRecord': 'physical-acceptance.json',
            'evidence': [{'file': name, 'sha256': rt.file_hash(delivery / name)}
                         for name in evidence_names],
            'findingDispositions': old['findingDispositions'],
            'components': material['componentDispositions'],
            'excludedCode': material['excludedCode'],
            'nonBlockingProvenanceLimits': material['nonBlockingProvenanceLimits'],
            'nativeDependencyRecord': sbom_dir + '/hap-native-dependencies.json',
            'externalNotices': {
                'filename': 'THIRD-PARTY-NOTICES.txt',
                'sha256': rt.file_hash(delivery / 'THIRD-PARTY-NOTICES.txt'),
                'scope': 'Complete notices from exact 0.1.2 store-candidate delivery',
            },
            'releaseApproved': False,
            'publicDistributionApproved': False,
        }
        path = output / (label + '-review-decisions.json')
        path.write_bytes((json.dumps(review, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print(json.dumps({'target': label, 'hapSha256': hap_hash,
                          'reviewSha256': rt.file_hash(path)}))


if __name__ == '__main__':
    main()
