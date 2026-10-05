"""Offline end-to-end check: real Lua calls, failure retry, append-only merge."""
import argparse
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import urllib.error
import urllib.parse

import translate_incremental as tool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lua', default='lua')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='whw-incremental-test-') as folder:
        root = Path(folder)
        addon, data, out = root / 'addon', root / 'Data', root / 'out'
        addon.mkdir(); data.mkdir()
        # The special key proves extraction uses Lua's wordKey, not Python regex.
        (addon / 'Core.lua').write_text('''WordHunterWoW_Addon = {}
local A = WordHunterWoW_Addon
function A.TextLines(text) local t={} for token in text:gmatch("%S+") do t[#t+1]=token end return {t} end
function A.cleanWord(token) return (token:gsub("^%p+", ""):gsub("%p+$", "")) end
function A.wordKey(word) local key=A.cleanWord(word):lower():gsub("ß", "ss") if key=="geissel" then return "geisselspecial" end return key end
function A.RegisterDictionaryProvider(locale, id, entries) A.entries=entries return true end
function A.GetDictionaryEntry(key, locale) return A.entries[key] end
''', encoding='utf-8')
        dictionary = data / 'DictionaryDE.lua'
        original_lua = b'WordHunterWoW_Dictionary_DE = {die={word="Die",translation="the"},strasse={word="Stra\\195\\159e",translation="street",status="known"},besucht={word="besucht",translation="visits"}}\n'
        dictionary.write_bytes(original_lua)
        curated = data / 'CuratedDE.jsonl'
        tool.write(curated, [{'key': 'strasse', 'word': 'Straße', 'translation': 'street', 'status': 'known'}])
        original_curated = curated.read_bytes()
        corpus = root / 'corpus.jsonl'
        tool.write(corpus, [
            {'locale': 'deDE', 'id': 1, 'kind': 'completion', 'text': 'Die Straße besucht Geißel Jessica {name} 123 [q4].'},
            {'locale': 'deDE', 'id': 2, 'kind': 'name', 'text': 'Jessica', 'enText': 'Jessica'},
            {'locale': 'enUS', 'id': 1, 'kind': 'completion', 'text': 'English must never enter the queue.'},
        ])
        tool.extract(SimpleNamespace(addon=addon,dictionary=dictionary,corpus=[corpus],out=out,lua=args.lua))
        candidates = tool.load(out / 'candidates.jsonl')
        assert {r['key'] for r in candidates} == {'geisselspecial', 'jessica'}
        assert next(r for r in candidates if r['key'] == 'jessica').get('nameEvidence')
        assert {r['reason'] for r in tool.load(out / 'excluded.jsonl')} == {'player_or_tooltip_macro', 'numeric_or_symbol', 'markup_formula_or_variant'}
        for row in candidates:
            row['action'] = 'proper_name' if row['key'] == 'jessica' else 'translate'
        classified, cache = out / 'classified.jsonl', out / 'cache.jsonl'
        tool.write(classified, candidates)
        tool.write(cache, [{'key':'geisselspecial','word':'Geißel','translation':'','error':'old_failure'}])
        translate_args = SimpleNamespace(reviewed=classified,cache=cache,allow_network=True,attempts=2,workers=1,interval=0)
        calls = []
        def respond(request, timeout):
            calls.append(urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)['q'][0])
            if len(calls) == 1:
                raise urllib.error.URLError('retry this failure')
            return io.BytesIO(b'"Scourge"')
        with patch.object(tool.urllib.request, 'urlopen', side_effect=respond), patch.object(tool.time, 'sleep', return_value=None):
            assert tool.translate(translate_args) == 0
            assert tool.translate(translate_args) == 0
        assert calls == ['Geißel', 'Geißel'], 'only a public word is sent, no context; failed/empty old rows retry'
        complete = tool.successful_cache(cache)
        assert complete['jessica']['status'] == 'ignored'
        assert complete['geisselspecial']['translation'] == 'Scourge'
        for row in complete.values():
            row['action'] = 'accept'
        # A reviewed entry that already exists must not overwrite a learned/glossed baseline.
        rows = list(complete.values()) + [{'key':'strasse','word':'Straße','translation':'wrong new translation','action':'accept'}]
        reviewed = out / 'reviewed.jsonl'
        tool.write(reviewed, rows)
        merge_args = SimpleNamespace(addon=addon,dictionary=dictionary,reviewed=reviewed,backup=out/'backup',lua=args.lua)
        assert tool.merge(merge_args) == 0
        merged_lua, merged_curated = dictionary.read_bytes(), curated.read_bytes()
        assert merged_lua.startswith(original_lua) and merged_curated.startswith(original_curated)
        assert tool.merge(merge_args) == 0
        assert dictionary.read_bytes() == merged_lua and curated.read_bytes() == merged_curated, 'merge is idempotent'
        assert dictionary.read_bytes().count(b'geisselspecial') == 1
        assert len(tool.load(curated)) == 3
        # A swapped/wrong runtime key cannot sneak through another row's key.
        tool.write(reviewed, [{'key':'absent','word':'different','translation':'different','action':'accept'}])
        try:
            tool.merge(merge_args)
        except ValueError:
            pass
        else:
            raise AssertionError('wrong runtime key accepted')
        assert dictionary.read_bytes() == merged_lua
        # Batch mapping is permitted only with exactly N strings in input order.
        batch_words = [{'key':'hund','word':'Hund','action':'translate'}, {'key':'katze','word':'Katze','action':'translate'}]
        tool.write(classified, batch_words)
        batch_cache = out / 'batch-cache.jsonl'
        batch_args = SimpleNamespace(reviewed=classified,cache=batch_cache,allow_network=True,attempts=1,workers=1,interval=0,batch_size=2)
        batch_calls = []
        def batch_response(request, timeout):
            words = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)['q']
            batch_calls.append(words)
            return io.BytesIO(json.dumps([{'Hund':'dog','Katze':'cat'}[w] for w in words]).encode())
        with patch.object(tool.urllib.request,'urlopen',side_effect=batch_response):
            assert tool.translate(batch_args) == 0
        assert batch_calls == [['Hund','Katze']]
        assert {k:r['translation'] for k,r in tool.successful_cache(batch_cache).items()} == {'hund':'dog','katze':'cat'}
        mismatch_cache = out / 'mismatch-cache.jsonl'
        batch_args.cache = mismatch_cache
        batch_calls.clear()
        def mismatch_response(request, timeout):
            words = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)['q']
            batch_calls.append(words)
            if len(words) > 1:
                return io.BytesIO(b'["wrong first-only response"]')
            return io.BytesIO(json.dumps({'Hund':'dog','Katze':'cat'}[words[0]]).encode())
        with patch.object(tool.urllib.request,'urlopen',side_effect=mismatch_response):
            assert tool.translate(batch_args) == 0
        assert batch_calls == [['Hund','Katze'],['Hund'],['Katze']], 'bad batch falls back without caching any misassigned gloss'
        assert {k:r['translation'] for k,r in tool.successful_cache(mismatch_cache).items()} == {'hund':'dog','katze':'cat'}
        print('incremental dictionary: offline extraction/review/retry/resume/prefix preservation/idempotence/key guard passed')


if __name__ == '__main__':
    main()
