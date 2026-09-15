"""Surface runoff calculation per terrain cell.

Runoff = Rainfall x Area x RunoffCoefficient
Accounts for infiltration approximation, depression storage and existing surface water.
"""
from dataclasses import dataclass
from typing import List

from ...config import settings


@dataclass
class RunoffResult:
    cell_id: str
    lat: float
    lon: float
    rainfall_mm_hr: float
    area_m2: float
    runoff_coefficient: float
    infiltration_mm: float
    depression_storage_mm: float
    runoff_volume_m3_hr: float
    runoff_depth_mm: float


class RunoffEngine:
    def __init__(self, coefficients=None):
        self.coefficients = coefficients or settings.runoff_coefficients

    def coefficient_for(self, land_cover: str) -> float:
        return self.coefficients.get(land_cover, 0.5)

    def compute(self, cell: dict, rainfall_mm_hr: float, area_m2: float) -> RunoffResult:
        coeff = self.coefficient_for(cell.get("land_cover", "mixed"))
        imperv = cell.get("imperviousness", 0.5)
        effective_coeff = coeff * (0.6 + 0.4 * imperv)
        # infiltration approximation: 3 mm/hr for permeable, 0.3 mm/hr for impervious
        infiltration_mm = (3.0 * (1 - imperv)) + (0.3 * imperv)
        # depression storage: 5 mm permeable, 1.5 mm impervious
        depression_mm = (5.0 * (1 - imperv)) + (1.5 * imperv)
        effective_rain = max(0.0, rainfall_mm_hr - infiltration_mm - depression_mm)
        runoff_depth_mm = effective_rain * effective_coeff
        runoff_volume_m3_hr = (runoff_depth_mm / 1000.0) * area_m2
        return RunoffResult(
            cell_id=cell.get("cell_id"),
            lat=cell.get("lat"),
            lon=cell.get("lon"),
            rainfall_mm_hr=rainfall_mm_hr,
            area_m2=area_m2,
            runoff_coefficient=round(effective_coeff, 3),
            infiltration_mm=round(infiltration_mm, 2),
            depression_storage_mm=round(depression_mm, 2),
            runoff_volume_m3_hr=round(runoff_volume_m3_hr, 3),
            runoff_depth_mm=round(runoff_depth_mm, 2),
        )

    def compute_all(self, terrain_cells: List[dict], rainfall_field: dict, area_m2: float) -> List[RunoffResult]:
        """rainfall_field: dict cell_id -> rainfall_mm_hr for a given timestep."""
        out = []
        for cell in terrain_cells:
            rain = rainfall_field.get(cell["cell_id"], 0.0)
            out.append(self.compute(cell, rain, area_m2))
        return out