"""Offline classification and review of incremental public-corpus vocabulary.

Translation is a separate command, run after the import/code publication.
Shared names and existing curator rows remain held; nothing here marks them known.
"""
import argparse
import collections
import json
from pathlib import Path
import re

from translate_incremental import load, valid_gloss, write


DEVELOPER = re.compile(r'\b(?:debug|dummy|tracking|tracker|placeholder|unused|deprecated|dnd|dnt|nyi|qadebug|qaench\w*|flag)\b|^ZZOLD|^Copy of|^Monster\s*-|\(PT\)', re.I)
TOKEN = re.compile(r"[^\W\d_]+(?:[-'’‘][^\W\d_]+)*", re.UNICODE)


def key(word):
    return word.casefold().replace('ß', 'ss')


def classify(rows):
    output = []
    for original in rows:
        row = dict(original)
        source, reason = row['source'], None
        paired = source.get('enText', '')
        same = row['context'] == paired
        name = source.get('category') in ('name', 'title') or source.get('kind') == 'title'
        shared = name and row['key'] in {key(t) for t in TOKEN.findall(paired)}
        if row.get('curated'):
            reason = 'Existing curator entry remains authoritative; no automatic reactivation'
        elif same and DEVELOPER.search(row['context']):
            reason = 'Explicit English developer/debug source label'
        elif shared or 'nameEvidence' in row:
            reason = 'Shared DE/EN name token needs contextual review'
        elif same:
            reason = 'Identical short DE/EN field needs contextual review'
        row.update(action='skip' if reason else 'translate', reviewReason=reason or
                   'Lexical token in distinct German context, without curator/shared-name evidence')
        output.append(row)
    return output


def names(corpora):
    """Pair full names only within one source flavor, kind, and ID."""
    english = {}
    for path in corpora:
        with path.open(encoding='utf-8-sig') as handle:
            for line in handle:
                row = json.loads(line)
                if row.get('locale') == 'enUS' and row.get('category') == 'name':
                    english[(row['sourceFlavor'], row['kind'], row['id'])] = row['text']
    pairs = collections.defaultdict(dict)
    for path in corpora:
        with path.open(encoding='utf-8-sig') as handle:
            for line in handle:
                row = json.loads(line)
                text = row.get('text', '')
                if row.get('locale') != 'deDE' or row.get('category') != 'name' or not TOKEN.fullmatch(text):
                    continue
                identity = (row['sourceFlavor'], row['kind'], row['id'])
                gloss = english.get(identity)
                if gloss and key(gloss) != key(text) and valid_gloss({'translation': gloss}) and not re.search(r'[{}$<>|]', gloss):
                    pairs[key(text)][gloss] = {'sourceFlavor': identity[0], 'kind': identity[1], 'id': identity[2], 'de': text, 'en': gloss}
    return pairs


def review(rows, cache, pairs):
    output = []
    for original in rows:
        row = dict(original)
        if row['action'] == 'skip':
            output.append(row)
            continue
        result = cache.get(row['key'])
        if not result or result.get('error') or not valid_gloss(result):
            raise ValueError('Missing successful machine translation: ' + row['key'])
        row.update(translation=result['translation'], status='new', note='', action='accept',
                   reviewReason='Machine gloss passed lexical/source/output checks; not individually human verified')
        evidence = pairs.get(row['key'], {})
        if row['word'][0].isupper() and len(evidence) == 1:
            gloss, proof = next(iter(evidence.items()))
            row.update(translation=gloss, action='revise', glossSource=proof,
                       note='Source English game name; source versions may differ.',
                       reviewReason='Unambiguous full-token same-source DE/EN entity name')
        if key(row['translation']) == key(row['word']):
            row.update(action='skip', reviewReason='Unchanged machine output needs name/meaning review')
        elif re.search(r'[{}$<>|]|\[(?:Quellwert|source value)\]', row['translation']) or any(not c.isprintable() for c in row['translation']):
            row.update(action='skip', reviewReason='Formatting/source artifact in translation')
        output.append(row)
    return output


def self_check():
    def row(word, text, en, **extra):
        return dict(key=key(word), word=word, context=text, source={'category':'name', 'enText':en}, **extra)
    samples = [row('Bannschlag', 'Bannschlag', 'Banishing Strike'), row('Sturm', 'Sturm Lord', 'Sturm Lord'),
               row('Legacy', 'Legacy', 'Legacy', curated={'word':'Legacy','translation':'Legacy'})]
    classified = classify(samples)
    assert [r['action'] for r in classified] == ['translate','skip','skip']
    checked = review(classified, {'bannschlag':{'translation':'Banishing blow'}},
                     {'bannschlag':{'Banishing Strike':{'sourceFlavor':'tbc','kind':'spell','id':7}}})
    assert checked[0]['action'] == 'revise' and checked[0]['translation'] == 'Banishing Strike'
    conflicting = review(classified, {'bannschlag':{'translation':'Banishing blow'}},
                         {'bannschlag':{'First':{},'Second':{}}})
    assert conflicting[0]['translation'] == 'Banishing blow' and conflicting[0]['action'] == 'accept'
    assert review(classified, {'bannschlag':{'translation':'Bannschlag'}}, {})[0]['action'] == 'skip'
    assert samples[0].get('action') is None
    try:
        review(classified, {}, {})
    except ValueError:
        pass
    else:
        raise AssertionError('Missing translation accepted')
    print('PASS: shared/curator holds, unique/conflicting localization evidence, unchanged output and missing-cache gates')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('classify', 'review'), nargs='?')
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--corpus', type=Path, action='append', default=[])
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    if not args.command or not args.folder:
        parser.error('command and --folder required')
    if args.command == 'classify':
        result = classify(load(args.folder / 'candidates.jsonl'))
        filename = 'reviewed-translation-queue.jsonl'
    else:
        if not args.corpus:
            parser.error('review requires --corpus')
        cache = {r['key']:r for r in load(args.folder / 'translations-de-en.jsonl')}
        result = review(load(args.folder / 'reviewed-translation-queue.jsonl'), cache, names(args.corpus))
        filename = 'reviewed-merge.jsonl'
    write(args.folder / filename, result)
    write(args.folder / (args.command + '-held.jsonl'), [r for r in result if r['action']=='skip'])
    report = {'rows':len(result), 'actions':dict(collections.Counter(r['action'] for r in result)),
              'networkUsed':False, 'dictionaryChanged':False, 'exhaustiveHumanSemanticReview':False}
    (args.folder / (args.command + '-summary.json')).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
