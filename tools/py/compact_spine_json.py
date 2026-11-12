#!/usr/bin/env python3
"""Lossless numeric/deform representation compaction; does not simplify motion curves."""
import argparse, json
from pathlib import Path
from spine_common import deform_keys, dump, new_outputs


def normalize(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, list):
        return [normalize(x) for x in v]
    if isinstance(v, dict):
        return {k: normalize(x) for k, x in v.items()}
    return v


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--drop-identical', action='append', default=[], metavar='REMOVE=KEEP',
                   help='Only after checking runtime callers; refuses nonidentical animations')
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    if args.input.resolve() == args.out.resolve() or args.out.exists():
        p.error('Use a new output file; inputs and existing outputs are never overwritten')
    new_outputs([args.input], [args.out, args.report])
    data = json.loads(args.input.read_text())
    removed, zeros, keys = [], 0, 0
    for pair in args.drop_identical:
        if pair.count('=') != 1:
            p.error('Expected REMOVE=KEEP')
        remove, keep = pair.split('=')
        anims = data.get('animations', {})
        if remove == keep or remove not in anims or keep not in anims or anims[remove] != anims[keep]:
            p.error('Animations must exist, be distinct, and have identical structures: ' + pair)
        del anims[remove]
        removed.append(remove)
    for anim in data.get('animations', {}).values():
        for key in deform_keys(anim):
            keys += 1
            v = key.get('vertices', [])
            lo, hi = 0, len(v)
            while lo < hi and v[lo] == 0:
                lo += 1
            while hi > lo and v[hi - 1] == 0:
                hi -= 1
            zeros += len(v) - (hi - lo)
            if hi == lo:
                key.pop('vertices', None)
                key.pop('offset', None)
            elif lo or hi < len(v):
                key['vertices'] = v[lo:hi]
                key['offset'] = key.get('offset', 0) + lo
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(normalize(data), ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    result = {'before_bytes': args.input.stat().st_size, 'after_bytes': args.out.stat().st_size,
              'removed_animations': removed, 'retained_deform_keys': keys, 'zero_components_removed': zeros,
              'visual_verdict': 'NOT_EVALUATED', 'required': 'Native visual + mixing regression before release'}
    if args.report:
        dump(args.report, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
