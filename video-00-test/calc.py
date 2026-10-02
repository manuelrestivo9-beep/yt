"""Video 00 (test) - Il conto veloce dell'auto: carburante + RC auto in un anno.
Parametri in cima, fonti in sources.md. Rilancia dopo ogni modifica: render.py legge risultati.json.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

PARAMS = {
    # --- DATI DA FONTE UFFICIALE / PUBBLICA ---
    "prezzo_medio_nuova": 36421,    # Quattroruote Professional, media listino, feb 2026
    "benzina_euro_litro": 2.11,     # MIMIT Osservaprezzi, media self rete stradale, 30 set 2026 (VOLATILE)
    "rc_auto_anno": 422,            # IVASS IPER, premio medio RC auto, II trim. 2026
    # --- IPOTESI (dichiarate nel video) ---
    "km_anno": 12000,
    "consumo_l_100km": 6.0,
}


def main(p=PARAMS):
    carburante = p["km_anno"] / 100 * p["consumo_l_100km"] * p["benzina_euro_litro"]
    totale = carburante + p["rc_auto_anno"]
    r = {**p, "carburante_anno": round(carburante), "totale_anno": round(totale),
         "totale_mese": round(totale / 12)}
    (OUT / "risultati.json").write_text(json.dumps(r, ensure_ascii=False, indent=2))
    return r


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
