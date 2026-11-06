"""Re-speak German words whose clip is cut off (loud at the end) or implausibly short, choosing the best of several seeds.

Same model, reference voice, sampling and loudness as the approved set. The text gets a closing full stop (and a capital
for lower-case words) so the model finishes the word; seeds are tried until one fades out cleanly.
Resumable (fixes.jsonl); installs nothing. Chosen clips go to chosen/<path>.
"""
import contextlib, hashlib, json, os, subprocess, sys, time
from pathlib import Path
import numpy as np, soundfile as sf, torch

ROOT = Path(__file__).resolve().parent
REPO = Path.home() / 'fish-speech-pilot'
SEEDS = [42, 1, 2, 3, 4, 5]
sys.path.insert(0, str(REPO))
from loguru import logger
from fish_speech.models.text2semantic import inference as fish
logger.remove(); logger.add(sys.stderr, level='WARNING')
fish.tqdm = lambda iterable, *a, **kw: iterable


def spoken(text):
    t = text[0].upper() + text[1:] if text[:1].islower() else text
    return t if t.endswith(('.', '!', '?')) else t + '.'


def metrics(audio, sr, token_limit, text):
    k = int(sr*.02); pk = float(np.max(np.abs(audio))) + 1e-9
    db = lambda x: round(20*np.log10(np.sqrt(np.mean(x**2))/pk + 1e-9), 1)
    sec = len(audio)/sr
    flags = []
    if token_limit: flags.append('token_limit')
    if sec > max(2.5, len(text)*.12+.7): flags.append('too_long')
    if sec < .2: flags.append('too_short')
    return dict(sec=round(sec, 3), start=db(audio[:k]), end=db(audio[-k:]), flags=flags)


def score(m):
    """Lower is better: a clean fade-out and a soft onset, no length flags."""
    return (len(m['flags']) * 100) + max(m['end'] + 35, 0) + max(m['start'] + 18, 0) * .5 + (50 if m['sec'] < .25 else 0)


def main():
    rows = [json.loads(l) for l in (ROOT/'plan.jsonl').read_text(encoding='utf-8').splitlines()]
    done = {json.loads(l)['path'] for l in (ROOT/'fixes.jsonl').read_text(encoding='utf-8').splitlines()} if (ROOT/'fixes.jsonl').exists() else set()
    rows = [r for r in rows if r['path'] not in done]
    reference = (ROOT/'reference.txt').read_text(encoding='utf-8')
    checkpoint = REPO/'checkpoints/s2-pro'
    (ROOT/'chosen').mkdir(exist_ok=True)
    tmp = ROOT/'tmp'; tmp.mkdir(exist_ok=True)
    began = time.time(); count = 0
    with torch.inference_mode(), open(os.devnull, 'w') as quiet:
        model, decoder = fish.init_model(checkpoint, 'cuda', torch.bfloat16, compile=True)
        with torch.device('cuda'):
            model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len, dtype=torch.bfloat16)
        codec = fish.load_codec_model(checkpoint/'codec.pth', 'cuda', torch.bfloat16)
        prompt = fish.encode_audio(ROOT/'reference.wav', codec, 'cuda').cpu()
        for row in rows:
            best = None; tried = []
            for seed in SEEDS:
                torch.manual_seed(seed); torch.cuda.manual_seed(seed)
                codes = []
                try:
                    with contextlib.redirect_stdout(quiet):
                        for r in fish.generate_long(model=model, device='cuda', decode_one_token=decoder,
                            text='<|speaker:0|>' + spoken(row['text']), num_samples=1, max_new_tokens=240, top_p=.9,
                            top_k=30, temperature=1.0, compile=True, iterative_prompt=True, chunk_length=300,
                            prompt_text=[reference], prompt_tokens=[prompt]):
                            if r.action == 'sample': codes.append(r.codes)
                    merged = torch.cat(codes, dim=1)
                    audio = fish.decode_to_audio(merged.to('cuda'), codec).cpu().float().numpy()
                    assert audio.size > 1000 and np.isfinite(audio).all() and np.max(np.abs(audio)) > .0001
                except Exception as error:
                    tried.append(dict(seed=seed, error=repr(error))); continue
                m = metrics(audio, codec.sample_rate, merged.shape[1] >= 239, row['text']); m['seed'] = seed
                tried.append(m)
                if best is None or score(m) < score(best[0]):
                    best = (m, audio)
                if score(m) == 0 or (m['end'] <= -40 and m['start'] <= -20 and not m['flags'] and m['sec'] >= .3):
                    break
            if best is None:
                result = dict(row, status='failed', tried=tried)
            else:
                m, audio = best
                out = ROOT/'chosen'/row['path']; out.parent.mkdir(parents=True, exist_ok=True)
                raw = tmp/'current.wav'; sf.write(raw, audio, codec.sample_rate)
                subprocess.run(['ffmpeg','-v','error','-y','-i',str(raw),'-af','loudnorm=I=-18:TP=-2','-ar','24000',
                    '-c:a','libvorbis','-q:a','5',str(out)], check=True)
                data = out.read_bytes()
                improved = score(m) < score(dict(sec=row['old_sec'], start=row['old_start'], end=row['old_end'], flags=[]))
                result = dict(row, status='better' if improved else 'not_better', chosen=m, sha256=hashlib.sha256(data).hexdigest(),
                              bytes=len(data), tried=tried)
                if not improved: out.unlink()
            with (ROOT/'fixes.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
            count += 1
            if count % 25 == 0 or count <= 5:
                print('DONE', count, '/', len(rows), 'elapsed %.0fs' % (time.time()-began), flush=True)
    print('FINISHED', flush=True)

if __name__ == '__main__':
    main()
