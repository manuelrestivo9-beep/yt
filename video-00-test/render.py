"""Video 00 (test): scene animate + sottotitoli + musica -> video.mp4 (1080p 16:9) e miniatura.png.

Ingressi: audio/voce_montata.wav (approvato), audio/trascrizione_montata.json (tempi del montato),
risultati.json (da calc.py). Ogni animazione parte sulla parola che la nomina.
Uso: python render.py            (video completo)
     python render.py --frame 30  (salva solo il fotogramma al secondo 30 in _anteprima_frame.png)
"""
import json, subprocess, sys
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

DIR = Path(__file__).resolve().parent
FONT_DIR = DIR.parent / "assets" / "font"
W, H, FPS, SR = 1920, 1080, 30, 48000
CODA = 1.2  # secondi di immagine finale dopo l'ultima parola

# palette del canale
BG_TOP, BG_BOT = (16, 24, 38), (10, 15, 25)
TESTO, TENUE, ACCENTO, COSTO, LINEA = (240, 242, 245), (140, 150, 165), (255, 196, 0), (255, 107, 87), (60, 72, 92)

R = json.loads((DIR / "risultati.json").read_text())
PAROLE_RAW = json.loads((DIR / "audio" / "trascrizione_montata.json").read_text())["parole"]

# Correzioni ai sottotitoli (tempo nel montato, parola di Whisper, testo mostrato):
# maiuscole e punteggiatura mancanti, sigle, elisioni; i due punti dubbi seguono lo script.
CORREZIONI = [
    (0.15, "un", "Un"), (1.12, "italia", "Italia"), (4.46, "listino", "listino."), (4.96, "ma", "Ma"),
    (6.94, "'inizio", "'inizio."), (7.84, "facciamo", "Facciamo"), (8.49, "veloce", "veloce."),
    (10.45, "'anno", "'anno,"), (12.13, "chilometri", "chilometri,"), (12.93, "benzina", "benzina a"),
    (15.61, "MIMIT", "Mimit"), (24.08, "'IVAS", "'Ivass"), (25.34, "RC", "Rc"), (27.68, "euro,", "euro."),
    (28.46, "in", "In"), (41.83, "fai", "fai i"), (46.23, "contrusata.", "contro usata."),
]


def fmt(n):
    return f"{n:,.0f}".replace(",", ".")


def fmt_dec(x):
    return f"{x:.2f}".replace(".", ",")


# ---------- parole e sottotitoli ----------
def parole():
    ws = [dict(w) for w in PAROLE_RAW]
    for t, orig, nuovo in CORREZIONI:
        w = min(ws, key=lambda w: abs(w["inizio"] - t))
        assert w["p"] == orig and abs(w["inizio"] - t) < 0.02, (t, orig, w)
        w["p"] = nuovo
    out = []  # unisce i pezzi che Whisper separa: "l" + "'anno", "36" + ".000", "2" + ",11"
    for w in ws:
        if out and (w["p"][0] in "'" or (w["p"][0] in ".," and w["p"][1:2].isdigit())):
            out[-1]["p"] += w["p"]; out[-1]["fine"] = w["fine"]
        else:
            out.append(w)
    return out


PAROLE = parole()


def t_di(parola, dopo=0.0):
    """Tempo della prima parola (senza punteggiatura) che inizia dopo `dopo`."""
    for w in PAROLE:
        if w["inizio"] >= dopo and w["p"].split()[0].strip(".,;:").lower() == parola.lower():
            return w["inizio"]
    raise KeyError(parola)


