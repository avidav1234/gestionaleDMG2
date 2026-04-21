"""
DMGDesk Quality Intelligence — Analysis Engine
Analisi profonda dei dati di collaudo:
- Statistiche per sezione
- Analisi direzionale dei vettori di deviazione
- Decomposizione errore sistematico (traslazione + rotazione + residuo)
- Fingerprinting root cause
"""

import math
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter

from models import InspectionReport, InspectionSection, InspectionPoint, PointStatus


# ──────────────────────────────────────────────────────────
# STATISTICHE SEZIONE
# ──────────────────────────────────────────────────────────

@dataclass
class SectionStats:
    """Statistiche per una sezione del report."""
    name: str
    total_points: int
    ok: int
    warning: int
    nok: int
    conformity_pct: float
    
    mean_dev: float
    median_dev: float
    std_dev: float
    max_dev: float
    min_dev: float
    
    # Cp/Cpk
    cp: Optional[float] = None
    cpk: Optional[float] = None
    
    # Punto peggiore
    worst_point_name: str = ""
    worst_point_dev: float = 0.0
    worst_point_dir: str = ""
    
    # Direzione predominante
    dominant_direction: str = ""
    direction_coherence_pct: float = 0.0


def compute_section_stats(section: InspectionSection) -> SectionStats:
    """Calcola le statistiche complete per una sezione."""
    points = section.points
    if not points:
        return SectionStats(
            name=section.name, total_points=0,
            ok=0, warning=0, nok=0, conformity_pct=100.0,
            mean_dev=0, median_dev=0, std_dev=0, max_dev=0, min_dev=0,
        )
    
    devs = [abs(p.dev) for p in points]
    signed_devs = [p.dev for p in points]
    n = len(devs)
    
    mean_dev = sum(devs) / n
    sorted_devs = sorted(devs)
    median_dev = sorted_devs[n // 2] if n % 2 else (sorted_devs[n//2 - 1] + sorted_devs[n//2]) / 2
    
    variance = sum((d - mean_dev) ** 2 for d in devs) / max(n - 1, 1)
    std_dev = math.sqrt(variance)
    
    # Cp/Cpk
    tolerance_range = section.tolerance_max - section.tolerance_min
    signed_mean = sum(signed_devs) / n
    signed_std = math.sqrt(sum((d - signed_mean) ** 2 for d in signed_devs) / max(n - 1, 1))
    
    cp = None
    cpk = None
    if signed_std > 0:
        cp = tolerance_range / (6 * signed_std)
        cpu = (section.tolerance_max - signed_mean) / (3 * signed_std)
        cpl = (signed_mean - section.tolerance_min) / (3 * signed_std)
        cpk = min(cpu, cpl)
    
    worst = max(points, key=lambda p: abs(p.dev))
    
    # Direzione predominante
    dir_counts = Counter(p.direction for p in points)
    dominant_dir = dir_counts.most_common(1)[0] if dir_counts else ("", 0)
    coherence = (dominant_dir[1] / n * 100) if n > 0 else 0
    
    return SectionStats(
        name=section.name,
        total_points=n,
        ok=section.ok_count,
        warning=section.warning_count,
        nok=section.nok_count,
        conformity_pct=round(section.conformity_pct, 1),
        mean_dev=round(mean_dev, 4),
        median_dev=round(median_dev, 4),
        std_dev=round(std_dev, 4),
        max_dev=round(max(devs), 4),
        min_dev=round(min(devs), 4),
        cp=round(cp, 3) if cp else None,
        cpk=round(cpk, 3) if cpk else None,
        worst_point_name=worst.name,
        worst_point_dev=round(worst.dev, 4),
        worst_point_dir=worst.direction,
        dominant_direction=dominant_dir[0],
        direction_coherence_pct=round(coherence, 1),
    )


# ──────────────────────────────────────────────────────────
# ANALISI DIREZIONALE
# ──────────────────────────────────────────────────────────

@dataclass
class DirectionalAnalysis:
    """Analisi del campo vettoriale delle deviazioni."""
    # Componenti medie
    mean_dx: float = 0.0
    mean_dy: float = 0.0
    mean_dz: float = 0.0
    
    # Magnitudine del vettore medio
    mean_vector_magnitude: float = 0.0
    
    # Coerenza: quanto i vettori puntano nella stessa direzione (0-1)
    coherence: float = 0.0
    
    # Direzione del vettore medio
    mean_direction: str = ""
    
    # Distribuzione direzioni
    direction_distribution: dict = field(default_factory=dict)
    
    # Tipo di errore
    error_type: str = ""  # "SYSTEMATIC", "RANDOM", "MIXED"
    error_description: str = ""


def analyze_directions(points: list[InspectionPoint]) -> DirectionalAnalysis:
    """Analizza il campo vettoriale delle deviazioni."""
    if not points:
        return DirectionalAnalysis()
    
    n = len(points)
    
    # Componenti medie
    mean_dx = sum(p.dx for p in points) / n
    mean_dy = sum(p.dy for p in points) / n
    mean_dz = sum(p.dz for p in points) / n
    
    mean_mag = math.sqrt(mean_dx**2 + mean_dy**2 + mean_dz**2)
    
    # Magnitudine media delle deviazioni individuali
    individual_mags = [math.sqrt(p.dx**2 + p.dy**2 + p.dz**2) for p in points]
    mean_individual_mag = sum(individual_mags) / n
    
    # Coerenza: rapporto tra magnitudine del vettore medio e media delle magnitudini
    # Se tutti puntano nella stessa direzione: coerenza ≈ 1
    # Se casuali: coerenza ≈ 0
    coherence = mean_mag / mean_individual_mag if mean_individual_mag > 0 else 0
    
    # Direzione predominante del vettore medio
    abs_components = {'x': abs(mean_dx), 'y': abs(mean_dy), 'z': abs(mean_dz)}
    dominant_axis = max(abs_components, key=abs_components.get)
    dominant_value = {'x': mean_dx, 'y': mean_dy, 'z': mean_dz}[dominant_axis]
    mean_direction = f"{'+' if dominant_value >= 0 else '-'}{dominant_axis}"
    
    # Distribuzione direzioni
    dir_counts = Counter(p.direction for p in points)
    dir_dist = {d: round(c / n * 100, 1) for d, c in dir_counts.most_common()}
    
    # Classificazione tipo di errore
    if coherence > 0.7:
        error_type = "SYSTEMATIC"
        error_desc = (
            f"Errore SISTEMATICO: il {coherence*100:.0f}% delle deviazioni punta in direzione {mean_direction}. "
            f"Vettore medio: Dx={mean_dx:.4f} Dy={mean_dy:.4f} Dz={mean_dz:.4f} (mag={mean_mag:.4f}mm). "
            f"Probabile causa: offset di riferimento, staffaggio, o traslazione pezzo."
        )
    elif coherence > 0.3:
        error_type = "MIXED"
        error_desc = (
            f"Errore MISTO: tendenza direzionale verso {mean_direction} (coerenza {coherence*100:.0f}%) "
            f"ma con significativa dispersione. Possibile combinazione di errore sistematico e processo."
        )
    else:
        error_type = "RANDOM"
        error_desc = (
            f"Errore CASUALE: le deviazioni non hanno direzione predominante (coerenza {coherence*100:.0f}%). "
            f"Il processo è la causa principale, non il setup."
        )
    
    return DirectionalAnalysis(
        mean_dx=round(mean_dx, 5),
        mean_dy=round(mean_dy, 5),
        mean_dz=round(mean_dz, 5),
        mean_vector_magnitude=round(mean_mag, 5),
        coherence=round(coherence, 3),
        mean_direction=mean_direction,
        direction_distribution=dir_dist,
        error_type=error_type,
        error_description=error_desc,
    )


# ──────────────────────────────────────────────────────────
# DECOMPOSIZIONE ERRORE SISTEMATICO
# ──────────────────────────────────────────────────────────

@dataclass
class ErrorDecomposition:
    """Decomposizione dell'errore in componenti sistematiche + residuo."""
    # Traslazione stimata (offset pezzo)
    tx: float = 0.0
    ty: float = 0.0
    tz: float = 0.0
    
    # Impatto percentuale della traslazione
    translation_pct: float = 0.0
    
    # Deviazione residua dopo rimozione traslazione
    residual_mean_dev: float = 0.0
    residual_max_dev: float = 0.0
    
    # Quanti punti rientrano in tolleranza dopo rimozione traslazione
    ok_after_correction: int = 0
    total_points: int = 0
    conformity_after_correction_pct: float = 0.0
    
    # Punti che restano NOK anche dopo correzione
    persistent_nok: list = field(default_factory=list)
    
    description: str = ""


def decompose_error(section: InspectionSection) -> ErrorDecomposition:
    """
    Decompone l'errore in traslazione (sistematico) + residuo (processo).
    
    Logica: calcola la traslazione media (Tx, Ty, Tz) che minimizza
    la somma dei quadrati delle deviazioni residue. Per un primo approccio,
    usiamo semplicemente la media di Dx, Dy, Dz come stima della traslazione.
    Poi calcoliamo le deviazioni residue dopo la rimozione della traslazione.
    """
    points = section.points
    if not points:
        return ErrorDecomposition()
    
    n = len(points)
    
    # Stima traslazione come media delle deviazioni per asse
    tx = sum(p.dx for p in points) / n
    ty = sum(p.dy for p in points) / n
    tz = sum(p.dz for p in points) / n
    
    translation_mag = math.sqrt(tx**2 + ty**2 + tz**2)
    
    # Calcola deviazioni residue dopo rimozione traslazione
    residuals = []
    ok_count = 0
    persistent_nok = []
    
    for p in points:
        # Rimuovi la componente di traslazione
        res_dx = p.dx - tx
        res_dy = p.dy - ty
        res_dz = p.dz - tz
        res_dev = math.sqrt(res_dx**2 + res_dy**2 + res_dz**2)
        residuals.append(res_dev)
        
        if abs(res_dev) <= p.tmax:
            ok_count += 1
        else:
            persistent_nok.append({
                "name": p.name,
                "original_dev": round(p.dev, 4),
                "residual_dev": round(res_dev, 4),
                "direction": p.direction,
            })
    
    mean_residual = sum(residuals) / n
    max_residual = max(residuals)
    
    # Calcola impatto percentuale della traslazione
    original_total_dev = sum(abs(p.dev) for p in points)
    residual_total_dev = sum(residuals)
    
    if original_total_dev > 0:
        translation_pct = max(0, (1 - residual_total_dev / original_total_dev)) * 100
    else:
        translation_pct = 0
    
    conformity_after = (ok_count / n * 100) if n > 0 else 100
    
    # Descrizione
    original_nok = section.nok_count
    recovered = original_nok - len(persistent_nok)
    
    desc = (
        f"Traslazione stimata: Tx={tx:.4f} Ty={ty:.4f} Tz={tz:.4f} (mag={translation_mag:.4f}mm). "
        f"La traslazione spiega il {translation_pct:.0f}% della deviazione totale. "
    )
    
    if recovered > 0:
        desc += (
            f"Rimuovendo la traslazione, {recovered} punti su {original_nok} NOK "
            f"rientrerebbero in tolleranza (conformità: {section.conformity_pct:.1f}% → {conformity_after:.1f}%). "
        )
    
    if persistent_nok:
        worst_persistent = max(persistent_nok, key=lambda x: x['residual_dev'])
        desc += (
            f"Restano {len(persistent_nok)} punti NOK anche dopo correzione. "
            f"Il peggiore è {worst_persistent['name']} (residuo {worst_persistent['residual_dev']}mm) — "
            f"questo punto ha un problema di processo, non di setup."
        )
    
    return ErrorDecomposition(
        tx=round(tx, 5),
        ty=round(ty, 5),
        tz=round(tz, 5),
        translation_pct=round(translation_pct, 1),
        residual_mean_dev=round(mean_residual, 4),
        residual_max_dev=round(max_residual, 4),
        ok_after_correction=ok_count,
        total_points=n,
        conformity_after_correction_pct=round(conformity_after, 1),
        persistent_nok=persistent_nok,
        description=desc,
    )


# ──────────────────────────────────────────────────────────
# ROOT CAUSE FINGERPRINTING
# ──────────────────────────────────────────────────────────

@dataclass
class RootCauseFingerprint:
    """Risultato del fingerprinting per una possibile root cause."""
    cause: str
    confidence_pct: float
    pattern_match: str
    suggested_action: str


def fingerprint_root_causes(
    section: InspectionSection,
    directional: DirectionalAnalysis,
    decomposition: ErrorDecomposition,
) -> list[RootCauseFingerprint]:
    """
    Analizza i pattern di deviazione e suggerisce le root cause più probabili.
    """
    candidates = []
    points = section.points
    if not points:
        return candidates
    
    # ── 1. ERRORE DI RIFERIMENTO (offset zero pezzo) ──
    if directional.coherence > 0.7 and decomposition.translation_pct > 50:
        confidence = min(95, directional.coherence * 100 * (decomposition.translation_pct / 100))
        candidates.append(RootCauseFingerprint(
            cause="ERRORE DI RIFERIMENTO",
            confidence_pct=round(confidence, 0),
            pattern_match=(
                f"Traslazione dominante ({decomposition.translation_pct:.0f}% dell'errore). "
                f"Coerenza direzionale {directional.coherence*100:.0f}% verso {directional.mean_direction}. "
                f"Traslazione stimata: X={decomposition.tx:.4f} Y={decomposition.ty:.4f} Z={decomposition.tz:.4f}mm."
            ),
            suggested_action=(
                f"Verificare e correggere zero pezzo (G54/G55). "
                f"Applicare offset: X={-decomposition.tx:.4f} Y={-decomposition.ty:.4f} Z={-decomposition.tz:.4f}. "
                f"Ri-tastare il pezzo prima della prossima lavorazione."
            ),
        ))
    
    # ── 2. USURA UTENSILE ──
    # Pattern: deviazione che cresce progressivamente (correlata con l'ordine dei punti)
    if len(points) >= 10:
        first_half = points[:len(points)//2]
        second_half = points[len(points)//2:]
        avg_first = sum(abs(p.dev) for p in first_half) / len(first_half)
        avg_second = sum(abs(p.dev) for p in second_half) / len(second_half)
        
        if avg_second > avg_first * 1.3:  # 30% di aumento nella seconda metà
            growth_pct = ((avg_second - avg_first) / avg_first) * 100
            confidence = min(80, 30 + growth_pct)
            candidates.append(RootCauseFingerprint(
                cause="USURA UTENSILE",
                confidence_pct=round(confidence, 0),
                pattern_match=(
                    f"Deviazione crescente: media prima metà {avg_first:.4f}mm, "
                    f"seconda metà {avg_second:.4f}mm (+{growth_pct:.0f}%). "
                    f"Pattern compatibile con usura progressiva del tagliente."
                ),
                suggested_action=(
                    f"Verificare stato utensili nella zona. "
                    f"Ridurre vita utensile massima. "
                    f"Controllare correttore usura nel programma NC."
                ),
            ))
    
    # ── 3. FLESSIONE UTENSILE ──
    # Pattern: NOK concentrati su pareti/zone con alto sbalzo
    nok_points = [p for p in points if p.status == PointStatus.NOK]
    if nok_points and len(nok_points) < len(points) * 0.3:  # NOK localizzati, non diffusi
        # Verifica se i NOK sono spazialmente concentrati
        if len(nok_points) >= 2:
            nok_coords = [(p.xn, p.yn, p.zn) for p in nok_points]
            centroid = tuple(sum(c) / len(nok_coords) for c in zip(*nok_coords))
            spread = sum(
                math.sqrt(sum((a - b)**2 for a, b in zip(p, centroid)))
                for p in nok_coords
            ) / len(nok_coords)
            
            all_coords = [(p.xn, p.yn, p.zn) for p in points]
            all_centroid = tuple(sum(c) / len(all_coords) for c in zip(*all_coords))
            all_spread = sum(
                math.sqrt(sum((a - b)**2 for a, b in zip(p, all_centroid)))
                for p in all_coords
            ) / len(all_coords)
            
            # NOK concentrati in una zona più piccola del pezzo
            if all_spread > 0 and spread < all_spread * 0.6:
                confidence = min(70, 40 + (1 - spread / all_spread) * 60)
                candidates.append(RootCauseFingerprint(
                    cause="FLESSIONE UTENSILE",
                    confidence_pct=round(confidence, 0),
                    pattern_match=(
                        f"Punti NOK concentrati spazialmente (spread {spread:.1f}mm vs {all_spread:.1f}mm globale). "
                        f"Zona localizzata con deviazioni superiori alla media. "
                        f"Pattern compatibile con flessione utensile su zona critica."
                    ),
                    suggested_action=(
                        f"Verificare la zona dei punti NOK: parete sottile? Lungo sbalzo? "
                        f"Considerare utensile più corto/rigido o ridurre ae/ap in quella zona. "
                        f"Valutare strategia di finitura alternativa."
                    ),
                ))
    
    # ── 4. VIBRAZIONE / CHATTER ──
    # Pattern: alta varianza nelle deviazioni, nessuna direzione predominante
    if directional.coherence < 0.3:
        devs = [abs(p.dev) for p in points]
        mean_d = sum(devs) / len(devs)
        std_d = math.sqrt(sum((d - mean_d)**2 for d in devs) / max(len(devs) - 1, 1))
        cv = std_d / mean_d if mean_d > 0 else 0  # coefficiente di variazione
        
        if cv > 0.8:  # alta variabilità
            confidence = min(65, 25 + cv * 30)
            candidates.append(RootCauseFingerprint(
                cause="VIBRAZIONE / CHATTER",
                confidence_pct=round(confidence, 0),
                pattern_match=(
                    f"Alta variabilità delle deviazioni (CV={cv:.2f}). "
                    f"Nessuna direzione predominante (coerenza {directional.coherence*100:.0f}%). "
                    f"Pattern compatibile con vibrazione durante la lavorazione."
                ),
                suggested_action=(
                    f"Verificare parametri di taglio (giri, avanzamento). "
                    f"Controllare rigidità staffaggio. "
                    f"Considerare utensile antivibrante o cambio strategia."
                ),
            ))
    
    # Ordina per confidenza
    candidates.sort(key=lambda x: x.confidence_pct, reverse=True)
    return candidates


# ──────────────────────────────────────────────────────────
# ANALISI COMPLETA DEL REPORT
# ──────────────────────────────────────────────────────────

@dataclass
class FullAnalysis:
    """Risultato dell'analisi completa di un report."""
    report_summary: dict
    section_stats: list[SectionStats]
    directional_analyses: dict[str, DirectionalAnalysis]
    error_decompositions: dict[str, ErrorDecomposition]
    root_causes: dict[str, list[RootCauseFingerprint]]
    
    # Diagnosi globale
    global_diagnosis: str = ""


def analyze_report(report: InspectionReport) -> FullAnalysis:
    """Esegue l'analisi completa su un report di collaudo."""
    
    stats_list = []
    dir_analyses = {}
    decompositions = {}
    root_causes = {}
    
    for section in report.sections:
        if not section.points:
            continue
        
        # Statistiche
        stats = compute_section_stats(section)
        stats_list.append(stats)
        
        # Analisi direzionale
        dir_analysis = analyze_directions(section.points)
        dir_analyses[section.name] = dir_analysis
        
        # Decomposizione errore
        decomp = decompose_error(section)
        decompositions[section.name] = decomp
        
        # Root cause fingerprinting
        causes = fingerprint_root_causes(section, dir_analysis, decomp)
        if causes:
            root_causes[section.name] = causes
    
    # Diagnosi globale
    diagnosis_parts = []
    for section in report.sections:
        if section.name in root_causes and root_causes[section.name]:
            top_cause = root_causes[section.name][0]
            diagnosis_parts.append(
                f"{section.name}: {top_cause.cause} (confidenza {top_cause.confidence_pct:.0f}%)"
            )
    
    global_diag = f"Report {report.metadata.part_code} — "
    global_diag += f"{report.total_points} punti, {report.total_nok} NOK ({100 - report.overall_conformity_pct:.1f}% non conforme). "
    
    if diagnosis_parts:
        global_diag += "Diagnosi per sezione: " + "; ".join(diagnosis_parts) + "."
    else:
        global_diag += "Nessun pattern di root cause dominante identificato."
    
    return FullAnalysis(
        report_summary=report.summary(),
        section_stats=stats_list,
        directional_analyses=dir_analyses,
        error_decompositions=decompositions,
        root_causes=root_causes,
        global_diagnosis=global_diag,
    )
