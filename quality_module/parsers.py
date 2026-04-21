"""
DMGDesk Quality Intelligence — Parsers
Parsers per dati collaudo CMM. Supporta:
- CSV/TXT export da SurferNT (primario, affidabile)
- Testo strutturato (tabelle estratte manualmente o da OCR pulito)
- PDF (via OCR — fallback, meno affidabile)
"""

import csv
import re
import io
import json
from pathlib import Path
from datetime import date, datetime
from typing import Optional

from models import (
    InspectionPoint, InspectionHole, InspectionSection,
    InspectionMetadata, InspectionReport,
)


# ──────────────────────────────────────────────────────────
# PARSER CSV/TXT — Formato primario, alta affidabilità
# ──────────────────────────────────────────────────────────

class SurferCSVParser:
    """
    Parser per export CSV/TXT da SurferNT.
    Formato atteso: N.Punto;Xm;Xn;Dx;Ym;Yn;Dy;Zm;Zn;Dz;TMin;TMax;Dev;Dir
    Il separatore può essere ; o , o \\t (auto-detect).
    """
    
    EXPECTED_COLUMNS = {
        'n.punto', 'punto', 'point', 'name',
        'xm', 'xn', 'dx',
        'ym', 'yn', 'dy',
        'zm', 'zn', 'dz',
        'tmin', 'tmax',
        'dev', 'dir',
    }
    
    def parse_file(self, filepath: str, section_name: str = "UNKNOWN",
                   tolerance_min: float = -0.020, tolerance_max: float = 0.020,
                   metadata: Optional[InspectionMetadata] = None) -> InspectionReport:
        """Parse un file CSV/TXT e ritorna un InspectionReport."""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        return self.parse_text(content, section_name, tolerance_min, tolerance_max, metadata)
    
    def parse_text(self, content: str, section_name: str = "UNKNOWN",
                   tolerance_min: float = -0.020, tolerance_max: float = 0.020,
                   metadata: Optional[InspectionMetadata] = None) -> InspectionReport:
        """Parse testo CSV e ritorna un InspectionReport."""
        
        # Auto-detect separator
        sep = self._detect_separator(content)
        reader = csv.DictReader(io.StringIO(content), delimiter=sep)
        
        # Normalize column names
        if reader.fieldnames:
            col_map = self._map_columns(reader.fieldnames)
        else:
            raise ValueError("Nessuna intestazione trovata nel CSV")
        
        points = []
        for row in reader:
            try:
                point = self._row_to_point(row, col_map, section_name, tolerance_min, tolerance_max)
                if point:
                    points.append(point)
            except (ValueError, KeyError) as e:
                continue  # Skip malformed rows
        
        section = InspectionSection(
            name=section_name,
            tolerance_min=tolerance_min,
            tolerance_max=tolerance_max,
            points=points,
        )
        
        if metadata is None:
            metadata = InspectionMetadata(
                drawing_number="", part_code="", part_type="",
                description="", client="", operator="",
            )
        
        return InspectionReport(metadata=metadata, sections=[section])
    
    def _detect_separator(self, content: str) -> str:
        first_line = content.split('\n')[0]
        counts = {';': first_line.count(';'), ',': first_line.count(','), '\t': first_line.count('\t')}
        return max(counts, key=counts.get)
    
    def _map_columns(self, fieldnames: list[str]) -> dict[str, str]:
        """Mappa le intestazioni del CSV ai nomi standard."""
        col_map = {}
        for fn in fieldnames:
            fn_lower = fn.strip().lower().replace(' ', '').replace('.', '')
            if fn_lower in ('npunto', 'punto', 'point', 'name', 'npoint'):
                col_map['name'] = fn
            elif fn_lower == 'xm': col_map['xm'] = fn
            elif fn_lower == 'xn': col_map['xn'] = fn
            elif fn_lower == 'dx': col_map['dx'] = fn
            elif fn_lower == 'ym': col_map['ym'] = fn
            elif fn_lower == 'yn': col_map['yn'] = fn
            elif fn_lower == 'dy': col_map['dy'] = fn
            elif fn_lower == 'zm': col_map['zm'] = fn
            elif fn_lower == 'zn': col_map['zn'] = fn
            elif fn_lower == 'dz': col_map['dz'] = fn
            elif fn_lower == 'tmin': col_map['tmin'] = fn
            elif fn_lower == 'tmax': col_map['tmax'] = fn
            elif fn_lower == 'dev': col_map['dev'] = fn
            elif fn_lower == 'dir': col_map['dir'] = fn
        return col_map
    
    def _row_to_point(self, row: dict, col_map: dict, section: str,
                      tmin: float, tmax: float) -> Optional[InspectionPoint]:
        """Converte una riga CSV in un InspectionPoint."""
        name = row.get(col_map.get('name', ''), '').strip()
        if not name:
            return None
        
        def fval(key: str, default: float = 0.0) -> float:
            raw = row.get(col_map.get(key, ''), '').strip().replace(',', '.')
            if not raw:
                return default
            return float(raw)
        
        return InspectionPoint(
            name=name,
            section=section,
            xm=fval('xm'), xn=fval('xn'), dx=fval('dx'),
            ym=fval('ym'), yn=fval('yn'), dy=fval('dy'),
            zm=fval('zm'), zn=fval('zn'), dz=fval('dz'),
            tmin=fval('tmin', tmin), tmax=fval('tmax', tmax),
            dev=fval('dev'), direction=row.get(col_map.get('dir', ''), '').strip(),
        )


