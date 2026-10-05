#!/usr/bin/env python3
"""Missing public DE words only: extract, resume translation, append reviewed rows.

Translation is deliberately a separate command and needs --allow-network. Run it
only after the import and code changes have been pushed. Existing dictionary
entries and reviewed records are never overwritten; no legacy cache is required.
"""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
import urllib.parse
import urllib.request

from harvest_filters import looks_german

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIELDS = ('word', 'translation', 'note', 'status')
VALID_STATUS = {'new', 'known', 'learning', 'ignored'}
DEVELOPER = re.compile(r'\[(?:PH|DNT|NYI|UNUSED)\]|\b(?:DND|DNT|NYI|UNUSED|Deprecated|QADebug|QAEnchant)\b|^(?:Monster\s*-|S\d{2}\s*-|QA(?:Debug|Enchant|Test|[ _-]))', re.I)


def load(path):
    path = pathlib.Path(path)
    if not path.exists():
        return []
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]


def write(path, rows):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def luaq(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\r', '\\r').replace('\n', '\\n').replace('\t', '\\t') + '"'


def name_field(row):
    return row.get('category') == 'name' or row.get('kind') in ('name', 'npc_name', 'item_name', 'spell_name')


def lua_lookup(addon, dictionary, passages, lua='lua'):
    """Execute the existing UI tokenizer/lookup outside WoW, not a regex copy."""
    with tempfile.TemporaryDirectory(prefix='whw-vocabulary-') as folder:
        folder = pathlib.Path(folder)
        source, output, script = (folder / name for name in ('input.lua', 'tokens.tsv', 'lookup.lua'))
        lines = ['local rows = {}']
        # Each function owns its constants, just like build_dictionary_lua.py.
        for start in range(0, len(passages), 2000):
            lines.append(';(function()')
            for i, row in enumerate(passages[start:start + 2000], start + 1):
                name = name_field(row) and row.get('text') == row.get('enText')
                lines.append(f'rows[#rows + 1] = {{ {i}, {luaq(row["text"])}, {str(name).lower()} }}')
            lines.append('end)()')
        lines.append('return rows')
        source.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        script.write_text('''strlower = string.lower
strtrim = function(s) return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", "")) end
time = os.time
GetLocale = function() return "deDE" end
CreateFrame = function() return setmetatable({}, {__index = function() return function() end end}) end
''' + f'dofile({luaq((pathlib.Path(addon) / "Core.lua").resolve().as_posix())})\n'
            + f'dofile({luaq(pathlib.Path(dictionary).resolve().as_posix())})\n'
            + f'local input = dofile({luaq(source.as_posix())})\n'
            + f'local out = assert(io.open({luaq(output.as_posix())}, "wb"))\n'
            + '''local A = WordHunterWoW_Addon
assert(A.RegisterDictionaryProvider("deDE", "incremental-extract", WordHunterWoW_Dictionary_DE))
local words = {}
for _, p in ipairs(input) do
  for _, line in ipairs(A.TextLines(p[2])) do
    for _, token in ipairs(line) do
      local word = A.cleanWord(token)
      local key = A.wordKey(word)
      if key ~= "" then
        local record = words[key]
        if not record then
          record = {count = 0, word = word, token = token, index = p[1], known = A.GetDictionaryEntry(key, "deDE") ~= nil}
          words[key] = record
        end
        record.count = record.count + 1
        if p[3] and not record.nameIndex then record.nameIndex = p[1] end
      end
    end
  end
end
for key, r in pairs(words) do
  out:write(key, "\\t", r.word, "\\t", r.token, "\\t", tostring(r.index), "\\t", tostring(r.count), "\\t", r.known and "1" or "0", "\\t", tostring(r.nameIndex or 0), "\\n")
end
out:close()
''', encoding='utf-8')
        subprocess.run([lua, str(script)], check=True, capture_output=True, text=True, encoding='utf-8')
        result = []
        for line in output.read_text(encoding='utf-8').splitlines():
            key, word, token, index, count, known, name_index = line.split('\t')
            result.append({'key': key, 'word': word, 'token': token, 'count': int(count), 'known': known == '1', 'index': int(index) - 1, 'nameIndex': int(name_index) - 1})
        return result


def excluded_token(row):
    token, key = row['token'], row['key']
    if re.search(r'\{[^}]*\}|\$[A-Za-z]|<(?:name|class|race|klasse|rasse|volk)>', token, re.I):
        return 'player_or_tooltip_macro'
    if any(c in token for c in '{}[]|=') or '/' in key:
        return 'markup_formula_or_variant'
    if not any(c.isalpha() for c in key):
        return 'numeric_or_symbol'
    if len(key) < 2:
        return 'single_letter_or_initial'
    if any(c.isalpha() and 'LATIN' not in unicodedata.name(c, '') for c in key):
        return 'non_latin_script'
    if any(c.isspace() for c in key) or '\ufffd' in key:
        return 'encoding_or_space_artifact'
    if not re.fullmatch(r"[^\W\d_]+(?:[-'’‘][^\W\d_]+)*", key, re.UNICODE):
        return 'number_abbreviation_plural_template_or_punctuation_review'
    return None


def extract(args):
    passages, skipped = [], collections.Counter()
    corpus = [row for path in args.corpus for row in load(path)]
    def identity(row):
        return tuple(str(row.get(k, '')) for k in ('sourceFlavor', 'kind', 'id', 'category'))
    english = {identity(row): row['text'] for row in corpus if row.get('locale') in ('enUS', 'enGB') and isinstance(row.get('text'), str)}
    for row in corpus:
            if row.get('locale') != 'deDE':
                skipped['not_deDE'] += 1
                continue
            text = row.get('text')
            if not isinstance(text, str) or not text.strip():
                skipped['empty_text'] += 1
                continue
            chow_test = row.get('kind') == 'quest' and str(row.get('id')) == '1' and 'Chow' in text
            if row.get('skipVocabulary') or DEVELOPER.search(text) or chow_test:
                skipped['developer_or_ineligible_text'] += 1
                continue
            if not looks_german(text):
                skipped['non_german_passage'] += 1
                continue
            if 'enText' not in row and identity(row) in english:
                row = {**row, 'enText': english[identity(row)]}
            if not name_field(row) and not (row.get('kind') == 'quest' and row.get('category') == 'title') and row.get('enText') == text:
                skipped['untranslated_english_field'] += 1
                continue
            passages.append(row)
    words = lua_lookup(args.addon, args.dictionary, passages, args.lua)
    curated = {r['key']: r for r in load(pathlib.Path(args.dictionary).parent / 'CuratedDE.jsonl') if r.get('translation')}
    candidates, excluded = [], []
    for word in sorted(words, key=lambda r: (-r['count'], r['key'])):
        if word['known']:
            continue
        source = passages[word.pop('index')]
        reason = excluded_token(word)
        row = {k: v for k, v in word.items() if k not in ('known', 'nameIndex')}
        position = source['text'].find(word['token'])
        start = max(0, position - 250)
        row.update({'context': source['text'][start:start + 1000], 'source': {k: v for k, v in source.items() if k != 'text'}, 'action': 'review'})
        if reason:
            row['reason'] = reason
            excluded.append(row)
            continue
        if word['nameIndex'] >= 0:
            name_source = passages[word['nameIndex']]
            row['nameEvidence'] = {'meaning': 'Token occurs in identical German/English name; this is review evidence, not an ignored status.',
                                   'name': name_source['text'], 'source': {k: v for k, v in name_source.items() if k != 'text'}}
        if word['key'] in curated:
            row['curated'] = {k: curated[word['key']][k] for k in FIELDS if k in curated[word['key']]}
        candidates.append(row)
    out = pathlib.Path(args.out)
    write(out / 'candidates.jsonl', candidates)
    write(out / 'excluded.jsonl', excluded)
    summary = {'passages': len(passages), 'tokens': sum(r['count'] for r in words), 'uniqueKeys': len(words),
               'dictionaryCoveredKeys': sum(r['known'] for r in words), 'candidateKeys': len(candidates),
               'candidateKeysWithExistingCuratedGloss': sum('curated' in r for r in candidates),
               'candidateKeysWithNameEvidence': sum('nameEvidence' in r for r in candidates),
               'excludedKeys': len(excluded), 'skippedPassages': dict(skipped),
               'dictionarySha256': hashlib.sha256(pathlib.Path(args.dictionary).read_bytes()).hexdigest(),
               'coreSha256': hashlib.sha256((pathlib.Path(args.addon) / 'Core.lua').read_bytes()).hexdigest(),
               'corpusSha256': {str(path): hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() for path in args.corpus}}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True))


