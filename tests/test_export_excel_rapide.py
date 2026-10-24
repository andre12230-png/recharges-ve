"""L'export Excel ne ralentit plus a mesure que l'historique grandit
(second audit du 16/10/2026, constat A6).

Defaut d'origine : a chaque recharge ecrite, le programme demandait a la
feuille sa derniere ligne (`max_row`), qu'openpyxl recalcule en parcourant
toute la feuille. Le temps grandissait donc comme le carre du nombre de
lignes : 1,25 s pour 1 000 recharges, 42,81 s pour 10 000.

Le test compte ces demandes plutot que de chronometrer (un chronometre
varie d'un ordinateur a l'autre) : leur nombre ne doit plus dependre du
nombre de recharges. Recharges inventees.

    py -m pytest tests/test_export_excel_rapide.py
"""

from __future__ import annotations

import openpyxl
import pytest
from openpyxl.worksheet.worksheet import Worksheet

import export


def _recharges(n: int) -> list[dict]:
    return [{"id": f"r{i}", "date": f"2026-01-{1 + i % 28:02d}T{i % 24:02d}:00",
             "lieu": "maison" if i % 2 else "exterieur", "kwh": 10.0,
             "cout_eur": 2.0, "prix_kwh": 0.2, "tarif_nom": "Inventé",
             "operateur": "Réseau A", "carte": "", "lieu_detail": "",
             "kwh_hc": 6.0, "kwh_hp": 4.0} for i in range(n)]


def _demandes_de_derniere_ligne(monkeypatch, tmp_path, n: int) -> int:
    vraie = Worksheet.max_row
    compte = {"n": 0}

    def comptee(self):
        compte["n"] += 1
        return vraie.fget(self)
    monkeypatch.setattr(Worksheet, "max_row", property(comptee))
    export.exporter_excel(_recharges(n), tmp_path / f"export_{n}.xlsx")
    monkeypatch.setattr(Worksheet, "max_row", vraie)
    return compte["n"]


def test_le_nombre_de_demandes_ne_depend_plus_du_nombre_de_lignes(
        monkeypatch, tmp_path):
    peu = _demandes_de_derniere_ligne(monkeypatch, tmp_path, 10)
    beaucoup = _demandes_de_derniere_ligne(monkeypatch, tmp_path, 300)
    assert beaucoup == peu


@pytest.mark.parametrize("n", [1, 25])
def test_le_classeur_reste_le_meme(tmp_path, n):
    # Les textes restent des textes et chaque ligne a ses formats.
    recharges = _recharges(n)
    recharges[0]["carte"] = "=1+1"
    chemin = tmp_path / "export.xlsx"
    export.exporter_excel(recharges, chemin)
    ws = openpyxl.load_workbook(chemin).worksheets[0]
    assert ws.cell(row=2, column=7).value == "=1+1"
    assert ws.cell(row=2, column=7).data_type == "s"
    assert ws.cell(row=n + 1, column=4).number_format == "0.00"
    assert ws.cell(row=n + 1, column=1).number_format == "DD/MM/YYYY HH:MM"