# ──────────────────────────────────────────────────────────
# PARSER TABELLARE — Per dati estratti da testo strutturato
# ──────────────────────────────────────────────────────────

class SurferTableParser:
    """
    Parser per tabelle SurferNT in formato testo strutturato.
    Accetta il formato delle tabelle come visibili nel PDF:
    
    N. Punto    Xm       Xn      Dx     Ym       Yn      Dy     Zm       Zn      Dz    TMin   TMax   Dev   Dir
    P1       191.729  191.729  0.000  -54.043  -54.043  0.000  -17.227  -17.303  0.076  -0.020  0.020  0.076  +z
    """
    
    # Regex per una riga di dati punto
    # Matches: optional *, point name (P1, CP35, etc.), then 13 numbers, then direction
    POINT_RE = re.compile(
        r'^\*?\s*'                          # optional * marker
        r'((?:P|CP)\s*\d+)\s+'             # point name (P1, CP 35, etc.)
        r'(-?\d+\.\d+)\s+'                 # Xm
        r'(-?\d+\.\d+)\s+'                 # Xn
        r'(-?\d+\.\d+)\s+'                 # Dx
        r'(-?\d+\.\d+)\s+'                 # Ym
        r'(-?\d+\.\d+)\s+'                 # Yn
        r'(-?\d+\.\d+)\s+'                 # Dy
        r'(-?\d+\.\d+)\s+'                 # Zm
        r'(-?\d+\.\d+)\s+'                 # Zn
        r'(-?\d+\.\d+)\s+'                 # Dz
        r'(-?\d+\.\d+)\s+'                 # TMin
        r'(-?\d+\.\d+)\s+'                 # TMax
        r'(-?\d+\.\d+)\s+'                 # Dev
        r'([+-][xyz])'                      # Dir
    )
    
    # Regex per la sezione title (dal footer delle pagine)
    SECTION_RE = re.compile(
        r'BOTTOM\s+SLIDER\s*-\s*(\w+)',
        re.IGNORECASE
    )
    
    # Regex per metadati footer
    DRAWING_RE = re.compile(r'Disegno\s*N\.?\s*:?\s*(\S+)', re.IGNORECASE)
    PARTCODE_RE = re.compile(r'Cod\.?\s*Part\.?\s*:?\s*(\S+)', re.IGNORECASE)
    CLIENT_RE = re.compile(r'Cliente\s*:?\s*(.+?)(?:\s+Tolleranz|$)', re.IGNORECASE)
    OPERATOR_RE = re.compile(r'Operatore\s*:?\s*(.+?)(?:\s+Firma|$)', re.IGNORECASE)
    DATE_RE = re.compile(r'D[at]*\s*:?\s*(\d{2,4}[-/.]\d{2}[-/.]\d{2,4})', re.IGNORECASE)
    TOLERANCE_RE = re.compile(r'Tolleranz[ae]?\s*:?\s*(-?\d+[.,]\d+)\s+(\d+[.,]\d+)', re.IGNORECASE)
    TYPE_RE = re.compile(r'Tipo\s*:?\s*(.+?)(?:\s+Cliente|$)', re.IGNORECASE)
    
    def parse_text(self, text: str) -> InspectionReport:
        """
        Parse testo contenente tabelle SurferNT multi-sezione.
        Il testo può contenere più pagine/sezioni.
        """
        lines = text.strip().split('\n')
        
        metadata = self._extract_metadata(text)
        sections: dict[str, InspectionSection] = {}
        current_section = "UNKNOWN"
        current_tmin = -0.020
        current_tmax = 0.020
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for section header
            section_match = self.SECTION_RE.search(line)
            if section_match:
                current_section = section_match.group(1).upper()
                continue
            
            # Check for tolerance
            tol_match = self.TOLERANCE_RE.search(line)
            if tol_match:
                current_tmin = -abs(float(tol_match.group(1).replace(',', '.')))
                current_tmax = abs(float(tol_match.group(2).replace(',', '.')))
                continue
            
            # Try to parse as data point
            point_match = self.POINT_RE.match(line)
            if point_match:
                g = point_match.groups()
                point_name = g[0].replace(' ', '')
                
                # Ensure section exists
                if current_section not in sections:
                    sections[current_section] = InspectionSection(
                        name=current_section,
                        tolerance_min=current_tmin,
                        tolerance_max=current_tmax,
                    )
                
                point = InspectionPoint(
                    name=point_name,
                    section=current_section,
                    xm=float(g[1]), xn=float(g[2]), dx=float(g[3]),
                    ym=float(g[4]), yn=float(g[5]), dy=float(g[6]),
                    zm=float(g[7]), zn=float(g[8]), dz=float(g[9]),
                    tmin=float(g[10]), tmax=float(g[11]),
                    dev=float(g[12]), direction=g[13],
                )
                sections[current_section].points.append(point)
        
        return InspectionReport(
            metadata=metadata,
            sections=list(sections.values()),
        )
    
    def _extract_metadata(self, text: str) -> InspectionMetadata:
        """Estrae metadati dal testo del report."""
        drawing = ""
        m = self.DRAWING_RE.search(text)
        if m:
            drawing = m.group(1).strip()
        
        part_code = ""
        m = self.PARTCODE_RE.search(text)
        if m:
            part_code = m.group(1).strip()
        
        client = ""
        m = self.CLIENT_RE.search(text)
        if m:
            client = m.group(1).strip()
        
        operator = ""
        m = self.OPERATOR_RE.search(text)
        if m:
            operator = m.group(1).strip()
        
        inspection_date = None
        m = self.DATE_RE.search(text)
        if m:
            try:
                raw = m.group(1).replace('/', '-').replace('.', '-')
                parts = raw.split('-')
                if len(parts[0]) == 2:
                    # YY-MM-DD
                    inspection_date = date(2000 + int(parts[0]), int(parts[1]), int(parts[2]))
                else:
                    inspection_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                pass
        
        part_type = ""
        m = self.TYPE_RE.search(text)
        if m:
            part_type = m.group(1).strip()
        
        return InspectionMetadata(
            drawing_number=drawing,
            part_code=part_code,
            part_type=part_type,
            description="",
            client=client,
            operator=operator,
            inspection_date=inspection_date,
        )


