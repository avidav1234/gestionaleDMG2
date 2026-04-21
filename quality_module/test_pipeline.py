"""
Test del pipeline completo con dati reali dal report c.4296 CHIUSURA (pagina 1).
"""
import sys
sys.path.insert(0, '/home/claude/quality_module')

import json
from models import InspectionPoint, InspectionSection, InspectionMetadata, InspectionReport
from analysis import analyze_report, compute_section_stats, analyze_directions, decompose_error, fingerprint_root_causes

# ──────────────────────────────────────────────────────────
# Dati reali dalla pagina 1 del report PDF (CHIUSURA P1-P28)
# Estratti dal rendering del documento
# ──────────────────────────────────────────────────────────

page1_data = [
    # name,   Xm,       Xn,       Dx,     Ym,        Yn,        Dy,     Zm,       Zn,       Dz,     TMin,   TMax,  Dev,    Dir
    ("P1",   191.729, 191.729,  0.000,  -54.043,  -54.043,  0.000, -17.227, -17.303,  0.076, -0.020, 0.020,  0.076, "+z"),
    ("P2",   172.355, 172.355,  0.000,  -73.954,  -73.954,  0.000, -17.212, -17.303,  0.091, -0.020, 0.020,  0.091, "+z"),
    ("P3",   164.736, 164.666,  0.070,  -76.564,  -76.639,  0.075, -14.324, -14.342,  0.018, -0.020, 0.020,  0.104, "+y"),
    ("P4",   164.486, 164.456,  0.030,  -79.168,  -79.200,  0.032,  -1.590,  -1.596,  0.006, -0.020, 0.020,  0.044, "+y"),
    ("P5",   172.617, 172.598,  0.018,  -85.684,  -85.741,  0.057,  -1.579,  -1.594,  0.014, -0.020, 0.020,  0.061, "+y"),
    ("P6",   172.552, 172.532,  0.021,  -82.168,  -82.284,  0.116, -14.100, -14.134,  0.034, -0.020, 0.020,  0.122, "+y"),
    ("P7",   180.074, 180.163, -0.089,  -79.159,  -79.243,  0.083, -14.173, -14.206,  0.033, -0.020, 0.020,  0.127, "-x"),
    ("P8",   180.219, 180.285, -0.066,  -83.570,  -83.638,  0.068,  -2.626,  -2.652,  0.026, -0.020, 0.020,  0.098, "+y"),
    ("P9",   201.699, 201.765, -0.065,  -56.364,  -56.425,  0.061, -13.297, -13.321,  0.024, -0.020, 0.020,  0.093, "-x"),
    ("P10",  201.868, 201.922, -0.053,  -60.524,  -60.574,  0.050,  -2.313,  -2.333,  0.020, -0.020, 0.020,  0.076, "-x"),
    ("P11",  206.564, 206.564,  0.000,  -67.137,  -67.137,  0.000,   0.046,   0.000,  0.046, -0.020, 0.020,  0.046, "+z"),
    ("P12",  207.132, 207.132,  0.000, -162.181, -162.181,  0.000,   0.055,   0.000,  0.055, -0.020, 0.020,  0.055, "+z"),
    ("P13",  197.074, 197.074,  0.000, -171.035, -171.132,  0.097,   6.032,   6.015,  0.017, -0.020, 0.020,  0.099, "+y"),
    ("P14",  211.503, 211.474,  0.030, -173.709, -173.753,  0.044,   5.832,   5.821,  0.010, -0.020, 0.020,  0.054, "+y"),
    ("P15",  218.934, 218.876,  0.058, -193.053, -193.057,  0.003,   5.890,   5.885,  0.005, -0.020, 0.020,  0.058, "+x"),
    ("P16",  224.127, 224.098,  0.029, -293.123, -293.125,  0.002,   6.139,   6.136,  0.003, -0.020, 0.020,  0.029, "+x"),
    ("P17",  221.598, 221.565,  0.033, -293.069, -293.071,  0.002,  35.024,  35.021,  0.003, -0.020, 0.020,  0.033, "+x"),
    ("P18",  216.420, 216.396,  0.024, -194.029, -194.031,  0.001,  34.775,  34.775,  0.002, -0.020, 0.020,  0.024, "+x"),
    ("P19",  209.181, 209.152,  0.029, -178.765, -178.810,  0.044,  34.727,  34.717,  0.010, -0.020, 0.020,  0.054, "+y"),
    ("P20",  207.476, 207.435,  0.041, -182.949, -183.003,  0.054,  46.373,  46.315,  0.058, -0.020, 0.020,  0.089, "+z"),
    ("P21",  207.490, 207.457,  0.032, -198.374, -198.377,  0.003,  50.379,  50.313,  0.067, -0.020, 0.020,  0.074, "+z"),
    ("P22",  215.404, 215.354,  0.050, -297.927, -297.931,  0.004,  50.353,  50.289,  0.064, -0.020, 0.020,  0.081, "+z"),
    ("P23",  195.264, 195.264,  0.000, -297.757, -297.758,  0.000,  53.671,  53.657,  0.013, -0.020, 0.020,  0.013, "+z"),
    ("P24",  196.108, 196.108,  0.000, -197.555, -197.555, -0.000,  51.898,  51.909, -0.011, -0.020, 0.020, -0.011, "-z"),
    ("P25",  195.924, 195.924,  0.000, -180.333, -180.419,  0.086,  46.227,  46.155,  0.073, -0.020, 0.020,  0.113, "+y"),
    ("P26",  195.718, 195.718,  0.000, -175.804, -175.903,  0.100,  33.095,  33.077,  0.018, -0.020, 0.020,  0.101, "+y"),
    ("P27",  140.413, 140.413,  0.000, -181.601, -181.676,  0.075,  47.560,  47.479,  0.080, -0.020, 0.020,  0.110, "+z"),
    ("P28",  140.210, 140.210,  0.000, -176.185, -176.290,  0.105,  35.287,  35.268,  0.019, -0.020, 0.020,  0.107, "+y"),
]

