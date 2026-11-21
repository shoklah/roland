#!/usr/bin/env python3
"""Find a kit by name and print its manifest, with every file it names as a full path.

show: read <kits>/<name>/kit.json and print {"status": "ok", "format", "name", "version", "folder", "applies_when",
      "design", "guidance", "checklist", "checks": [{"name", "command"}], "bindings": [{"read", "tag"}], "stacks"}.
      design, guidance, checklist and each read are full paths under folder, or null when the manifest leaves the key
      out; {kit} in a check's command becomes folder. A check or binding carrying "stack" is listed only when --stack
      names that stack.

list: print {"status": "ok", "kits": [{"name", "applies_when"}], "refused": [{"name", "reason"}]}, both sorted by
      name: every folder or link under <kits> not starting with "." that show accepts, and show's reason for each
      other. A missing <kits> lists nothing; a <kits> that is not a folder is refused.

Prints one JSON object. Exit codes: done 0, a kit that is missing or malformed, or a <kits> that is not a folder, 1 ({"status": "refused", "reason"}),
usage error 2 (on stderr, nothing on stdout). The lookup reads only; it never runs a check.

Usage: kit.py show NAME [--stack STACK] [--kits DIR]
       kit.py list [--kits DIR]
"""
import argparse
import json
import os
import sys

FORMAT = 1


class Refused(Exception):
    pass


def parse_args(argv):
    parser = argparse.ArgumentParser(prog='kit.py', description='Find a kit by name and print its manifest.')
    subs = parser.add_subparsers(dest='command', required=True)
    for name, text in (('show', "print a kit's manifest with full paths"),
                       ('list', 'list every kit with its applies_when, and each kit show would refuse')):
        sub = subs.add_parser(name, help=text, description=text)
        if name == 'show':
            sub.add_argument('name', help='the kit, a folder under --kits')
            sub.add_argument('--stack', help="also list the kit's entries for this stack")
        sub.add_argument('--kits', default=os.path.expanduser('~/.claude/kits'),
                         help='the folder holding the kits (default: ~/.claude/kits)')
    return parser.parse_args(argv)


def kit_file(folder, rel, key):
    """The full path of a file the manifest names, or a refusal when it is missing."""
    if not isinstance(rel, str) or not rel:
        raise Refused('%s in kit.json must name a file' % key)
    path = os.path.join(folder, rel)
    if not os.path.isfile(path):
        raise Refused('%s names %s, which the kit does not hold' % (key, rel))
    return path


def entries(manifest, key, required):
    """The manifest's list of objects under key, each carrying the required string."""
    items = manifest.get(key, [])
    if not isinstance(items, list) or not all(isinstance(i, dict) and isinstance(i.get(required), str)
                                              for i in items):
        raise Refused('%s in kit.json must be a list of objects, each with a "%s"' % (key, required))
    return items


def show(kits, name, stack=None):
    folder = os.path.join(kits, name)
    if not os.path.isdir(folder):
        raise Refused('no kit named %s in %s' % (name, kits))
    try:
        with open(os.path.join(folder, 'kit.json')) as f:
            manifest = json.load(f)
    except (OSError, ValueError) as e:
        raise Refused('could not read %s/kit.json: %s' % (name, e))
    if not isinstance(manifest, dict):
        raise Refused('kit.json of %s is not a JSON object' % name)
    if manifest.get('format') != FORMAT:
        raise Refused('kit.json has format %r, and this lookup reads format %d' % (manifest.get('format'), FORMAT))
    if manifest.get('name') != name:
        raise Refused('kit.json has name %r, not its folder name %s' % (manifest.get('name'), name))
    for key in ('version', 'applies_when'):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise Refused('kit.json has no %s' % key)
    stacks = manifest.get('stacks', [])
    if not isinstance(stacks, list) or not all(isinstance(s, str) for s in stacks):
        raise Refused('stacks in kit.json must be a list of names')

    files = {key: kit_file(folder, manifest[key], key) if key in manifest else None
             for key in ('design', 'guidance', 'checklist')}
    checks = entries(manifest, 'checks', 'command')
    bindings = entries(manifest, 'bindings', 'read')
    reads = [kit_file(folder, b['read'], 'bindings') for b in bindings]

    def listed(entry):
        return 'stack' not in entry or entry['stack'] == stack

    return {'status': 'ok', 'format': FORMAT, 'name': name, 'version': manifest['version'], 'folder': folder,
            'applies_when': manifest['applies_when'], **files,
            'checks': [{'name': c.get('name'), 'command': c['command'].replace('{kit}', folder)}
                       for c in checks if listed(c)],
            'bindings': [{'read': read, 'tag': b.get('tag')} for b, read in zip(bindings, reads) if listed(b)],
            'stacks': stacks}


def list_kits(kits):
    if not os.path.lexists(kits):
        names = []
    elif not os.path.isdir(kits):
        raise Refused('%s is not a folder' % kits)
    else:
        try:
            entries = os.listdir(kits)
        except OSError as e:
            raise Refused('could not read %s: %s' % (kits, e))
        names = sorted(n for n in entries if not n.startswith('.')
                       and (os.path.isdir(os.path.join(kits, n)) or os.path.islink(os.path.join(kits, n))))
    listed, refused = [], []
    for name in names:
        try:
            listed.append({'name': name, 'applies_when': show(kits, name)['applies_when']})
        except Refused as e:
            refused.append({'name': name, 'reason': str(e)})
    return {'status': 'ok', 'kits': listed, 'refused': refused}


def main(argv):
    opts = parse_args(argv)
    try:
        result = show(opts.kits, opts.name, opts.stack) if opts.command == 'show' else list_kits(opts.kits)
    except Refused as e:
        print(json.dumps({'status': 'refused', 'reason': str(e)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