# ──────────────────────────────────────────────────────────
# PARSER JSON — Per import da dati pre-estratti
# ──────────────────────────────────────────────────────────

class JSONParser:
    """
    Parser per dati in formato JSON strutturato.
    Utile per import da altri sistemi o da dati pre-estratti.
    
    Formato atteso:
    {
        "metadata": { "drawing_number": "...", "part_code": "...", ... },
        "sections": [
            {
                "name": "CHIUSURA",
                "tolerance_min": -0.020,
                "tolerance_max": 0.020,
                "points": [
                    { "name": "P1", "xm": 191.729, "xn": 191.729, ... }
                ]
            }
        ]
    }
    """
    
    def parse_file(self, filepath: str) -> InspectionReport:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return self.parse_dict(data)
    
    def parse_dict(self, data: dict) -> InspectionReport:
        meta_d = data.get('metadata', {})
        metadata = InspectionMetadata(
            drawing_number=meta_d.get('drawing_number', ''),
            part_code=meta_d.get('part_code', ''),
            part_type=meta_d.get('part_type', ''),
            description=meta_d.get('description', ''),
            client=meta_d.get('client', ''),
            operator=meta_d.get('operator', ''),
            inspection_date=date.fromisoformat(meta_d['inspection_date']) if meta_d.get('inspection_date') else None,
        )
        
        sections = []
        for sec_d in data.get('sections', []):
            points = []
            for pt_d in sec_d.get('points', []):
                points.append(InspectionPoint(
                    name=pt_d['name'],
                    section=sec_d['name'],
                    xm=pt_d['xm'], xn=pt_d['xn'], dx=pt_d['dx'],
                    ym=pt_d['ym'], yn=pt_d['yn'], dy=pt_d['dy'],
                    zm=pt_d['zm'], zn=pt_d['zn'], dz=pt_d['dz'],
                    tmin=pt_d.get('tmin', sec_d.get('tolerance_min', -0.020)),
                    tmax=pt_d.get('tmax', sec_d.get('tolerance_max', 0.020)),
                    dev=pt_d['dev'], direction=pt_d['dir'],
                ))
            
            holes = []
            for h_d in sec_d.get('holes', []):
                holes.append(InspectionHole(
                    name=h_d.get('name', ''),
                    hole_code=h_d.get('hole_code', ''),
                    hole_number=h_d.get('hole_number', 0),
                    xm=h_d['xm'], xn=h_d['xn'], dx=h_d['dx'],
                    ym=h_d['ym'], yn=h_d['yn'], dy=h_d['dy'],
                    zm=h_d['zm'], zn=h_d['zn'], dz=h_d['dz'],
                    diameter_measured=h_d.get('diameter_measured', 0),
                    diameter_nominal=h_d.get('diameter_nominal', 0),
                    diameter_dev=h_d.get('diameter_dev', 0),
                    tp_measured=h_d.get('tp_measured', 0),
                    tp_tolerance=h_d.get('tp_tolerance', 0),
                    form=h_d.get('form', 0),
                ))
            
            sections.append(InspectionSection(
                name=sec_d['name'],
                tolerance_min=sec_d.get('tolerance_min', -0.020),
                tolerance_max=sec_d.get('tolerance_max', 0.020),
                points=points,
                holes=holes,
            ))
        
        return InspectionReport(metadata=metadata, sections=sections)


# ──────────────────────────────────────────────────────────
# AUTO-DETECT e dispatch
# ──────────────────────────────────────────────────────────

def parse_inspection_file(filepath: str, **kwargs) -> InspectionReport:
    """
    Auto-detect del formato e parsing.
    Supporta: .csv, .txt, .json, .tsv
    Per .pdf: richiede estrazione preventiva (OCR o export).
    """
    path = Path(filepath)
    ext = path.suffix.lower()
    
    if ext == '.json':
        return JSONParser().parse_file(filepath)
    elif ext in ('.csv', '.txt', '.tsv'):
        return SurferCSVParser().parse_file(filepath, **kwargs)
    elif ext == '.pdf':
        raise NotImplementedError(
            "Il PDF SurferNT è basato su immagini. "
            "Esportare in CSV/TXT da SurferNT per parsing affidabile, "
            "oppure usare JSONParser con dati pre-estratti."
        )
    else:
        # Try CSV parser as fallback
        return SurferCSVParser().parse_file(filepath, **kwargs)