# Costruisci i punti
points = []
for d in page1_data:
    p = InspectionPoint(
        name=d[0], section="CHIUSURA",
        xm=d[1], xn=d[2], dx=d[3],
        ym=d[4], yn=d[5], dy=d[6],
        zm=d[7], zn=d[8], dz=d[9],
        tmin=d[10], tmax=d[11],
        dev=d[12], direction=d[13],
    )
    points.append(p)

# Crea sezione e report
section = InspectionSection(
    name="CHIUSURA",
    tolerance_min=-0.020,
    tolerance_max=0.020,
    points=points,
)

metadata = InspectionMetadata(
    drawing_number="ID24103D.20201A1",
    part_code="c.4296",
    part_type="PSA DCT MHEV #19",
    description="TRANSMISSION HOUSING - BOTTOM SLIDER",
    client="TEKSID ALUMINUM S.R.L.",
    operator="V. Parmiggiani",
    inspection_date=None,  # 2019-12-25
    total_pages=21,
    software="SurferNT",
)

report = InspectionReport(
    metadata=metadata,
    sections=[section],
    source_file="4296-1D24103D_20201A1_Carrello-Inferiore-REPORT-CMM.pdf",
)

# ──────────────────────────────────────────────────────────
# ESEGUI ANALISI COMPLETA
# ──────────────────────────────────────────────────────────

print("=" * 70)
print("DMGDesk Quality Intelligence — Analisi Report c.4296")
print("=" * 70)

# 1. Summary
summary = report.summary()
print(f"\n{'─'*50}")
print(f"RIEPILOGO")
print(f"{'─'*50}")
print(f"Disegno:  {summary['metadata']['drawing']}")
print(f"Codice:   {summary['metadata']['part_code']}")
print(f"Cliente:  {summary['metadata']['client']}")
print(f"Punti:    {summary['totals']['points']}")
print(f"OK:       {summary['totals']['ok']}")
print(f"WARNING:  {summary['totals']['warning']}")
print(f"NOK:      {summary['totals']['nok']}")
print(f"Conform.: {summary['totals']['conformity_pct']}%")

# 2. Statistiche sezione
print(f"\n{'─'*50}")
print(f"STATISTICHE SEZIONE CHIUSURA (pag.1, P1-P28)")
print(f"{'─'*50}")
stats = compute_section_stats(section)
print(f"Punti totali:      {stats.total_points}")
print(f"OK/WARNING/NOK:    {stats.ok}/{stats.warning}/{stats.nok}")
print(f"Conformità:        {stats.conformity_pct}%")
print(f"Dev media:         {stats.mean_dev} mm")
print(f"Dev mediana:       {stats.median_dev} mm")
print(f"Dev std:           {stats.std_dev} mm")
print(f"Dev max:           {stats.max_dev} mm ({stats.worst_point_name}, dir {stats.worst_point_dir})")
print(f"Cp:                {stats.cp}")
print(f"Cpk:               {stats.cpk}")
print(f"Dir predominante:  {stats.dominant_direction} ({stats.direction_coherence_pct}%)")

