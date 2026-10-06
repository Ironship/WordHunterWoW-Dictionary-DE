"""CI regression: growing dictionaries keep bounded, closed Lua functions."""
from mark_proper_names import MAX_LUA_CHUNK_ROWS, lua_chunk_errors


def chunk(rows):
    return ';(function()\n' + 'WordHunterWoW_Dictionary_DE["key"] = {}\n' * rows + 'end)()\n'


assert not lua_chunk_errors(chunk(1) * 6)
assert not lua_chunk_errors(chunk(2) * 6 + chunk(17) + chunk(3))
assert not lua_chunk_errors(chunk(MAX_LUA_CHUNK_ROWS))
for invalid in ('', chunk(0), chunk(MAX_LUA_CHUNK_ROWS + 1),
                'WordHunterWoW_Dictionary_DE["outside"] = {}\n' + chunk(1),
                chunk(1).removesuffix('end)()\n'), 'end)()\n' + chunk(1),
                ';(function()\n' + chunk(1)):
    assert lua_chunk_errors(invalid), 'Malformed dictionary chunks passed'
print('PASS: base and incremental chunks accepted; unsafe, empty and unbalanced chunks rejected')
