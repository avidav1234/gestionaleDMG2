# DMGDesk Quality Intelligence Module

Modulo per l'integrazione dei report di collaudo CMM in DMGDesk.

## Struttura

- **models.py** — Modelli dati: InspectionPoint, InspectionHole, InspectionSection, InspectionReport
- **parsers.py** — Parser per CSV, testo tabellare, JSON (auto-detect formato)
- **analysis.py** — Motore di analisi: statistiche, analisi direzionale vettoriale, decomposizione errore sistematico, fingerprinting root cause
- **test_pipeline.py** — Test con dati reali dal report c.4296 (SurferNT)

## Analisi disponibili

1. **Statistiche per sezione** — Cp/Cpk, deviazione media/max, conformità %
2. **Analisi direzionale** — Coerenza vettoriale, direzione predominante, classificazione errore (sistematico/casuale/misto)
3. **Decomposizione errore** — Separazione traslazione (setup) da residuo (processo)
4. **Root cause fingerprinting** — Riconoscimento pattern: errore riferimento, usura utensile, flessione, vibrazione

## Formati supportati

- CSV/TXT export da SurferNT (primario)
- JSON strutturato
- Testo tabellare (regex-based)

## Fase del progetto

Fase 1 della roadmap Quality Intelligence. Vedi i documenti di visione per il piano completo (5 fasi).
