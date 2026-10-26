"""Static documentation and source inspection; never executes project code."""
import ast
import fnmatch
import json
import re
from pathlib import Path

I18N = (
    'supports multiple languages', 'multiple languages supported', 'multiple language support',
    'available in multiple languages', 'supports several languages', 'supports many languages',
    'supports other languages', 'supports translations', 'translation support',
    'translations supported', 'translations available', 'translation system', 'supports translation',
    'localized', 'localised', 'localization support', 'localisation support',
    'internationalization support', 'internationalisation support', 'i18n support',
    'supports i18n', 'multilingual support', 'is multilingual', 'fully translated',
    'translated into multiple languages',
)
NOI18N = (
    'no translation support', 'no translations', 'does not support translations',
    'does not support translation', 'not translated', 'never translated',
    'does not support multiple languages', 'no localization support', 'no localisation support',
    'no i18n support', 'does not support i18n', 'not localized', 'not localised',
    'no multilingual support', 'not multilingual', 'english only', 'only available in english',
    'available in english only', 'english only support',
)
CATALOG_DIRS = {'locale', 'locales', 'lang', 'langs', 'i18n', 'translations'}
GETTEXT = {'gettext', 'ngettext', 'npgettext', 'dgettext', 'pgettext'}


def pattern(phrases):
    return re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in sorted(phrases, key=len, reverse=True)) + r')\b')


def doc_claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.match(r'^\s{0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$', line):
                fence = None
            lines.append('')
        elif match:
            fence = match.group(1)
            lines.append('')
        else:
            lines.append(line)
    result = set()
    for para in re.split(r'\n\s*\n', '\n'.join(lines)):
        normalized = ' '.join(para.lower().replace('-', ' ').split())
        negative = pattern(NOI18N)
        if negative.search(normalized):
            result.add('noi18n')
        normalized = negative.sub(' ', normalized)
        if pattern(I18N).search(normalized):
            result.add('i18n')
    return result


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + '.' + node.attr if base else ''
    return ''


def source_evidence(text, filename):
    tree = ast.parse(text, filename=filename)
    aliases = {}
    gettext_modules = set()
    gettext_functions = set()
    babel = False
    fluent = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                binding = item.asname or item.name.split('.')[0]
                aliases[binding] = item.name if item.asname else binding
                if item.name == 'gettext':
                    gettext_modules.add(binding)
                babel |= item.name == 'babel' or item.name.startswith('babel.')
                fluent |= item.name.startswith('fluent.')
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for item in node.names:
                binding = item.asname or item.name
                aliases[binding] = module + '.' + item.name
                if item.name in GETTEXT:
                    gettext_functions.add(binding)
            babel |= module == 'babel' or module.startswith('babel.')
            fluent |= module.startswith('fluent.')
    kinds = set()
    qt = install = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func)
        head, _, tail = name.partition('.')
        resolved = aliases.get(head, head) + ('.' + tail if tail else '')
        if name in gettext_functions or (head in gettext_modules and tail):
            kinds.add('gettext')
        if babel and resolved.startswith('babel.'):
            kinds.add('babel')
        if fluent and resolved.endswith('FluentBundle'):
            kinds.add('fluent')
        qt |= resolved.endswith('QTranslator')
        install |= isinstance(node.func, ast.Attribute) and node.func.attr == 'installTranslator'
    if qt and install:
        kinds.add('qt')
    return kinds


def audit(root, ignores=()):
    root = Path(root)
    if not root.is_dir():
        raise ValueError('ROOT must be a directory')
    evidence = []
    claims = []

    def walk(directory):
        for path in sorted(directory.iterdir()):
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or any(fnmatch.fnmatchcase(rel, g) for g in ignores):
                continue
            if path.is_dir():
                yield from walk(path)
            elif path.is_file():
                yield path, rel

    for path, rel in walk(root):
        if path.name == '.env' or path.name.startswith('.env.'):
            continue
        parts = Path(rel).parts
        testing = 'tests' in parts
        if rel == 'README.md' or ('docs' in parts[:-1] and path.suffix == '.md'):
            for family in sorted(doc_claims(path.read_text(encoding='utf-8'))):
                claims.append({'family': family, 'path': rel})
        if testing:
            continue
        kinds = set()
        if path.suffix == '.py' and not path.name.startswith('test_'):
            kinds = source_evidence(path.read_text(encoding='utf-8'), rel)
        elif path.suffix in {'.po', '.mo'}:
            kinds.add('catalog')
        elif path.suffix == '.json' and CATALOG_DIRS.intersection(parts[:-1]):
            try:
                obj = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, UnicodeError):
                obj = None
            if isinstance(obj, dict) and any(
                isinstance(v, str) or (isinstance(v, dict) and any(isinstance(w, str) for w in v.values()))
                for v in obj.values()
            ):
                kinds.add('json-catalog')
        evidence.extend({'kind': kind, 'path': rel} for kind in sorted(kinds))
    findings = []
    for family in ('i18n', 'noi18n'):
        candidates = [c for c in claims if c['family'] == family]
        false = not evidence if family == 'i18n' else bool(evidence)
        if candidates and false:
            chosen = min(candidates, key=lambda c: ('tests' in Path(c['path']).parts, c['path']))
            findings.append({'rule': 'documented-' + ('i18n' if family == 'i18n' else 'no-i18n') + '-claim-false',
                             'severity': 'MEDIUM' if 'tests' in Path(chosen['path']).parts else 'HIGH',
                             'path': chosen['path']})
    return {'status': 'FAIL' if findings else 'PASS', 'evidence': evidence, 'claims': claims, 'findings': findings}