def battute(max_car=36):
    lung = lambda ws: len(" ".join(x["p"] for x in ws))
    # 1. pezzi di frase: si chiude alla punteggiatura (se il pezzo non è troppo corto) o a una pausa > 0,5 s
    pezzi, cur = [], []
    for w in PAROLE:
        if cur and w["inizio"] - cur[-1]["fine"] > 0.5:
            pezzi.append(cur); cur = []
        cur.append(w)
        if w["p"][-1] in ".,;:?" and lung(cur) >= 14:
            pezzi.append(cur); cur = []
    if cur:
        pezzi.append(cur)
    # una parola isolata da una pausa si unisce al pezzo che segue
    i = 0
    while i < len(pezzi) - 1:
        if len(pezzi[i]) == 1:
            pezzi[i:i + 2] = [pezzi[i] + pezzi[i + 1]]
        else:
            i += 1
    # 2. pezzi troppo lunghi divisi in n parti di lunghezza simile (niente parole orfane)
    cues = []
    for p in pezzi:
        n = -(-lung(p) // max_car)
        obiettivo, parte = lung(p) / n, []
        for w in p:
            if parte and lung(parte + [w]) > obiettivo + 4:
                cues.append(parte); parte = []
            parte.append(w)
        cues.append(parte)
    out = []
    for i, c in enumerate(cues):
        fine = c[-1]["fine"] + 0.3
        if i + 1 < len(cues):
            fine = min(fine, cues[i + 1][0]["inizio"] - 0.10)
        out.append({"parole": c, "inizio": c[0]["inizio"] - 0.08, "fine": fine})
    return out


BATTUTE = battute()


# ---------- disegno ----------
@lru_cache(None)
def font(peso, size):
    return ImageFont.truetype(str(FONT_DIR / f"Inter-{peso}.ttf"), size)


@lru_cache(None)
def sprite(testo, peso, size, colore):
    """Testo su un riquadro alto quanto il font (ascendente + discendente): stessa altezza per ogni parola,
    linea di base in im.info["base"], così numeri ed etichette si allineano."""
    f = font(peso, size)
    asc, desc = f.getmetrics()
    x0, _, x1, _ = f.getbbox(testo)
    im = Image.new("RGBA", (x1 - x0 + 4, asc + desc + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - x0, 2), testo, font=f, fill=colore)
    im.info["base"] = asc + 2
    return im


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def con_alpha(im, a):
    if a >= 0.999:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def incolla(frame, im, xy, anchor="mm", a=1.0):
    if a <= 0.003:
        return
    x, y = xy
    w, h = im.size
    x -= {"l": 0, "m": w / 2, "r": w}[anchor[0]]
    y -= {"t": 0, "m": h / 2, "b": h, "s": im.info.get("base", h)}[anchor[1]]
    frame.alpha_composite(con_alpha(im, a), (int(round(x)), int(round(y))))


class Scena:
    """Una scena per blocco: visibile in [inizio, fine) con dissolvenza di 0.35 s ai bordi."""
    def __init__(self, inizio, fine, disegna):
        self.inizio, self.fine, self.disegna = inizio, fine, disegna

    def alpha(self, t):
        return min(ease((t - self.inizio) / 0.35) if self.inizio > 0 else 1.0, ease((self.fine - t) / 0.35))


def testo(frame, t, t0, s, peso, size, colore, xy, anchor="mm", ga=1.0, sale=24, t_out=None):
    """Testo che entra a t0 salendo di `sale` px; esce a t_out."""
    a = ease((t - t0) / 0.4) * ga
    if t_out is not None:
        a *= ease((t_out - t) / 0.3)
    dy = (1 - ease((t - t0) / 0.4)) * sale
    incolla(frame, sprite(s, peso, size, colore), (xy[0], xy[1] + dy), anchor, a)


def sfondo(w=W, h=H, logo=True):
    g = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(BG_TOP) * (1 - g) + np.array(BG_BOT) * g).repeat(w, axis=1).astype(np.uint8)
    im = Image.fromarray(arr, "RGB").convert("RGBA")
    if logo:
        ImageDraw.Draw(im).text((80, 64), "FAI I CONTI", font=font("ExtraBold", 30), fill=ACCENTO)
    return im


SFONDO = sfondo()


