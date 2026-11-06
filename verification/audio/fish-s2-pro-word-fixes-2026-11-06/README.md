# Cut-off word recordings, repaired 2026-11-06

Some word clips from the Fish S2 Pro set ended abruptly or were nearly silent (for example "das", "den", "dem", "Feinde").
The length heuristics of the original verification did not catch most of them, so the clips were re-measured:
loudness of the last 20 ms against the clip peak (end above -25 dB means the word is cut off), clips of four letters or fewer
shorter than 0.3 s, and the 51 clips flagged earlier. That selected 2197 words.

Each selected word was spoken again with the same model, reference voice, sampling settings and loudness as the original set.
Only the text changed (a capital letter for lower-case words and a closing full stop, so the model finishes the word) and up to
six seeds were tried; the clip with the cleanest fade-out and no length flag was kept (`generate_fixes.py`).

* **2187 clips replaced.** `fixes.jsonl` lists old and new duration and edge loudness, the seed and the SHA256.
  `../fish-s2-pro-2026-10-13/inventory.jsonl` was updated to the new hashes, so verification against the repository still passes.
* **10 clips unchanged** because no candidate was better: di, Grlrlrglrmg, mglgrgrlm, mgrlmlgr, Murr, rlmgr, Tipp, Ts, vom, Vos.
* This is an objective measurement, not a listening audit. The remaining clips were not re-checked by ear.
