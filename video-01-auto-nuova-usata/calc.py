"""Video 01 - Auto nuova vs usata: costo reale in 5 anni.
Tutti i parametri sono in PARAMS. Cambia i numeri, rilancia, ricevi tabella e grafico.
Fonti per ogni parametro: vedi sources.md (stessa cartella)
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ANNI = 5
OUT = Path(__file__).resolve().parent  # output sempre nella cartella del video

PARAMS = {
    # --- DATI DA FONTE UFFICIALE / PUBBLICA ---
    "prezzo_nuova": 26349,          # Quattroruote Professional, media listino segmento B, feb 2026
    "rc_auto_anno": 422,            # IVASS IPER, premio medio RC auto, II trim. 2026
    "benzina_euro_litro": 2.11,     # MIMIT Osservaprezzi, media self rete stradale, 30 set 2026 (VOLATILE)
    # --- IPOTESI (da dichiarare nel video) ---
    "km_anno": 12000,
    "consumo_l_100km": 6.0,
    "svalutazione_nuova_5a": 0.45,  # fonte secondaria Facile.it: 40-50% nei primi 4 anni
    "usata_prezzo_pct_nuovo": 0.62, # usata di 3 anni = 62% del prezzo nuovo (ipotesi)
    "svalutazione_usata_5a": 0.30,  # perdita % del prezzo pagato in 5 anni, partendo da 3 anni di eta (ipotesi)
    "bollo_anno": 180,              # dipende da kW e regione: SOSTITUIRE col calcolo ACI
    "manutenzione_nuova_anno": 400,
    "manutenzione_usata_anno": 750,
    "rendimento_denaro": 0.02,      # costo opportunita' del capitale (conto deposito ipotetico)
}

def scenario(prezzo, svalut, manut, p=PARAMS):
    carburante = p["km_anno"] / 100 * p["consumo_l_100km"] * p["benzina_euro_litro"]
    voci = {
        "Svalutazione": prezzo * svalut,
        "Carburante": carburante * ANNI,
        "Assicurazione RC": p["rc_auto_anno"] * ANNI,
        "Bollo": p["bollo_anno"] * ANNI,
        "Manutenzione": manut * ANNI,
        "Soldi 'fermi' nell'auto": prezzo * p["rendimento_denaro"] * ANNI,
    }
    voci["TOTALE"] = sum(voci.values())
    return {k: round(v) for k, v in voci.items()}

def main(p=PARAMS):
    nuova = scenario(p["prezzo_nuova"], p["svalutazione_nuova_5a"], p["manutenzione_nuova_anno"])
    prezzo_usata = p["prezzo_nuova"] * p["usata_prezzo_pct_nuovo"]
    usata = scenario(prezzo_usata, p["svalutazione_usata_5a"], p["manutenzione_usata_anno"])
    risultato = {"nuova": nuova, "usata": usata, "prezzo_usata": round(prezzo_usata),
                 "differenza_totale": nuova["TOTALE"] - usata["TOTALE"],
                 "differenza_al_mese": round((nuova["TOTALE"] - usata["TOTALE"]) / (ANNI * 12)),
                 "costo_mese_nuova": round(nuova["TOTALE"] / (ANNI * 12)),
                 "costo_mese_usata": round(usata["TOTALE"] / (ANNI * 12))}
    with open(OUT / "risultati.json", "w") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)

    voci = [k for k in nuova if k != "TOTALE"]
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=200)
    colori = ["#C0392B", "#E67E22", "#2980B9", "#7F8C8D", "#27AE60", "#8E44AD"]
    for i, (nome, d) in enumerate([("Nuova", nuova), ("Usata", usata)]):
        base = 0
        for j, v in enumerate(voci):
            ax.barh(i, d[v], left=base, color=colori[j], label=v if i == 0 else None)
            base += d[v]
        ax.text(base + 400, i, f"{d['TOTALE']:,} €".replace(",", "."), va="center", fontsize=14, fontweight="bold")
    ax.set_yticks([0, 1]); ax.set_yticklabels(["Nuova", "Usata"], fontsize=14)
    ax.invert_yaxis(); ax.set_xlim(0, max(nuova["TOTALE"], usata["TOTALE"]) * 1.2)
    ax.set_title("Costo reale di 5 anni di auto", fontsize=16, fontweight="bold")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=10, ncol=3, frameon=False)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    plt.tight_layout(); plt.savefig(OUT / "grafico_totale.png")
    return risultato

if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