def pompa(frame, xy, a, col=TESTO):
    """Icona della pompa di benzina disegnata a mano (niente asset esterni)."""
    if a <= 0.003:
        return
    lay = Image.new("RGBA", (260, 320), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = col + (255,)
    d.rounded_rectangle((20, 30, 160, 300), 18, outline=c, width=12)
    d.rounded_rectangle((48, 66, 132, 140), 8, fill=c)
    d.rectangle((0, 290, 180, 310), fill=c)
    d.line((160, 120, 210, 120, 222, 140, 222, 240, 200, 260), fill=c, width=12, joint="curve")
    d.line((200, 256, 186, 230), fill=c, width=12)
    incolla(frame, lay, xy, "mm", a)


def riga_conto(frame, t, t0, segno, valore, etichetta, nota, y, ga, col_val=TESTO, x=760):
    y += 26  # y = centro visivo della riga; i testi stanno sulla stessa linea di base
    testo(frame, t, t0, segno, "Medium", 64, TENUE, (x - 30, y), "rs", ga)
    testo(frame, t, t0, valore, "Bold", 72, col_val, (x, y), "ls", ga)
    vw = sprite(valore, "Bold", 72, col_val).size[0]
    testo(frame, t, t0 + 0.1, etichetta, "Medium", 40, TENUE, (x + vw + 24, y), "ls", ga)
    if nota:
        testo(frame, t, t0 + 0.25, nota, "Medium", 26, ACCENTO if nota == "ipotesi" else TENUE,
              (x, y + 14), "lt", ga, sale=10)


# ---------- scene (una per blocco di script.md) ----------
T_B2, T_B3, T_B4 = t_di("facciamo"), t_di("aggiungi"), t_di("quindi")
T_FINE = PAROLE[-1]["fine"] + CODA


def scena1(frame, t, ga):
    # [VISUAL: numero "36.421 €" grande, che appare con un effetto di zoom]
    t0 = t_di("36.000") - 0.15
    testo(frame, t, 0.3, "Prezzo medio di listino di un'auto nuova", "SemiBold", 44, TENUE, (W / 2, 300), ga=ga)
    z = ease((t - t0) / 0.9)
    if z > 0:
        sp = sprite(f"{fmt(R['prezzo_medio_nuova'])} €", "ExtraBold", 230, TESTO)
        s = 0.55 + 0.45 * z
        sp = sp.resize((int(sp.size[0] * s), int(sp.size[1] * s)), Image.LANCZOS)
        incolla(frame, sp, (W / 2, 500), "mm", min(1, z * 1.6) * ga)
    testo(frame, t, t0 + 0.8, "Quattroruote Professional, feb 2026", "Medium", 28, TENUE, (W / 2, 650), ga=ga, sale=10)
    testo(frame, t, t_di("solo", 5), "…ed è solo l'inizio", "SemiBold", 52, ACCENTO, (W / 2, 760), ga=ga)


def scena2(frame, t, ga):
    # [VISUAL: icona pompa + calcolo riga per riga: 12.000 km · 6 l/100 km · 2,11 €/l = 1.519 € all'anno]
    pompa(frame, (420, 460), ease((t - T_B2) / 0.5) * ga)
    righe = [(t_di("12.000"), "", f"{fmt(R['km_anno'])} km", "all'anno", "ipotesi"),
             (t_di("6"), "×", f"{R['consumo_l_100km']:g} litri", "ogni 100 km", "ipotesi"),
             (t_di("benzina"), "×", f"{fmt_dec(R['benzina_euro_litro'])} €", "al litro", "MIMIT, 30 settembre 2026")]
    for i, (t0, segno, val, et, nota) in enumerate(righe):
        riga_conto(frame, t, t0, segno, val, et, nota, 250 + i * 150, ga)
    t_tot = t_di("sono") - 0.1
    a = ease((t - t_tot) / 0.4) * ga
    if a > 0:
        lay = Image.new("RGBA", (900, 6), LINEA + (255,))
        incolla(frame, lay, (760, 690), "lm", a)
    riga_conto(frame, t, t_tot, "=", f"{fmt(R['carburante_anno'])} €", "all'anno di carburante", None, 760, ga, ACCENTO)


def scena3(frame, t, ga):
    # [VISUAL: "+ 422 € RC auto (IVASS)", poi riga di somma: "≈ 1.941 € all'anno = 162 € al mese"]
    x = 640
    riga_conto(frame, t, T_B3 - 0.3, "", f"{fmt(R['carburante_anno'])} €", "carburante", None, 230, ga, x=x)
    riga_conto(frame, t, t_di("422") - 0.1, "+", f"{fmt(R['rc_auto_anno'])} €", "RC auto",
               "IVASS, premio medio II trim. 2026", 370, ga, COSTO, x=x)
    t_tot = t_di("totale") - 0.1
    a = ease((t - t_tot) / 0.4) * ga
    if a > 0:
        incolla(frame, Image.new("RGBA", (1000, 6), LINEA + (255,)), (x, 470), "lm", a)
    riga_conto(frame, t, t_tot, "≈", f"{fmt(R['totale_anno'])} €", "all'anno", None, 540, ga, ACCENTO, x=x)
    riga_conto(frame, t, t_di("circa", 31) - 0.1, "=", f"{fmt(R['totale_mese'])} €", "al mese", None, 660, ga, ACCENTO, x=x)
    # "E questo senza contare bollo, tagliandi e soprattutto la svalutazione."
    t_nc = t_di("senza") - 0.1
    testo(frame, t, t_nc, "Non inclusi:", "SemiBold", 36, TENUE, (x, 803), "ls", ga, sale=10)
    cx = x + sprite("Non inclusi:", "SemiBold", 36, TENUE).size[0] + 30
    for parola, chip in (("bollo", "bollo"), ("tagliandi", "tagliandi"), ("svalutazione", "svalutazione")):
        t0 = t_di(parola, 30) - 0.05
        f = font("SemiBold", 36)
        box = Image.new("RGBA", (int(f.getlength(chip)) + 48, 66), (0, 0, 0, 0))
        db = ImageDraw.Draw(box)
        db.rounded_rectangle((0, 0, box.size[0] - 1, 65), 22, outline=COSTO + (255,), width=3)
        db.text((box.size[0] / 2, 33), chip, font=f, fill=TESTO, anchor="mm")
        incolla(frame, box, (cx, 790 + (1 - ease((t - t0) / 0.4)) * 10), "lm", ease((t - t0) / 0.4) * ga)
        cx += box.size[0] + 20


def scena4(frame, t, ga):
    # [VISUAL: testo "Fai i conti" + "Non è consulenza finanziaria" in basso]
    testo(frame, t, T_B4 + 0.1, "Prima di firmare, non guardare solo la rata.", "SemiBold", 46, TENUE, (W / 2, 280), ga=ga)
    t_fai = t_di("fai") - 0.1
    z = ease((t - t_fai) / 0.7)
    if z > 0:
        sp = sprite("Fai i conti.", "ExtraBold", 190, ACCENTO)
        s = 0.8 + 0.2 * z
        sp = sp.resize((int(sp.size[0] * s), int(sp.size[1] * s)), Image.LANCZOS)
        incolla(frame, sp, (W / 2, 470), "mm", z * ga)
    testo(frame, t, t_di("prossimo") - 0.1, "Prossimo video: nuova contro usata, conti su 5 anni",
          "Medium", 40, TESTO, (W / 2, 660), ga=ga)
    # disclaimer sempre visibile nella scena, in basso sopra i sottotitoli
    testo(frame, t, T_B4 + 0.3, "Informazione generale, non è consulenza finanziaria", "Medium", 30, TENUE,
          (W / 2, 820), ga=ga, sale=0)


SCENE = [Scena(0.0, T_B2 - 0.15, scena1), Scena(T_B2 - 0.15, T_B3 - 0.4, scena2),
         Scena(T_B3 - 0.4, T_B4 - 0.15, scena3), Scena(T_B4 - 0.15, T_FINE + 1, scena4)]


def sottotitolo(frame, t):
    for i, c in enumerate(BATTUTE):
        if c["inizio"] <= t < c["fine"]:
            attiva = max([j for j, w in enumerate(c["parole"]) if w["inizio"] <= t] or [-1])
            incolla(frame, sprite_battuta(i, attiva), (W / 2, 955), "mm", 1.0)
            return


@lru_cache(None)
def sprite_battuta(i, attiva):
    f = font("SemiBold", 52)
    ws = [w["p"] for w in BATTUTE[i]["parole"]]
    sp = f.getlength(" ")
    larg = sum(f.getlength(w) for w in ws) + sp * (len(ws) - 1)
    im = Image.new("RGBA", (int(larg) + 64, 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), 16, fill=(0, 0, 0, 170))
    x = 32
    for j, w in enumerate(ws):
        d.text((x, 45), w, font=f, fill=ACCENTO if j == attiva else TESTO, anchor="lm")
        x += f.getlength(w) + sp
    return im


def fotogramma(t):
    frame = SFONDO.copy()
    for s in SCENE:
        if s.inizio - 0.01 <= t < s.fine + 0.01:
            s.disegna(frame, t, max(0.0, s.alpha(t)))
    sottotitolo(frame, t)
    return frame.convert("RGB")


# ---------- audio ----------
def musica(durata):
    """Tappeto musicale generato qui (niente diritti di terzi): accordi lenti Am-F-C-G, sinusoidi morbide."""
    t = np.arange(int(durata * SR)) / SR
    accordi = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 261.63, 329.63), (196.0, 246.94, 293.66)]
    dur = 4.0
    y = np.zeros_like(t)
    for k in range(int(durata / dur) + 1):
        a, b = k * dur, (k + 1) * dur + 1.5
        m = (t >= a) & (t < b)
        tt = t[m] - a
        env = np.minimum(1, tt / 1.2) * np.clip((b - a - tt) / 1.5, 0, 1)
        for f in accordi[k % 4]:
            y[m] += env * (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2.002 * f * tt)
                           + 0.5 * np.sin(2 * np.pi * f / 2 * tt))
    y *= np.minimum(1, t / 2.0) * np.clip((durata - t) / 2.0, 0, 1)
    return (y / np.abs(y).max() * 0.5).astype(np.float32)


