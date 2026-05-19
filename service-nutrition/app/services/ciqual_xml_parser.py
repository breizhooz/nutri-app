from __future__ import annotations

import os
import re
from dataclasses import dataclass
from xml.etree.ElementTree import iterparse


@dataclass
class AlimRecord:
    alim_code: int
    nom_fr: str
    nom_eng: str
    nom_sci: str | None
    alim_grp_code: str | None
    alim_ssgrp_code: str | None
    alim_ssssgrp_code: str | None


class CiqualXmlParser:
    _MACRO_CONST_CODES: dict[int, str] = {
        328:   "calories",
        25000: "proteines",
        31000: "glucides",
        40000: "lipides",
        34100: "fibres",
    }

    @classmethod
    def parse_aliments(cls, extract_dir: str) -> dict[int, AlimRecord]:
        path = cls._find_xml(extract_dir, "alim_")
        records: dict[int, AlimRecord] = {}
        for _, el in iterparse(path, events=("end",)):
            if el.tag != "ALIM":
                continue
            code_str = cls._text(el, "alim_code")
            if not code_str:
                el.clear()
                continue
            records[int(code_str)] = AlimRecord(
                alim_code=int(code_str),
                nom_fr=cls._text(el, "alim_nom_fr") or "",
                nom_eng=cls._text(el, "alim_nom_eng") or "",
                nom_sci=cls._text(el, "alim_nom_sci"),
                alim_grp_code=cls._text(el, "alim_grp_code"),
                alim_ssgrp_code=cls._text(el, "alim_ssgrp_code"),
                alim_ssssgrp_code=cls._text(el, "alim_ssssgrp_code"),
            )
            el.clear()
        return records

    @classmethod
    def parse_compo(cls, extract_dir: str) -> dict[int, dict[str, float | None]]:
        path = cls._find_xml(extract_dir, "compo_")
        macros: dict[int, dict] = {}
        confidence: dict[int, str | None] = {}

        for _, el in iterparse(path, events=("end",)):
            if el.tag != "COMPO":
                el.clear()
                continue
            alim_str = cls._text(el, "alim_code")
            const_str = cls._text(el, "const_code")
            if not alim_str or not const_str:
                el.clear()
                continue
            const_code = int(const_str)
            if const_code not in cls._MACRO_CONST_CODES:
                el.clear()
                continue
            alim_code = int(alim_str)
            field_name = cls._MACRO_CONST_CODES[const_code]
            value = cls._to_float(cls._text(el, "teneur"))
            macros.setdefault(alim_code, {})[field_name] = value
            if const_code == 328:
                confidence[alim_code] = cls._text(el, "code_confiance")
            el.clear()

        for alim_code, fields in macros.items():
            fields["code_confiance"] = confidence.get(alim_code)
        return macros

    @staticmethod
    def _find_xml(extract_dir: str, prefix: str) -> str:
        pattern = re.compile(rf'^{re.escape(prefix)}\d{{4}}_\d{{2}}_\d{{2}}\.xml$')
        for name in os.listdir(extract_dir):
            if pattern.match(name):
                return os.path.join(extract_dir, name)
        raise FileNotFoundError(f"Aucun fichier XML avec préfixe '{prefix}' dans {extract_dir}")

    @staticmethod
    def _text(el, tag) -> str | None:
        child = el.find(tag)
        if child is None:
            return None
        return (child.text or "").strip() or None

    @staticmethod
    def _to_float(val: str | None) -> float | None:
        if not val or val in ("-", "traces", ""):
            return None
        try:
            return float(val.lstrip("<").replace(",", "."))
        except ValueError:
            return None