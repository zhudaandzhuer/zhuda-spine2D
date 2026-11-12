#!/usr/bin/env python3
"""Read-only Spine JSON/Atlas/export checks; optional Pillow alpha inspection."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def page_names(text):
    lines = text.replace('\r', '').splitlines()
    pages = []
    for index, line in enumerate(lines):
        name = line.strip()
        if not name or ':' in name:
            continue
        following = next((s.strip() for s in lines[index + 1:] if s.strip()), '')
        if re.match(r'^size\s*:', following):
            pages.append(name)
    return list(dict.fromkeys(pages))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(args):
    source, atlas = args.json.resolve(), args.atlas.resolve()
    raw = json.loads(source.read_text(encoding='utf-8-sig'))
    errors, warnings = [], []
    if not isinstance(raw, dict) or not isinstance(raw.get('skeleton'), dict):
        raise ValueError('JSON is not a Spine skeleton object')
    names = set()
    for bone in raw.get('bones', []):
        name = bone.get('name')
        if not name or name in names:
            errors.append(f'Empty/duplicate bone: {name}')
        if bone.get('parent') and bone['parent'] not in names:
            errors.append(f'Parent missing or ordered after child: {name}')
        names.add(name)
    slots = set()
    for slot in raw.get('slots', []):
        if slot.get('name') in slots:
            errors.append(f'Duplicate slot: {slot.get("name")}')
        if slot.get('bone') not in names:
            errors.append(f'Slot references missing bone: {slot.get("name")}')
        slots.add(slot.get('name'))
    clips = raw.get('animations', {})
    for name in args.required_clips:
        if name not in clips:
            errors.append(f'Missing required animation: {name}')
    text = atlas.read_text(encoding='utf-8-sig')
    pages = page_names(text)
    if not pages:
        errors.append('No Atlas pages detected (this parser expects page size metadata)')
    images = []
    try:
        from PIL import Image
    except ImportError:
        Image = None
        warnings.append('Pillow unavailable: alpha inspection was skipped')
    for name in pages:
        path = (atlas.parent / name).resolve()
        if not path.is_relative_to(atlas.parent):
            errors.append(f'Atlas page escapes package: {name}')
            continue
        if not path.is_file():
            errors.append(f'Missing Atlas page: {name}')
            continue
        info = {'page': name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
        if Image:
            with Image.open(path) as image:
                rgba = image.convert('RGBA')
                hist = rgba.getchannel('A').histogram()
                info.update(mode=image.mode, size=list(image.size), transparentPixels=hist[0], semitransparentPixels=sum(hist[1:255]), opaquePixels=hist[255])
                if not hist[0]:
                    warnings.append(f'{name}: no fully transparent pixels; inspect intended transparency')
        images.append(info)
    export = None
    if args.export_zip:
        with zipfile.ZipFile(args.export_zip) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f'ZIP CRC failed: {bad}')
            candidates = []
            for name in archive.namelist():
                if name.endswith('.json'):
                    try:
                        document = json.loads(archive.read(name))
                        if isinstance(document, dict) and isinstance(document.get('skeleton'), dict):
                            candidates.append((name, document))
                    except (ValueError, UnicodeError):
                        pass
            if args.export_json:
                candidates = [item for item in candidates if item[0] == args.export_json]
            if len(candidates) != 1:
                errors.append('Export must contain one skeleton JSON; use --export-json to select an exact entry')
            else:
                name, other = candidates[0]
                fields = ['bones', 'slots', 'skins', 'animations', 'ik', 'transform', 'path', 'physics', 'events']
                differences = [key for key in fields if raw.get(key) != other.get(key)]
                if differences:
                    errors.append('Export structure differs: ' + ', '.join(differences))
                export = {'entry': name, 'comparedFields': fields, 'differentFields': differences}
    return {'ok': not errors, 'json': str(source), 'jsonSha256': digest(source), 'atlasSha256': digest(atlas), 'spineVersion': raw['skeleton'].get('spine'), 'bones': len(raw.get('bones', [])), 'slots': len(raw.get('slots', [])), 'animations': list(clips), 'pages': images, 'export': export, 'errors': errors, 'warnings': warnings, 'scope': 'Static package/alpha/structure only. No visual or animation quality claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, required=True)
    parser.add_argument('--atlas', type=Path, required=True)
    parser.add_argument('--required-clips', nargs='*', default=[])
    parser.add_argument('--export-zip', type=Path)
    parser.add_argument('--export-json')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('x', encoding='utf-8') as stream:
                stream.write(output + '\n')
        print(output)
        return 0 if result['ok'] else 1
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f'Audit failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
