"""Small, conservative Spine helpers; no I/O mutation on import."""
import json
from pathlib import Path


def skins(data):
    raw = data.get('skins', [])
    if isinstance(raw, dict):
        return [(name, slots) for name, slots in raw.items()]
    return [(s.get('name', 'default'), s.get('attachments', {})) for s in raw]


def attachments(data):
    for skin, slots in skins(data):
        for slot, values in slots.items():
            for name, value in values.items():
                yield skin, slot, name, value


def references(data):
    paths, unresolved = set(), []
    lookup = {(skin, slot, name): a for skin, slot, name, a in attachments(data)}
    def resolve(skin, slot, name, trail):
        key = (skin, slot, name)
        if key in trail or key not in lookup:
            unresolved.append({'attachment': list(key), 'reason': 'missing/cyclic linked parent'})
            return
        a = lookup[key]
        kind = a.get('type', 'region')
        if kind not in ('region', 'mesh', 'linkedmesh', 'skinnedmesh', 'weightedmesh'):
            return
        if a.get('sequence'):
            unresolved.append({'attachment': list(key), 'reason': 'sequence requires runtime expansion'})
        paths.add(a.get('path', name))
        if a.get('parent'):
            unresolved.append({'attachment': list(key), 'reason': 'linked mesh: verify runtime parent and texture lookup'})
            resolve(a.get('skin', skin), slot, a['parent'], trail | {key})
    for key in lookup:
        resolve(*key, set())
    return paths, unresolved


def atlas(path):
    """Parse named pages/regions while retaining fields. Blank separates pages."""
    pages, page, region = [], None, None
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line:
            page = region = None
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            target = region if region is not None else page
            if target is None:
                raise ValueError('Atlas field before page')
            target['fields'][key.strip()] = value.strip()
        elif page is None:
            page = {'name': line, 'fields': {}, 'regions': []}
            pages.append(page)
        else:
            region = {'name': line, 'fields': {}}
            page['regions'].append(region)
    return pages


def rect(region):
    f = region['fields']
    if 'bounds' in f:
        values = [int(v) for v in f['bounds'].split(',')]
    else:
        values = [int(v) for v in (f['xy'] + ',' + f['size']).split(',')]
    if len(values) != 4 or min(values[:2]) < 0 or min(values[2:]) <= 0:
        raise ValueError('Invalid region bounds: ' + region['name'])
    return tuple(values)


def deform_keys(anim):
    for slots in anim.get('attachments', {}).values():
        for ats in slots.values():
            for tracks in ats.values():
                yield from tracks.get('deform', [])
    for slots in anim.get('deform', {}).values():
        for ats in slots.values():
            for keys in ats.values():
                yield from keys


def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def new_outputs(inputs, outputs):
    """Preflight every destination before writing anything. Reject aliases/existing files."""
    source = [Path(p).resolve() for p in inputs]
    dest = [Path(p) for p in outputs if p is not None]
    seen = set()
    for p in dest:
        resolved = p.resolve()
        if resolved in source or resolved in seen or p.exists() or p.is_symlink():
            raise ValueError('Output must be new and distinct from every input/output: ' + str(p))
        seen.add(resolved)
