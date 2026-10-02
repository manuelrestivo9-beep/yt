# Canale "Fai i conti" — istruzioni di progetto

Canale YouTube faceless in italiano sulla finanza personale. Ogni video prende una scelta di soldi reale e la calcola con numeri veri.
La voce è dell'autore (registrata da lui). Claude prepara script, calcoli, grafici e montaggio.

## Regole di contenuto
- Ogni cifra ha una fonte ufficiale in `sources.md` (ISTAT, Banca d'Italia, IVASS, INPS, ACI, MIMIT). Se non c'è, è un'ipotesi e va dichiarata nel video.
- Mai consigli personalizzati ("compra X"). Solo calcoli, confronti, spiegazioni. Chiudere sempre con "non è consulenza finanziaria".
- Niente titoli allarmisti o clickbait su pensioni/conti.
- Ogni video deve avere calcoli e grafici propri, mai riutilizzare lo stesso schema visivo identico.

## Struttura di una cartella video
`video-NN-tema/` con: `script.md`, `calc.py` (parametri in cima), `risultati.json`, grafici `.png`, `voce.wav` (registrata dall'autore, originale intoccabile), `audio/` (versioni pulita e montata, trascrizione, tagli), `video.mp4` (output).

## Pipeline audio (quando c'è `voce.wav`)

Claude Code NON può ascoltare l'audio: lavora con trascrizione e misure (silencedetect, loudnorm, spettro). Non dichiarare mai un audio "ottimo" o "pulito": riporta le misure e lascia il giudizio all'autore.

Convenzioni di registrazione dell'autore:
- All'inizio del file ci sono ~10 secondi di silenzio (profilo del rumore di fondo).
- Se sbaglia, fa ~2 secondi di silenzio e ripete la frase dall'inizio.
- Un blocco di `script.md` alla volta, stessa distanza dal microfono.

Passi, in ordine. Non cancellare mai il file originale: lavora su copie in `audio/`.
1. **Analisi**: durata, livello (LUFS e picco), rumore di fondo misurato nei primi 10 secondi. Segnala se c'è clipping (picchi a 0 dB) o eco evidente: in quel caso dillo all'autore, i filtri non lo risolvono.
2. **Pulizia**: filtro passa-alto ~80 Hz, riduzione rumore (`afftdn` di ffmpeg con il profilo del silenzio iniziale, oppure DeepFilterNet se installato), de-esser leggero solo se le "s" superano la soglia. Poi normalizzazione a -16 LUFS (`loudnorm` a due passate), picco massimo -1 dBTP. Salva `audio/voce_pulita.wav`.
3. **Trascrizione**: Whisper (faster-whisper se disponibile), lingua `it`, timestamp per parola → `audio/trascrizione.json`.
4. **Allineamento con lo script**: confronta la trascrizione con `script.md`, blocco per blocco. Dove una frase compare più volte (ripetizioni dopo un errore, riconoscibili dai ~2 s di silenzio prima), tieni per default l'ULTIMA ripetizione e segna le altre come scartate.
5. **Lista dei tagli**: scrivi `audio/tagli.json` con, per ogni taglio, inizio, fine, motivo (`ripetizione`, `pausa lunga`, `intercalare`, `respiro lungo`, `errore`) e il testo tagliato. Regole: pause oltre 0,7 s ridotte a ~0,35 s; non tagliare mai dentro una parola (lascia 40-60 ms di margine); non tagliare i respiri brevi, rendono il parlato naturale; intercalari ("eh", "ehm") solo se isolati.
6. **Montaggio audio**: applica i tagli, dissolvenza incrociata di 15-30 ms su ogni giunzione. Salva `audio/voce_montata.wav` e un'anteprima `audio/anteprima.mp3`.
7. **STOP e verifica**: mostra all'autore il riepilogo (durata prima/dopo, numero di tagli, quali ripetizioni sono state scelte e con che testo) e chiedi di ascoltare l'anteprima. NON procedere al video finché l'autore non approva o chiede correzioni. Se l'autore indica un taglio sbagliato (con il tempo), correggi `tagli.json` e rigenera.

Se la trascrizione di una frase è dubbia (bassa confidenza) o non c'è un'ultima ripetizione chiara, non decidere da solo: elencala all'autore.

## Pipeline video (solo dopo l'approvazione dell'audio)
1. Usa `audio/voce_montata.wav` come traccia principale e i tempi di `trascrizione.json` aggiornati dopo i tagli.
2. Per ogni blocco di `script.md` crea la scena indicata in [VISUAL]: grafici da `calc.py`, testi animati, b-roll gratuito (citare l'autore in descrizione).
3. Sottotitoli burned-in dalla trascrizione, musica di sottofondo a volume basso (ducking sotto la voce).
4. Esporta 1080p 16:9 con ffmpeg → `video.mp4`. Esporta anche la miniatura.
5. Genera titolo, descrizione (con fonti e disclaimer) e capitoli.

## Prima di ogni video
Aggiorna i dati volatili (carburanti, tassi) il giorno della registrazione.
