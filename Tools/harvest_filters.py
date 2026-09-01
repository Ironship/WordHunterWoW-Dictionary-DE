#!/usr/bin/env python3
"""Passages a harvest export should not contribute to the corpus.

Two kinds got through a real import and became dictionary candidates.

The first is the player's own character names. Gossip and quest text address the
player by name -- "Ah, da seid Ihr ja, Aryo!" -- and the addon stored the line
verbatim, so four of one player's characters arrived looking like ordinary
German vocabulary. The addon substitutes the name now, but exports already taken
still carry it, and so does anyone running an older build.

The second is a passage in the wrong language. One entirely Portuguese passage
reached a German corpus and contributed nine Portuguese words. Whatever produced
it, a German corpus is the wrong home for it.

Neither check is clever, and that is deliberate: both err towards keeping a
passage, since dropping real quest text costs more than the odd stray word.
"""
import pathlib
import re

# A German passage of any length contains at least one of these. They are the
# words that make German German: articles, pronouns, the polite plural the game
# addresses the player with, and the commonest verbs and particles. A sentence
# in another language will contain none, which is the whole test.
GERMAN_MARKERS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
    "und", "oder", "aber", "nicht", "ist", "sind", "war", "waren", "wird",
    "ich", "du", "er", "sie", "es", "wir", "ihr", "euch", "eure", "euer",
    "mich", "mir", "sich", "zu", "zum", "zur", "von", "vom", "mit", "auf",
    "aus", "bei", "nach", "vor", "an", "am", "im", "in", "hat", "haben",
    "habt", "wenn", "dass", "als", "wie", "noch", "nur", "auch", "schon",
    "was", "wer", "wo", "wann", "warum", "will", "soll", "muss", "kann",
    "man", "mein", "dein", "sein", "ihre", "ihren", "alle", "allen", "viel",
    "mehr", "sehr", "hier", "dort", "dann", "doch", "denn", "gegen", "ohne",
    "bis", "seit", "damit", "weil", "dieser", "diese", "dieses", "jeder",
    "keine", "kein", "etwas", "nichts", "immer", "wieder", "werden", "seid",
}
# "um" is deliberately absent. It is a perfectly ordinary German word, but it is
# also Portuguese for "a", and the one non-German passage that reached this
# corpus was Portuguese. One shared short word was enough to make the passage
# look German, which is the whole failure this check exists to prevent.

# Twelve words, calibrated against the 30,815-record German corpus: at this
# length every real German passage carries at least one marker, and the ten that
# do not are all genuinely not German -- Blizzard's own [PH] and [DNT] test
# quests, untranslated English, and that Portuguese passage. Below twelve the
# check starts condemning real quest titles: "Einige Leute muss man einfach
# toeten" is six words of ordinary German with no article in it at all.
MIN_WORDS_TO_JUDGE = 12

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def looks_german(text, markers=GERMAN_MARKERS):
    """True unless the passage is long enough to judge and carries no German.

    Short passages -- an item name, a two-word objective, a stylised quest title
    -- are kept without argument. There is not enough in them to tell one
    language from another, and they are exactly the fragments the corpus is
    missing.
    """
    words = [w.casefold() for w in WORD.findall(text or "")]
    if len(words) < MIN_WORDS_TO_JUDGE:
        return True
    return any(w in markers for w in words)


def redact_names(text, names):
    """Replace the player's character names with the placeholder the addon uses.

    Substituted rather than dropped so the sentence still reads as a sentence and
    still yields its other words. Longest first, so a name that contains another
    is not half-replaced.

    Matched on word boundaries only. Without them a short character name inside
    an ordinary word tears the word apart: a first attempt turned "Kassandra"
    and "Gul'dans" into fragments that then arrived as new vocabulary. A name in
    quest text is always a word of its own.
    """
    if not names:
        return text
    for name in sorted((n for n in names if n), key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(name) + r"\b", "<name>", text, flags=re.IGNORECASE)
    return text


def character_names(saved_path):
    """Character names to redact, read from the WoW folder around the export.

    The addon's own SavedVariables file is account-wide and names no character,
    so the names come from the layout instead: WoW keeps one directory per realm
    under the account, and one per character under that. Every name the game
    could have addressed this account's text to is a directory name.

    Anything that cannot be read gives an empty set, which just means no
    redaction -- never an error, since this runs beside an import that has real
    work to do.
    """
    account = pathlib.Path(saved_path).resolve().parent.parent
    if not account.is_dir():
        return set()
    names = set()
    for realm in account.iterdir():
        if not realm.is_dir() or realm.name == "SavedVariables":
            continue
        for character in realm.iterdir():
            if character.is_dir() and character.name[:1].isalpha():
                names.add(character.name)
    return names
