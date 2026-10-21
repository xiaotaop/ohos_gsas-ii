#!/usr/bin/env python3
"""Apply an explicit, hash-bound engineering review to an actual HAP SBOM.

No license inference from filenames, no automatic legal/store approval. A new
HAP, draft, acceptance record or decision requires a new review.
"""
import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import zipfile
import release_tools as rt


def load(path):
    return json.loads(path.read_text())


def properties(entry):
    return {p['name']: p['value'] for p in entry.get('properties', [])}


def put(entry, **values):
    old = properties(entry)
    old.update({'gsas:' + k: str(v) for k, v in values.items()})
    entry['properties'] = [{'name': k, 'value': v} for k, v in sorted(old.items())]


def validate_graph(bom, inventory):
    rows = bom['components']
    if {'alg': 'SHA-256', 'content': inventory['hapSha256']} not in bom['metadata']['component'].get('hashes', []):
        raise ValueError('BOM application hash differs from actual HAP')
    refs = [r['bom-ref'] for r in rows] + [bom['metadata']['component']['bom-ref']]
    if len(refs) != len(set(refs)):
        raise ValueError('duplicate BOM reference')
    expected = {f['path']: f['sha256'] for f in inventory['files']}
    actual = {}
    for row in rows:
        if row['type'] == 'file':
            if row['name'] in actual:
                raise ValueError('duplicate file component')
            actual[row['name']] = next(h['content'] for h in row['hashes'] if h['alg'] == 'SHA-256')
    if actual != expected:
        raise ValueError('BOM file inventory differs from actual HAP')
    for edge in bom['dependencies']:
        if edge['ref'] not in refs or not set(edge.get('dependsOn', [])) <= set(refs):
            raise ValueError('unresolved dependency reference')


def validate_equivalent_device_acceptance(acceptance, inventory, decision, evidence):
    """Bind a store container to the tested device HAP without claiming it was installed."""
    if (acceptance.get('result') != 'critical-device-retest-passed-with-startup-warning'
            or acceptance.get('newJob', {}).get('independentNumericComparisonsPassed') != 12
            or not acceptance.get('newJob', {}).get('fiveStagesCompleted')
            or not acceptance.get('exports', {}).get('allThreeVisibleOnPickerReopen')
            or not acceptance.get('restart', {}).get('successfulResultAndArtifactsRestored')
            or acceptance.get('upgrade', {}).get('versionCodeAfter') != 3):
        raise ValueError('device counterpart acceptance is incomplete')
    counterpart = decision['counterpart']
    if (acceptance.get('deviceHapSha256') != counterpart['deviceHapSha256']
            or acceptance.get('publicAppSha256') != counterpart['storeAppSha256']):
        raise ValueError('counterpart hashes differ from physical acceptance')
    bound = {item['file'] for item in decision['evidence']}
    names = [counterpart[key] for key in ('deviceHapFile', 'publicHapFile', 'storeAppFile')]
    if not set(names) <= bound:
        raise ValueError('counterpart packages must be hash-bound evidence')
    device, public, app = (evidence / name for name in names)
    if (rt.file_hash(device) != counterpart['deviceHapSha256']
            or rt.file_hash(public) != counterpart['publicHapSha256']
            or rt.file_hash(app) != counterpart['storeAppSha256']):
        raise ValueError('counterpart package bytes changed')
    with zipfile.ZipFile(device) as d, zipfile.ZipFile(public) as p, zipfile.ZipFile(app) as outer:
        if set(d.namelist()) != set(p.namelist()) or any(d.read(name) != p.read(name) for name in d.namelist()):
            raise ValueError('public HAP content differs from tested device HAP')
        if rt.digest(outer.read('entry-default.hap')) != counterpart['embeddedHapSha256']:
            raise ValueError('store APP embedded HAP hash differs from review')
        with zipfile.ZipFile(outer.open('entry-default.hap')) as embedded:
            if counterpart['kind'] == 'public-standalone-hap':
                if inventory['hapSha256'] != counterpart['publicHapSha256']:
                    raise ValueError('reviewed HAP is not the public standalone HAP')
            elif counterpart['kind'] == 'store-embedded-hap':
                if inventory['hapSha256'] != counterpart['embeddedHapSha256']:
                    raise ValueError('reviewed HAP is not the store APP embedded HAP')
                if set(p.namelist()) - set(embedded.namelist()) != {'.pages.info'}:
                    raise ValueError('unexpected files removed from store embedded HAP')
                if set(embedded.namelist()) - set(p.namelist()):
                    raise ValueError('unexpected store embedded HAP files')
                for name in embedded.namelist():
                    if name == 'pack.info':
                        if json.loads(embedded.read(name)) != json.loads(p.read(name)):
                            raise ValueError('store pack.info semantics changed')
                    elif embedded.read(name) != p.read(name):
                        raise ValueError('store embedded HAP content differs: ' + name)
            else:
                raise ValueError('unknown counterpart kind')


