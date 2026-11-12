#!/usr/bin/env python3
"""Conservative single-page, unrotated, untrimmed atlas repack. Copies pixels and padding exactly."""
import argparse, json, shutil
from pathlib import Path
from PIL import Image
from spine_common import atlas, rect, references, dump


def pack(items, width, height):
    free, positions = [(0, 0, width, height)], {}
    for name, w, h in items:
        options = [(min(rw-w, rh-h), max(rw-w, rh-h), y, x) for x, y, rw, rh in free if rw >= w and rh >= h]
        if not options:
            return None
        _, _, y, x = min(options)
        positions[name] = x, y
        new = []
        for fx, fy, fw, fh in free:
            if x >= fx+fw or x+w <= fx or y >= fy+fh or y+h <= fy:
                new.append((fx, fy, fw, fh))
                continue
            if x > fx: new.append((fx, fy, x-fx, fh))
            if x+w < fx+fw: new.append((x+w, fy, fx+fw-x-w, fh))
            if y > fy: new.append((fx, fy, fw, y-fy))
            if y+h < fy+fh: new.append((fx, y+h, fw, fy+fh-y-h))
        free = [r for i, r in enumerate(new) if not any(i != k and r[0] >= q[0] and r[1] >= q[1]
                and r[0]+r[2] <= q[0]+q[2] and r[1]+r[3] <= q[1]+q[3]
                and (r != q or i > k) for k, q in enumerate(new))]
    return positions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skeleton', type=Path, required=True)
    p.add_argument('--atlas', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--padding', type=int, default=4)
    p.add_argument('--max-size', type=int, default=4096)
    p.add_argument('--step', type=int, default=128)
    p.add_argument('--keep-region', action='append', default=[])
    args = p.parse_args()
    if args.out_dir.exists() or args.padding < 0 or args.step < 1 or args.max_size < 1:
        p.error('Output directory must be new; padding>=0, step/max-size>0')
    pages = atlas(args.atlas)
    if len(pages) != 1:
        p.error('Only single-page atlases supported')
    page = pages[0]
    if Path(page['name']).name != page['name']:
        p.error('Page image must be a plain filename')
    if set(page['fields']) - {'size', 'format', 'filter', 'repeat', 'pma'}:
        p.error('Unsupported page fields; use a full-format packer')
    if Path(page['name']).suffix.lower() != '.png':
        p.error('This helper only exports lossless PNG pages')
    image = Image.open(args.atlas.parent/page['name']).convert('RGBA')
    regions = {}
    for r in page['regions']:
        fields = r['fields']
        if set(fields) - {'bounds', 'xy', 'size', 'rotate', 'offset', 'orig', 'index'}:
            p.error('Unsupported region metadata: ' + r['name'])
        if fields.get('rotate', 'false') not in ('false', '0') or fields.get('index', '-1') != '-1':
            p.error('Rotated/indexed regions require a full-format packer')
        box = rect(r)
        if fields.get('offset', '0,0').replace(' ', '') != '0,0':
            p.error('Trim offsets unsupported')
        if 'orig' in fields and tuple(map(int, fields['orig'].split(','))) != box[2:]:
            p.error('Trimmed original size unsupported')
        if r['name'] in regions:
            p.error('Duplicate region name')
        regions[r['name']] = box
    paths, unresolved = references(json.loads(args.skeleton.read_text()))
    if unresolved:
        p.error('Unresolved linked mesh or sequence: audit with a full runtime first')
    paths |= set(args.keep_region)
    if not paths or paths - set(regions):
        p.error('Empty selection or missing required atlas regions')
    pad = args.padding
    for n in paths:
        x, y, w, h = regions[n]
        if x < pad or y < pad or x+w+pad > image.width or y+h+pad > image.height:
            p.error('Source padding exceeds page: ' + n)
        for other, (ox, oy, ow, oh) in regions.items():
            if other != n and x-pad < ox+ow and x+w+pad > ox and y-pad < oy+oh and y+h+pad > oy:
                p.error('Padding overlaps source region: ' + n + ' / ' + other)
    items = sorted([(n, regions[n][2]+pad*2, regions[n][3]+pad*2) for n in paths],
                   key=lambda v: (-max(v[1:]), -v[1]*v[2], v[0]))
    sizes = list(range(args.step, args.max_size+1, args.step))
    if args.max_size not in sizes: sizes.append(args.max_size)
    area = sum(w*h for _, w, h in items)
    candidates = sorted([(w,h) for w in sizes for h in sizes if w*h >= area
                         and w >= max(i[1] for i in items) and h >= max(i[2] for i in items)],
                        key=lambda wh: (wh[0]*wh[1], abs(wh[0]-wh[1])))
    result = None
    for W, H in candidates:
        pos = pack(items, W, H)
        if pos is not None:
            result = W, H, pos
            break
    if result is None:
        p.error('Could not pack within max-size')
    W, H, pos = result
    output = Image.new('RGBA', (W, H))
    lines = [page['name'], f'size:{W},{H}']
    lines += [f'{k}:{v}' for k,v in page['fields'].items() if k != 'size']
    for r in page['regions']:
        n = r['name']
        if n not in paths: continue
        x,y,w,h = regions[n]; nx,ny = pos[n]
        output.paste(image.crop((x-pad,y-pad,x+w+pad,y+h+pad)), (nx,ny))
        lines += [n, f'bounds:{nx+pad},{ny+pad},{w},{h}']
    args.out_dir.mkdir(parents=True)
    output.save(args.out_dir/page['name'], optimize=True)
    (args.out_dir/args.atlas.name).write_text('\n'.join(lines)+'\n')
    shutil.copy2(args.skeleton, args.out_dir/args.skeleton.name)
    report = {'before_size': list(image.size), 'after_size': [W,H], 'before_regions': len(regions),
              'after_regions': len(paths), 'before_rgba8_bytes': image.width*image.height*4,
              'after_rgba8_bytes': W*H*4, 'padding': pad, 'visual_verdict': 'NOT_EVALUATED',
              'required': 'Check target NPOT/filter support, then native visual regression'}
    dump(args.out_dir/'repack-report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
