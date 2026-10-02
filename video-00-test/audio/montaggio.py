"""Applica audio/tagli.json a voce_pulita.wav -> voce_montata.wav, anteprima.mp3, trascrizione_montata.json.
Ogni giunzione ha una dissolvenza incrociata a potenza costante (CLAUDE.md: 15-30 ms)."""
import json, subprocess
from pathlib import Path
import numpy as np

DIR = Path(__file__).parent
SR = 48000


def carica(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def salva(x, path, *codec):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    *codec, str(path)], input=x.astype(np.float32).tobytes(), check=True)


def main():
    cfg = json.loads((DIR / "tagli.json").read_text())
    xf = int(SR * cfg["parametri"]["crossfade_ms"] / 1000)
    x = carica(DIR / "voce_pulita.wav")
    durata = len(x) / SR

    # tratti da tenere = complemento dei tagli
    tenuti, t0 = [], 0.0
    for t in sorted(cfg["tagli"], key=lambda t: t["inizio"]):
        if t["inizio"] > t0:
            tenuti.append((t0, t["inizio"]))
        t0 = max(t0, t["fine"])
    if t0 < durata:
        tenuti.append((t0, durata))

    # concatenazione con crossfade a potenza costante; si tiene la mappa vecchio -> nuovo tempo
    fade_in = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
    out = np.zeros(0, dtype=np.float32)
    mappa = []  # (inizio_vecchio, fine_vecchio, offset_nuovo)
    for i, (a, b) in enumerate(tenuti):
        pezzo = x[int(a * SR):int(b * SR)].copy()
        if i == 0 or len(out) < xf:
            mappa.append((a, b, len(out) / SR - a))
            out = np.concatenate([out, pezzo])
        else:
            mappa.append((a, b, (len(out) - xf) / SR - a))
            out[-xf:] = out[-xf:] * fade_in[::-1] + pezzo[:xf] * fade_in
            out = np.concatenate([out, pezzo[xf:]])
    # micro-dissolvenze agli estremi del file
    f = int(SR * 0.01); out[:f] *= np.linspace(0, 1, f); out[-f * 5:] *= np.linspace(1, 0, f * 5)

    salva(out, DIR / "voce_montata.wav", "-c:a", "pcm_s24le")
    salva(out, DIR / "anteprima.mp3", "-c:a", "libmp3lame", "-b:a", "192k")

    # trascrizione con i tempi del montato. Whisper anticipa spesso gli attacchi dentro le pause:
    # prima si agganciano inizio/fine di ogni parola alla voce misurata, poi si scartano
    # le parole che cadono in un taglio e si spostano le altre.
    from tagli import inviluppo, voce, WIN
    v = voce(inviluppo(x))
    def aggancia(w):
        """Riduce la parola alla voce misurata. Se dentro c'è una pausa >= 0,3 s (Whisper ha inglobato
        la coda della parola prima o il silenzio), tiene solo il gruppo di voce più lungo."""
        i0, i1 = int(w["inizio"] / WIN), min(int(w["fine"] / WIN), len(v) - 1)
        idx = np.flatnonzero(v[i0:i1]) + i0
        if len(idx) == 0:
            return w["inizio"], w["fine"]
        gruppi = np.split(idx, np.flatnonzero(np.diff(idx) * WIN >= 0.3) + 1)
        g = max(gruppi, key=len)
        return g[0] * WIN, (g[-1] + 1) * WIN
    def nuovo(t):
        for a, b, off in mappa:
            if a - 0.001 <= t <= b + 0.001:
                return round(t + off, 3)
        return None
    trasc = json.loads((DIR / "trascrizione.json").read_text())
    parole = []
    for s in trasc["segmenti"]:
        for w in s["parole"]:
            ini, fin = aggancia(w)
            mezzo = (ini + fin) / 2
            if nuovo(mezzo) is None:
                continue                      # parola dentro un taglio (es. ripetizione scartata)
            a, b, off = next(m for m in mappa if m[0] - 0.001 <= mezzo <= m[1] + 0.001)
            parole.append({**w, "inizio": round(max(ini, a) + off, 3), "fine": round(min(fin, b) + off, 3)})
    (DIR / "trascrizione_montata.json").write_text(json.dumps(
        {"sorgente": "audio/voce_montata.wav", "durata": round(len(out) / SR, 3), "parole": parole},
        ensure_ascii=False, indent=1))

    print(f"tratti tenuti: {len(tenuti)}, giunzioni: {len(tenuti) - 1}")
    print(f"durata: {durata:.2f} s -> {len(out) / SR:.2f} s")


if __name__ == "__main__":
    main()
