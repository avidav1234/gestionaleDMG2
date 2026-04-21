"""
DMGDesk Quality Intelligence — Data Models
Modelli per report di collaudo CMM (SurferNT e compatibili).
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import date


class PointStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"  # >80% tolleranza
    NOK = "NOK"


class ErrorType(str, Enum):
    SYSTEMATIC = "SYSTEMATIC"
    RANDOM = "RANDOM"
    MIXED = "MIXED"


@dataclass
class InspectionPoint:
    """Singolo punto di misura CMM."""
    name: str           # Es: "P1", "CP35"
    section: str        # Es: "CHIUSURA", "NERVATURE"
    
    # Coordinate misurate
    xm: float
    ym: float
    zm: float
    
    # Coordinate nominali (= coordinate CAD)
    xn: float
    yn: float
    zn: float
    
    # Deviazioni per asse
    dx: float
    dy: float
    dz: float
    
    # Tolleranza
    tmin: float
    tmax: float
    
    # Deviazione risultante e direzione
    dev: float
    direction: str      # "+x", "-x", "+y", "-y", "+z", "-z"
    
    @property
    def status(self) -> PointStatus:
        """Stato del punto rispetto alla tolleranza."""
        abs_dev = abs(self.dev)
        if abs_dev > self.tmax:
            return PointStatus.NOK
        elif abs_dev > self.tmax * 0.8:
            return PointStatus.WARNING
        return PointStatus.OK
    
    @property
    def tolerance_usage_pct(self) -> float:
        """Quanto della tolleranza è utilizzato (0-100+)."""
        if self.tmax == 0:
            return 0.0
        return (abs(self.dev) / self.tmax) * 100.0
    
    @property
    def deviation_vector(self) -> tuple[float, float, float]:
        """Vettore di deviazione 3D."""
        return (self.dx, self.dy, self.dz)


@dataclass
class InspectionHole:
    """Foro misurato (sezione FORATURA)."""
    name: str           # Es: "1 - K0806 1 - Min.Quad."
    hole_code: str      # Es: "K0806"
    hole_number: int    # Es: 1
    
    # Posizione misurata e nominale
    xm: float
    xn: float
    dx: float
    
    ym: float
    yn: float
    dy: float
    
    zm: float
    zn: float
    dz: float
    
    # Diametro
    diameter_measured: float
    diameter_nominal: float
    diameter_dev: float
    
    # Tolleranza posizione e diametro
    tp_measured: float
    tp_tolerance: float
    
    # Forma (circolarità)
    form: float
    form_tolerance: Optional[float] = None


@dataclass
class InspectionSection:
    """Sezione del report (CHIUSURA, PIEDE, TASCA, FORATURA, NERVATURE)."""
    name: str
    tolerance_min: float
    tolerance_max: float
    points: list[InspectionPoint] = field(default_factory=list)
    holes: list[InspectionHole] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    
    @property
    def total_points(self) -> int:
        return len(self.points)
    
    @property
    def ok_count(self) -> int:
        return sum(1 for p in self.points if p.status == PointStatus.OK)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for p in self.points if p.status == PointStatus.WARNING)
    
    @property
    def nok_count(self) -> int:
        return sum(1 for p in self.points if p.status == PointStatus.NOK)
    
    @property
    def conformity_pct(self) -> float:
        if self.total_points == 0:
            return 100.0
        return (self.ok_count / self.total_points) * 100.0
    
    @property
    def worst_point(self) -> Optional[InspectionPoint]:
        if not self.points:
            return None
        return max(self.points, key=lambda p: abs(p.dev))
    
    @property
    def mean_deviation(self) -> float:
        if not self.points:
            return 0.0
        return sum(abs(p.dev) for p in self.points) / len(self.points)
    
    @property
    def max_deviation(self) -> float:
        if not self.points:
            return 0.0
        return max(abs(p.dev) for p in self.points)


@dataclass
class InspectionMetadata:
    """Metadati dal footer del report."""
    drawing_number: str         # "ID24103D.20201A1"
    part_code: str              # "c.4296"
    part_type: str              # "PSA DCT MHEV #19"
    description: str            # "TRANSMISSION HOUSING"
    client: str                 # "TEKSID ALUMINUM S.R.L."
    operator: str               # "V. Parmiggiani"
    inspection_date: Optional[date] = None  # 2019-12-25
    total_pages: int = 0
    software: str = "SurferNT"


@dataclass
class InspectionReport:
    """Report completo di collaudo CMM."""
    metadata: InspectionMetadata
    sections: list[InspectionSection] = field(default_factory=list)
    source_file: str = ""
    
    # Link a DMGDesk
    commessa_id: Optional[str] = None
    posizione_id: Optional[str] = None
    
    @property
    def all_points(self) -> list[InspectionPoint]:
        """Tutti i punti di tutte le sezioni."""
        points = []
        for section in self.sections:
            points.extend(section.points)
        return points
    
    @property
    def all_holes(self) -> list[InspectionHole]:
        """Tutti i fori."""
        holes = []
        for section in self.sections:
            holes.extend(section.holes)
        return holes
    
    @property
    def total_points(self) -> int:
        return sum(s.total_points for s in self.sections)
    
    @property
    def total_ok(self) -> int:
        return sum(s.ok_count for s in self.sections)
    
    @property
    def total_nok(self) -> int:
        return sum(s.nok_count for s in self.sections)
    
    @property
    def total_warning(self) -> int:
        return sum(s.warning_count for s in self.sections)
    
    @property
    def overall_conformity_pct(self) -> float:
        total = self.total_points
        if total == 0:
            return 100.0
        return (self.total_ok / total) * 100.0
    
    def get_section(self, name: str) -> Optional[InspectionSection]:
        for s in self.sections:
            if s.name.upper() == name.upper():
                return s
        return None
    
    def summary(self) -> dict:
        """Riepilogo completo del report."""
        return {
            "metadata": {
                "drawing": self.metadata.drawing_number,
                "part_code": self.metadata.part_code,
                "client": self.metadata.client,
                "date": str(self.metadata.inspection_date) if self.metadata.inspection_date else None,
                "operator": self.metadata.operator,
            },
            "totals": {
                "points": self.total_points,
                "ok": self.total_ok,
                "warning": self.total_warning,
                "nok": self.total_nok,
                "conformity_pct": round(self.overall_conformity_pct, 1),
            },
            "sections": [
                {
                    "name": s.name,
                    "points": s.total_points,
                    "ok": s.ok_count,
                    "warning": s.warning_count,
                    "nok": s.nok_count,
                    "conformity_pct": round(s.conformity_pct, 1),
                    "mean_dev": round(s.mean_deviation, 4),
                    "max_dev": round(s.max_deviation, 4),
                    "worst_point": s.worst_point.name if s.worst_point else None,
                    "tolerance": f"±{s.tolerance_max}",
                }
                for s in self.sections
            ],
            "holes": len(self.all_holes),
        }
