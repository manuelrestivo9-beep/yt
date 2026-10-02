"""Calcola audio/tagli.json da voce_pulita.wav + trascrizione.json (regole in CLAUDE.md, passo 5).

Le pause si misurano sull'inviluppo d'energia (finestre da 10 ms), non sui timestamp di Whisper,
così i tagli cadono nel silenzio vero e restano fuori dalle parole.
Le ripetizioni (RIPETIZIONI qui sotto) sono decise dall'allineamento con script.md: si tiene l'ULTIMA.
"""
import json, subprocess
from pathlib import Path
import numpy as np

DIR = Path(__file__).parent
SR = 48000
WIN = 0.010              # finestra inviluppo (s)
SOGLIA_DB = -42.0        # sotto = silenzio (rumore di fondo dopo pulizia ~ -51 dB RMS)
PAUSA_MAX = 0.70         # pause oltre questa durata vengono ridotte
PAUSA_TARGET = 0.35      # durata che resta dopo la riduzione
MARGINE_FINE = 0.20      # silenzio tenuto dopo la fine della parola
MARGINE_INIZIO = PAUSA_TARGET - MARGINE_FINE   # silenzio tenuto prima dell'attacco successivo
CODA = 0.50              # silenzio tenuto alla fine del file

MIN_VOCE = 0.05         # energia sopra soglia per meno di 50 ms = click/rumore, non voce

# Ripetizioni trovate allineando la trascrizione allo script. Tempi misurati sull'inviluppo
# (Whisper anticipa l'attacco di "Questo" a 60.50; l'attacco vero è 60.90).
# "taglio_da": silenzio dopo la fine della frase precedente ("...contro usata.", coda fino a 60.52).
RIPETIZIONI = [
    {"frase": "Questo video è informazione generale, non consulenza finanziaria.",
     "scartata_da": 60.90, "taglio_da": 60.62, "tenuta_da": 67.71, "pausa_prima": 0.25},
]


def carica(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def inviluppo(x):
    n = int(SR * WIN)
    frames = x[: len(x) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-12)


def voce(env):
    """Maschera della voce: sopra soglia per almeno MIN_VOCE consecutivi (scarta click e rumori brevi)."""
    sopra = env >= SOGLIA_DB
    m = np.zeros_like(sopra); start = None
    for i, v in enumerate(np.append(sopra, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if (i - start) * WIN >= MIN_VOCE:
                m[start:i] = True
            start = None
    return m


def silenzi(env, min_dur):
    """Tratti senza voce lunghi almeno min_dur (s), come (inizio, fine)."""
    sotto = ~voce(env)
    out, start = [], None
    for i, s in enumerate(np.append(sotto, False)):
        if s and start is None:
            start = i
        elif not s and start is not None:
            if (i - start) * WIN >= min_dur:
                out.append((start * WIN, i * WIN))
            start = None
    return out


def parole_tra(trasc, a, b):
    return " ".join(w["p"] for s in trasc["segmenti"] for w in s["parole"]
                    if w["inizio"] >= a - 0.05 and w["fine"] <= b + 0.3)


def main():
    x = carica(DIR / "voce_pulita.wav")
    durata = len(x) / SR
    env = inviluppo(x)
    trasc = json.loads((DIR / "trascrizione.json").read_text())
    tagli = []

    # 1. Silenzio iniziale (profilo del rumore): via fino a poco prima del primo attacco.
    v = voce(env)
    primo = int(np.argmax(v[int(10.0 / WIN):])) * WIN + 10.0   # primo attacco dopo i ~10 s di profilo
    tagli.append({"inizio": 0.0, "fine": round(primo - MARGINE_INIZIO, 3), "motivo": "pausa lunga",
                  "nota": "silenzio iniziale (profilo rumore)", "testo": ""})

    # 2. Ripetizioni: taglio dal silenzio prima della versione scartata al silenzio prima di quella tenuta.
    for r in RIPETIZIONI:
        a, b = r["taglio_da"], r["tenuta_da"] - r["pausa_prima"]
        tagli.append({"inizio": round(a, 3), "fine": round(b, 3), "motivo": "ripetizione",
                      "testo": parole_tra(trasc, r["scartata_da"] - 0.45, r["tenuta_da"] - 2.0),
                      "nota": f"tenuta l'ultima ripetizione da {r['tenuta_da']:.2f} s"})

    # 3. Pause lunghe nel parlato (fuori dai tagli già fatti), coda esclusa.
    for s, e in silenzi(env, PAUSA_MAX):
        if e >= durata - 0.02 or any(s < t["fine"] and e > t["inizio"] for t in tagli):
            continue
        if s < tagli[0]["fine"]:
            continue
        tagli.append({"inizio": round(s + MARGINE_FINE, 3), "fine": round(e - MARGINE_INIZIO, 3),
                      "motivo": "pausa lunga", "testo": "", "nota": f"pausa di {e - s:.2f} s ridotta a {PAUSA_TARGET} s"})

    # 4. Coda finale.
    fine_voce = (len(v) - int(np.argmax(v[::-1]))) * WIN
    if durata - fine_voce > CODA:
        tagli.append({"inizio": round(fine_voce + CODA, 3), "fine": round(durata, 3), "motivo": "pausa lunga",
                      "nota": "silenzio finale", "testo": ""})

    tagli.sort(key=lambda t: t["inizio"])
    out = {"sorgente": "audio/voce_pulita.wav", "durata_sorgente": round(durata, 3),
           "parametri": {"soglia_silenzio_db": SOGLIA_DB, "pausa_max": PAUSA_MAX, "pausa_target": PAUSA_TARGET,
                         "crossfade_ms": 20},
           "tagli": tagli}
    (DIR / "tagli.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for t in tagli:
        print(f'{t["inizio"]:7.3f} – {t["fine"]:7.3f}  ({t["fine"] - t["inizio"]:.2f} s)  {t["motivo"]:12s} {t.get("nota", "")}  {t["testo"][:60]}')


if __name__ == "__main__":
    main()