def valid_gloss(row):
    translation = row.get('translation')
    return isinstance(translation, str) and bool(translation.strip()) and len(translation) <= 120 and '\ufffd' not in translation and '\n' not in translation and '\r' not in translation


def successful_cache(path):
    cached = {}
    for row in load(path):
        if row.get('key') and valid_gloss(row) and not row.get('error'):
            cached[row['key']] = row
    return cached


def translate(args):
    if not args.allow_network:
        raise ValueError('translate requires --allow-network; run only after the import/code push is verified')
    records = load(args.reviewed)
    if len(records) != len({r['key'] for r in records}):
        raise ValueError('duplicate reviewed keys')
    if any(r.get('action') not in {'translate', 'proper_name', 'reuse_curated', 'skip'} for r in records):
        raise ValueError('classify every row: translate, proper_name, reuse_curated or skip')
    if any(not isinstance(r.get('word'), str) or len(r['word'].split()) != 1 for r in records if r['action'] != 'skip'):
        raise ValueError('translator accepts individual public words only')
    cached = successful_cache(args.cache)
    pending = [r for r in records if r['action'] != 'skip' and r['key'] not in cached]
    target = pathlib.Path(args.cache)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock, rate, next_start = threading.Lock(), threading.Lock(), [0.0]

    def one(row):
        result = {**row, 'translation': '', 'note': row.get('note', '')}
        if row['action'] == 'proper_name':
            result.update(translation=row['word'], status='ignored')
        elif row['action'] == 'reuse_curated':
            result.update(row.get('curated', {}))
        else:
            for attempt in range(args.attempts):
                with rate:
                    delay = max(0.0, next_start[0] - time.monotonic())
                    if delay:
                        time.sleep(delay)
                    next_start[0] = time.monotonic() + args.interval
                try:
                    params = urllib.parse.urlencode({'client': 'dict-chrome-ex', 'sl': 'de', 'tl': 'en', 'q': row['word']})
                    request = urllib.request.Request('https://clients5.google.com/translate_a/t?' + params, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(request, timeout=20) as response:
                        data = json.load(response)
                    result['translation'] = data.strip() if isinstance(data, str) else data[0].strip() if isinstance(data, list) and len(data) == 1 and isinstance(data[0], str) else ''
                    if valid_gloss(result):
                        break
                    result['error'] = 'empty_or_invalid_translation'
                except Exception as error:
                    result['error'] = type(error).__name__
                if attempt + 1 < args.attempts:
                    time.sleep(min(4, attempt + 1))
        if valid_gloss(result):
            result.pop('error', None)
        else:
            result['error'] = result.get('error', 'empty_or_invalid_translation')
        with lock, target.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
        return not result.get('error')

    def many(rows):
        if len(rows) == 1:
            return int(one(rows[0]))
        for attempt in range(args.attempts):
            with rate:
                delay = max(0.0, next_start[0] - time.monotonic())
                if delay:
                    time.sleep(delay)
                next_start[0] = time.monotonic() + args.interval
            try:
                params = urllib.parse.urlencode([('client', 'dict-chrome-ex'), ('sl', 'de'), ('tl', 'en')]
                                                + [('q', row['word']) for row in rows])
                request = urllib.request.Request('https://clients5.google.com/translate_a/t?' + params, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = json.load(response)
                # A short/extra/nested response must never shift one word's gloss
                # onto another key. The individual path is the safe fallback.
                if not isinstance(data, list) or len(data) != len(rows) or not all(isinstance(t, str) for t in data):
                    break
                results = [{**row, 'translation': translation.strip(), 'note': row.get('note', '')}
                           for row, translation in zip(rows, data)]
                for result in results:
                    if not valid_gloss(result):
                        result['error'] = 'empty_or_invalid_translation'
                with lock, target.open('a', encoding='utf-8') as stream:
                    stream.write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in results))
                return sum(not r.get('error') for r in results)
            except Exception:
                if attempt + 1 < args.attempts:
                    time.sleep(min(4, attempt + 1))
        return sum(one(row) for row in rows)

    print(f'pending={len(pending)} cached={len(cached)}', flush=True)
    batch_size = getattr(args, 'batch_size', 1)
    local = [r for r in pending if r['action'] != 'translate']
    remote = [r for r in pending if r['action'] == 'translate']
    success = sum(one(row) for row in local)
    groups = [remote[start:start + batch_size] for start in range(0, len(remote), batch_size)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        success += sum(pool.map(many, groups))
    print(f'success={success} failed={len(pending) - success}; failed rows remain retriable')
    return 1 if success != len(pending) else 0


def merge(args):
    reviewed = load(args.reviewed)
    if len(reviewed) != len({r['key'] for r in reviewed}):
        raise ValueError('duplicate reviewed keys')
    accepted = []
    for row in reviewed:
        if row.get('action') == 'skip':
            continue
        if row.get('action') not in {'accept', 'revise'} or not valid_gloss(row):
            raise ValueError('merge needs context-reviewed accept/revise rows with valid glosses')
        note = row.get('note', '')
        if not isinstance(note, str) or len(note) > 200 or '\ufffd' in note or '\n' in note or '\r' in note:
            raise ValueError('invalid note')
        if not isinstance(row.get('word'), str) or len(row['word'].split()) != 1:
            raise ValueError('reviewed word must be one surface token')
        if row.get('status', 'new') not in VALID_STATUS:
            raise ValueError('invalid status')
        accepted.append(row)
    tokens = lua_lookup(args.addon, args.dictionary, [{'text': r['word']} for r in accepted], args.lua)
    by_key = {r['key']: r for r in tokens}
    curated_path = pathlib.Path(args.dictionary).parent / 'CuratedDE.jsonl'
    curated = {r['key']: r for r in load(curated_path)}
    additions, curated_additions = [], []
    for index, row in enumerate(accepted):
        key = row['key']
        if key not in by_key or by_key[key]['index'] != index:
            raise ValueError(f'word does not have the exact runtime key {key!r}')
        if by_key[key]['known']:
            continue
        clean = {'key': key, **{k: row[k] for k in FIELDS if k in row}}
        old = curated.get(key)
        if old:
            # The reviewed source also wins if it is currently absent from Lua.
            if any(clean.get(k, 'new' if k == 'status' else '') != old.get(k, 'new' if k == 'status' else '') for k in FIELDS):
                raise ValueError(f'existing curated entry differs for {key!r}; refusing overwrite')
            clean = {'key': key, **{k: old[k] for k in FIELDS if k in old}}
        else:
            curated_additions.append(clean)
        additions.append(clean)
    if not additions:
        print('added=0; all reviewed entries already exist')
        return 0
    lines = ['-- Incremental public-corpus vocabulary; existing entries above remain byte-for-byte unchanged.']
    for start in range(0, len(additions), 20000):
        lines.append(';(function()')
        for row in additions[start:start + 20000]:
            fields = ', '.join(k + ' = ' + luaq(row[k]) for k in FIELDS if k in row)
            lines.append('WordHunterWoW_Dictionary_DE[' + luaq(row['key']) + '] = { ' + fields + ' }')
        lines.append('end)()')
    dictionary = pathlib.Path(args.dictionary)
    old_lua, old_curated = dictionary.read_bytes(), curated_path.read_bytes() if curated_path.exists() else b''
    new_lua = old_lua + b'\n' + ('\n'.join(lines) + '\n').encode('utf-8')
    new_curated = old_curated + (b'\n' if old_curated and not old_curated.endswith(b'\n') else b'') + ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in curated_additions).encode('utf-8')
    with tempfile.TemporaryDirectory(prefix='whw-merge-') as folder:
        check = pathlib.Path(folder) / 'dictionary.lua'
        check.write_bytes(new_lua)
        parser = pathlib.Path(folder) / 'check.lua'
        parser.write_text('assert(loadfile(arg[1]))\n', encoding='utf-8')
        subprocess.run([args.lua, str(parser), str(check)], check=True, capture_output=True)
    backup = pathlib.Path(args.backup)
    backup.mkdir(parents=True, exist_ok=True)
    (backup / ('DictionaryDE-' + hashlib.sha256(old_lua).hexdigest() + '.lua')).write_bytes(old_lua)
    (backup / ('CuratedDE-' + hashlib.sha256(old_curated).hexdigest() + '.jsonl')).write_bytes(old_curated)
    # These are local build artifacts. Restore both originals if either write fails.
    try:
        curated_path.write_bytes(new_curated)
        dictionary.write_bytes(new_lua)
    except BaseException:
        curated_path.write_bytes(old_curated)
        dictionary.write_bytes(old_lua)
        raise
    write(backup / 'last-added.jsonl', additions)
    print(f'added={len(additions)} curatedAdded={len(curated_additions)} oldLuaSha256={hashlib.sha256(old_lua).hexdigest()}')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    e = commands.add_parser('extract')
    e.add_argument('--corpus', action='append', required=True, help='Public corpus JSONL: locale,id,kind,sourceFlavor,text; optional enText,skipVocabulary')
    e.add_argument('--out', required=True)
    t = commands.add_parser('translate')
    t.add_argument('--reviewed', required=True)
    t.add_argument('--cache', required=True)
    t.add_argument('--allow-network', action='store_true')
    t.add_argument('--workers', type=int, default=4)
    t.add_argument('--interval', type=float, default=.25)
    t.add_argument('--attempts', type=int, default=3)
    t.add_argument('--batch-size', type=int, default=1, help='Repeated q parameters; enable only after a post-push order/shape probe. Bad shape falls back to individual requests.')
    m = commands.add_parser('merge')
    m.add_argument('--reviewed', required=True)
    m.add_argument('--backup', required=True)
    for cmd in (e, m):
        cmd.add_argument('--dictionary', default=str(ROOT / 'Data/DictionaryDE.lua'))
        cmd.add_argument('--addon', default=str(ROOT.parent / 'WordHunterWoW'))
        cmd.add_argument('--lua', default='lua')
    args = parser.parse_args()
    if args.command == 'translate' and (args.workers < 1 or args.interval < 0 or args.attempts < 1 or args.batch_size < 1):
        parser.error('workers/attempts/batch-size must be positive; interval cannot be negative')
    try:
        return {'extract': extract, 'translate': translate, 'merge': merge}[args.command](args) or 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