def apply_review(bom, inventory, report, decision, evidence):
    if (decision.get('kind') != 'C-hash-bound-engineering-review'
            or decision.get('hapSha256') != inventory['hapSha256']
            or report.get('hapSha256') != inventory['hapSha256']):
        raise ValueError('review does not match actual HAP')
    for key, obj in [('draftCanonicalSha256', bom), ('reportCanonicalSha256', report)]:
        if decision.get(key) != rt.digest(json.dumps(obj, sort_keys=True).encode()):
            raise ValueError('review input changed: ' + key)
    if decision.get('publicDistributionApproved') is not False or decision.get('releaseApproved') is not False:
        raise ValueError('this review cannot authorize public or team release')
    for item in decision['evidence']:
        path = PurePosixPath(item['file'])
        if path.is_absolute() or '..' in path.parts or '\\' in item['file']:
            raise ValueError('unsafe evidence path')
        if rt.file_hash(evidence / path) != item['sha256']:
            raise ValueError('review evidence bytes changed')
    notices = decision.get('externalNotices')
    if notices and not any(r['file'] == notices['filename'] and r['sha256'] == notices['sha256'] for r in decision['evidence']):
        raise ValueError('external notices must be hash-bound delivery material')
    acceptance = load(evidence / decision['acceptanceRecord'])
    if decision.get('acceptanceMode') == 'equivalent-device-counterpart':
        validate_equivalent_device_acceptance(acceptance, inventory, decision, evidence)
    elif (acceptance.get('hapSha256') != inventory['hapSha256']
            or acceptance.get('independentWindowsBaselineChecksPassed') != 12
            or not all(acceptance.get(k) is True for k in ['installationPassed', 'coreReadyPassed',
                'realFiveStagePassed', 'gpxJsonLogSystemPickerExportPassed',
                'completedJobProcessRestartRecoveryPassed'])):
        raise ValueError('same-HAP physical acceptance is incomplete')
    if decision['acceptanceRecord'] not in {r['file'] for r in decision['evidence']}:
        raise ValueError('acceptance must be hash-bound evidence')
    findings = {f['id'] for f in report['findings']}
    dispositions = decision['findingDispositions']
    if (len(dispositions) != len(findings) or {d['id'] for d in dispositions} != findings
            or any(d['status'] not in ('closed', 'accepted-observation') or not d.get('reason') for d in dispositions)):
        raise ValueError('every finding requires an explicit disposition')
    result = copy.deepcopy(bom)
    nonfiles = {r['bom-ref']: r for r in result['components'] if r['type'] != 'file'}
    decisions = decision['components']
    if len(decisions) != len(nonfiles) or {r['ref'] for r in decisions} != set(nonfiles):
        raise ValueError('every actual logical component requires review')
    actual = {r['path']: r for r in inventory['files']}
    aliases = {}
    removed = set()
    declaration_only = set()
    for row in decisions:
        ref = row['ref']
        if not row.get('reason'):
            raise ValueError('component decision reason required')
        action = row['action']
        if action == 'merge':
            target = row['into']
            if target not in nonfiles or target == ref:
                raise ValueError('invalid merge target')
            aliases[ref] = target
            if row.get('declarationOnly'):
                declaration_only.add(ref)
            continue
        if action == 'exclude':
            if not row.get('evidenceFiles') or not set(row['evidenceFiles']) <= {x['file'] for x in decision['evidence']}:
                raise ValueError('component exclusion needs bound evidence')
            removed.add(ref)
            continue
        if action != 'reviewed' or not row.get('licenseFiles') or not row.get('licenses'):
            raise ValueError('reviewed component needs license text and conclusion')
        entry = nonfiles[ref]
        for text in row['licenseFiles']:
            if text['path'] not in actual or actual[text['path']]['sha256'] != text['sha256']:
                raise ValueError('reviewed license does not match actual HAP')
        entry['licenses'] = row['licenses']
        if row.get('versionStatus') == 'unverified':
            if 'version' in entry:
                put(entry, originalVersionDeclaration=entry.pop('version'))
        put(entry, distributionReview='reviewed', reviewScope=decision['scope'],
            reviewReason=row['reason'], versionStatus=row.get('versionStatus', 'package-declared'))
        # Replace draft wording; keep original source declarations as observations.
        put(entry, licenseEvidence='explicit engineering review with actual-HAP license hashes')
        entry['properties'] = [p for p in entry['properties'] if p['name'] != 'gsas:licenseFile']
        entry['properties'] += [{'name': 'gsas:licenseFile', 'value': x['path']} for x in row['licenseFiles']]
    if set(aliases.values()) & (set(aliases) | removed):
        raise ValueError('merge chains or excluded merge targets are not allowed')
    result['components'] = [r for r in result['components'] if r['bom-ref'] not in set(aliases) | removed]
    edges = {}
    for edge in result['dependencies']:
        ref = aliases.get(edge['ref'], edge['ref'])
        if ref in removed:
            continue
        targets = {aliases.get(t, t) for t in edge.get('dependsOn', []) if t not in removed | declaration_only}
        edges.setdefault(ref, set()).update(targets - {ref})
    for row in decisions:
        if row['action'] == 'reviewed':
            edges.setdefault(row['ref'], set()).update('file:' + x['path'] for x in row['licenseFiles'])
    # Containment/ownership is not a dependency back from a file to itself.
    contains = {}
    for owner, targets in edges.items():
        if not owner.startswith('file:'):
            for target in targets:
                if target.startswith('file:'):
                    contains.setdefault(target, set()).add(owner)
    for ref, targets in edges.items():
        if ref.startswith('file:'):
            targets.difference_update(contains.get(ref, set()))
    native_record = decision.get('nativeDependencyRecord')
    native_paths = {f['path'] for f in inventory['files'] if f['path'].startswith('libs/')}
    if native_paths and not native_record:
        raise ValueError('native dependency evidence required')
    if native_record:
        if native_record not in {r['file'] for r in decision['evidence']}:
            raise ValueError('native dependency record must be hash bound')
        native = load(evidence / native_record)
        if native.get('hapSha256') != inventory['hapSha256'] or native.get('unmatchedNames'):
            raise ValueError('native dependency graph is foreign or unresolved')
        libraries = native['libraries']
        if len(libraries) != len(native_paths) or {r['path'] for r in libraries} != native_paths:
            raise ValueError('native dependency inventory incomplete')
        for lib in libraries:
            if actual[lib['path']]['sha256'] != lib['sha256']:
                raise ValueError('native library bytes changed')
        platform = set()
        for edge in native['edges']:
            ref = 'file:' + edge['from']
            if edge['from'] not in native_paths:
                raise ValueError('native edge origin absent')
            if edge['status'] == 'packaged-filename':
                target = edge['packagedTarget']
                if target not in native_paths or PurePosixPath(target).name != edge['needed']:
                    raise ValueError('native dependency target mismatch')
                edges.setdefault(ref, set()).add('file:' + target)
            elif edge['status'] == 'sdk-filename-only':
                target = 'platform:' + edge['needed']
                platform.add(edge['needed'])
                edges.setdefault(ref, set()).add(target)
            else:
                raise ValueError('unresolved native dependency')
        for name in sorted(platform):
            result['components'].append({'bom-ref': 'platform:' + name, 'type': 'library', 'name': name,
                'scope': 'excluded', 'properties': [
                    {'name': 'gsas:distribution', 'value': 'not packaged; SDK filename observation only'},
                    {'name': 'gsas:versionEvidence', 'value': 'no OS library version or license inferred'},
                    {'name': 'gsas:runtimeScope', 'value': 'specific API23 sample acceptance, not universal symbol resolution'}]})
            edges['platform:' + name] = set()
    result['dependencies'] = [{'ref': r, 'dependsOn': sorted(t)} for r, t in sorted(edges.items())]
    distribution_review = ('reviewed-for-app-gallery-candidate' if decision.get('acceptanceMode')
                           == 'equivalent-device-counterpart' else 'reviewed-for-specified-internaltesting-delivery')
    put(result['metadata'], draft='false', engineeringReview='complete',
        distributionReview=distribution_review,
        thirdPartyReview='reviewed',
        releaseApproved='false', publicDistributionApproved='false',
        reviewCanonicalSha256=rt.digest(json.dumps(decision, sort_keys=True).encode()),
        scope=decision['scope'])
    validate_graph(result, inventory)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ['hap', 'manifest', 'draft', 'report', 'review', 'evidence-dir', 'output']:
        p.add_argument('--' + flag, type=Path, required=True)
    a = p.parse_args()
    try:
        if a.output.exists():
            raise ValueError('output must be new')
        inventory = rt.audit_hap(a.hap, load(a.manifest), 'development')
        bom = apply_review(load(a.draft), inventory, load(a.report), load(a.review), a.evidence_dir)
        a.output.write_bytes((json.dumps(bom, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print(json.dumps({'files': len(inventory['files']), 'engineeringReview': 'complete',
                          'publicDistributionApproved': False, 'sbomSha256': rt.file_hash(a.output)}))
    except (ValueError, OSError, KeyError) as e:
        p.exit(1, f'Final SBOM rejected: {e}\n')


if __name__ == '__main__':
    main()
