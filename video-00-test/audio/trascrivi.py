"""Trascrizione con faster-whisper: lingua it, timestamp per parola -> audio/trascrizione.json"""
import json, sys
from pathlib import Path
from faster_whisper import WhisperModel

AUDIO = Path(__file__).parent / "voce_pulita.wav"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "large-v3"
model = WhisperModel(MODEL, device="cpu", compute_type="int8")
segs, info = model.transcribe(str(AUDIO), language="it", word_timestamps=True, beam_size=5,
                              vad_filter=False, condition_on_previous_text=False)
out = {"modello": MODEL, "lingua": info.language, "durata": round(info.duration, 2), "segmenti": []}
for s in segs:
    out["segmenti"].append({
        "inizio": round(s.start, 2), "fine": round(s.end, 2), "testo": s.text.strip(),
        "avg_logprob": round(s.avg_logprob, 3), "no_speech_prob": round(s.no_speech_prob, 3),
        "parole": [{"p": w.word.strip(), "inizio": round(w.start, 3), "fine": round(w.end, 3),
                    "conf": round(w.probability, 3)} for w in s.words],
    })
(Path(__file__).parent / "trascrizione.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
for s in out["segmenti"]:
    print(f'[{s["inizio"]:6.2f}-{s["fine"]:6.2f}] ({s["avg_logprob"]}) {s["testo"]}')