# 3. Analisi direzionale
print(f"\n{'─'*50}")
print(f"ANALISI DIREZIONALE")
print(f"{'─'*50}")
dir_analysis = analyze_directions(points)
print(f"Vettore medio:     Dx={dir_analysis.mean_dx} Dy={dir_analysis.mean_dy} Dz={dir_analysis.mean_dz}")
print(f"Magnitudine:       {dir_analysis.mean_vector_magnitude} mm")
print(f"Coerenza:          {dir_analysis.coherence} ({dir_analysis.coherence*100:.0f}%)")
print(f"Direzione media:   {dir_analysis.mean_direction}")
print(f"Tipo errore:       {dir_analysis.error_type}")
print(f"\nDistribuzione direzioni:")
for d, pct in dir_analysis.direction_distribution.items():
    print(f"  {d}: {pct}%")
print(f"\n{dir_analysis.error_description}")

# 4. Decomposizione errore
print(f"\n{'─'*50}")
print(f"DECOMPOSIZIONE ERRORE SISTEMATICO")
print(f"{'─'*50}")
decomp = decompose_error(section)
print(f"Traslazione:       Tx={decomp.tx} Ty={decomp.ty} Tz={decomp.tz}")
print(f"Impatto trasl.:    {decomp.translation_pct}% della deviazione totale")
print(f"Dev residua media: {decomp.residual_mean_dev} mm")
print(f"Dev residua max:   {decomp.residual_max_dev} mm")
print(f"Conformità prima:  {stats.conformity_pct}%")
print(f"Conformità dopo:   {decomp.conformity_after_correction_pct}%")
if decomp.persistent_nok:
    print(f"\nPunti NOK persistenti ({len(decomp.persistent_nok)}):")
    for pnok in decomp.persistent_nok[:5]:
        print(f"  {pnok['name']}: originale={pnok['original_dev']}mm → residuo={pnok['residual_dev']}mm")
print(f"\n{decomp.description}")

# 5. Root cause fingerprinting
print(f"\n{'─'*50}")
print(f"DIAGNOSI ROOT CAUSE")
print(f"{'─'*50}")
causes = fingerprint_root_causes(section, dir_analysis, decomp)
if causes:
    for i, cause in enumerate(causes):
        print(f"\n{'▸'} {cause.cause} (confidenza: {cause.confidence_pct}%)")
        print(f"  Pattern: {cause.pattern_match}")
        print(f"  Azione:  {cause.suggested_action}")
else:
    print("Nessun pattern dominante identificato.")

# 6. Full analysis
print(f"\n{'─'*50}")
print(f"DIAGNOSI GLOBALE")
print(f"{'─'*50}")
full = analyze_report(report)
print(full.global_diagnosis)

# Export come JSON per verifica
print(f"\n{'─'*50}")
print(f"EXPORT JSON (primi 3 punti)")
print(f"{'─'*50}")
export = {
    "metadata": summary["metadata"],
    "sections": [{
        "name": "CHIUSURA",
        "tolerance": "±0.020",
        "stats": {
            "total": stats.total_points,
            "ok": stats.ok,
            "nok": stats.nok,
            "conformity_pct": stats.conformity_pct,
            "mean_dev": stats.mean_dev,
            "cpk": stats.cpk,
        },
        "directional": {
            "coherence": dir_analysis.coherence,
            "error_type": dir_analysis.error_type,
            "mean_direction": dir_analysis.mean_direction,
        },
        "decomposition": {
            "translation_pct": decomp.translation_pct,
            "tx": decomp.tx, "ty": decomp.ty, "tz": decomp.tz,
            "conformity_after_correction": decomp.conformity_after_correction_pct,
        },
        "root_causes": [
            {"cause": c.cause, "confidence": c.confidence_pct}
            for c in causes
        ],
    }],
}
print(json.dumps(export, indent=2))
