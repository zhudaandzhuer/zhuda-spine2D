#!/usr/bin/env python3
"""Read-only inventory. Unreferenced atlas regions are candidates, not deletion approval."""
import argparse, collections, hashlib, json
from pathlib import Path
from spine_common import attachments, references, atlas, dump, new_outputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('skeleton', type=Path)
    p.add_argument('--atlas', type=Path)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    new_outputs([args.skeleton] + ([args.atlas] if args.atlas else []), [args.out])
    data = json.loads(args.skeleton.read_text())
    paths, unresolved = references(data)
    groups, animations = collections.defaultdict(list), {}
    for name, a in data.get('animations', {}).items():
        canonical = json.dumps(a, sort_keys=True, separators=(',', ':')).encode()
        groups[hashlib.sha256(canonical).hexdigest()].append(name)
        animations[name] = {'compact_bytes': len(json.dumps(a, separators=(',', ':')).encode())}
    result = {'source': str(args.skeleton.resolve()), 'json_bytes': args.skeleton.stat().st_size,
              'spine_version': data.get('skeleton', {}).get('spine'),
              'bones': len(data.get('bones', [])), 'slots': len(data.get('slots', [])),
              'attachments': len(list(attachments(data))), 'image_paths': sorted(paths),
              'unresolved': unresolved, 'animations': animations,
              'identical_animation_groups': [g for g in groups.values() if len(g) > 1],
              'external_reference_audit_required': True}
    if args.atlas:
        pages = atlas(args.atlas)
        names = [r['name'] for page in pages for r in page['regions']]
        result.update({'pages': [{'name': x['name'], 'fields': x['fields'], 'regions': len(x['regions'])} for x in pages],
                       'unused_region_candidates': sorted(set(names) - paths),
                       'missing_regions': sorted(paths - set(names)),
                       'duplicate_region_names': [n for n, count in collections.Counter(names).items() if count > 1]})
    if args.out:
        dump(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