def audio_finale(durata):
    musica(durata).tofile(DIR / "audio" / "_musica.f32")
    out = DIR / "audio" / "mix.wav"
    # voce + musica a -24 dB con ducking (sidechain sulla voce), limitatore a -1,5 dBTP
    filtro = ("[0:a]apad=whole_dur={d},asplit=2[v][sc];"
              "[1:a]volume=-24dB[m];[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=350[md];"
              "[v][md]amix=inputs=2:normalize=0,alimiter=limit=0.84:level=false[out]").format(d=durata)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(DIR / "audio" / "voce_montata.wav"),
                    "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(DIR / "audio" / "_musica.f32"),
                    "-filter_complex", filtro, "-map", "[out]", "-c:a", "pcm_s24le", str(out)], check=True)
    (DIR / "audio" / "_musica.f32").unlink()
    return out


def miniatura():
    im = sfondo(1280, 720, logo=False)
    d = ImageDraw.Draw(im)
    d.text((70, 70), "FAI I CONTI", font=font("ExtraBold", 34), fill=ACCENTO)
    d.text((70, 170), "Solo benzina + RC auto:", font=font("Bold", 64), fill=TESTO)
    d.text((62, 250), f"{fmt(R['totale_anno'])} €", font=font("ExtraBold", 230), fill=ACCENTO)
    d.text((70, 530), "all'anno. E non è finita.", font=font("Bold", 64), fill=TESTO)
    pompa(im, (1100, 500), 1.0, TENUE)
    im.convert("RGB").save(DIR / "miniatura.png")


def main():
    if "--frame" in sys.argv:
        t = float(sys.argv[sys.argv.index("--frame") + 1])
        fotogramma(t).save(DIR / "_anteprima_frame.png")
        return
    durata = T_FINE
    mix = audio_finale(durata)
    n = int(durata * FPS)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", str(mix), "-c:v", "libx264", "-preset", "medium",
                            "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest",
                            "-movflags", "+faststart", str(DIR / "video.mp4")], stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(fotogramma(i / FPS).tobytes())
        if i % (FPS * 10) == 0:
            print(f"  {i / FPS:5.1f} / {durata:.1f} s", flush=True)
    enc.stdin.close(); enc.wait()
    miniatura()
    print("battute sottotitoli:", len(BATTUTE))


if __name__ == "__main__":
    main()
