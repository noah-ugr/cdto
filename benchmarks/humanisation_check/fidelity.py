"""
Fidelity check of humanised requests, without touching any prompt.

For every instruction of a sample, the request must mention:
- the activity and the task of the path, as a code (A003, A-3), as
  "actividad 3" / "actividad tres" or as an ordinal ("tercera actividad").
  When the number only appears apart from the entity word ("actividades 3 y
  5") the mention counts as loose, which passes;
- the parameter, by one of the synonyms the humaniser prompt prescribes (or
  a close variant, or the literal key);
- the value: numbers as digits (thousands separators allowed) or Spanish
  words; booleans by an activate/deactivate cue; team names by their letter;
  dependency targets like activity/task IDs. Values 1 and booleans are weak
  checks (articles and negations are everywhere) and never fail on their own.

The operation verb is recorded but does not fail a request. A request with
any missing activity, task, parameter or value is flagged; nothing is
dropped. The original requests get the same check as a reference.

Two warnings, reported in the table and the review file but never flagging
or dropping anything:
- possible inverted precedence: for ``X.Order_Before = Y`` (X ends before Y
  starts), a clause that reads "Y ... antes ... X" or "X ... depende de /
  despues de ... Y" (clauses about another activity are skipped);
- unit added: a unit attached to the instruction's number, which carries
  none (minutes, days, currency, %...). Hours on a time field are not
  reported, since they are the schema's unit for times.

Writes ``fidelity_<model>.csv`` and ``review_pairs_<model>.md`` (random
original/new pairs for manual review, also printed).

    python -m benchmarks.humanisation_check.fidelity --run-dir <run-dir>
"""

from __future__ import annotations

import argparse
import random
import re
import unicodedata
from collections import Counter
from typing import Dict, Iterable, List, Optional

import pandas as pd

from benchmarks.humanisation_check.common import find_requests_file, read_jsonl, resolve_run_dir


# ---------------------------------------------------------------- normalisation

def normalize(text: Optional[str]) -> str:
    """Lower case without accents (º -> o, ñ -> n)."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


_UNITS = [
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho",
    "diecinueve", "veinte", "veintiuno", "veintidos", "veintitres", "veinticuatro", "veinticinco",
    "veintiseis", "veintisiete", "veintiocho", "veintinueve",
]
_TENS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_HUNDREDS = {
    1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
    6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos",
}
_ORDINALS = {
    1: ["primero", "primera", "primer"], 2: ["segundo", "segunda"], 3: ["tercero", "tercera", "tercer"],
    4: ["cuarto", "cuarta"], 5: ["quinto", "quinta"], 6: ["sexto", "sexta"],
    7: ["septimo", "septima", "setimo", "setima"], 8: ["octavo", "octava"], 9: ["noveno", "novena"],
}


def cardinal_words(n: int) -> set:
    """Spanish words for 0..999, with un/una and feminine hundreds."""
    if not 0 <= n <= 999:
        return set()
    if n < 30:
        base = {_UNITS[n]}
    elif n < 100:
        tens, unit = divmod(n, 10)
        base = {_TENS[tens]} if unit == 0 else {f"{_TENS[tens]} y {_UNITS[unit]}"}
    elif n == 100:
        base = {"cien"}
    else:
        hundreds, rest = divmod(n, 100)
        head = _HUNDREDS[hundreds]
        base = {head} if rest == 0 else {f"{head} {w}" for w in cardinal_words(rest)}
    words = set()
    for w in base:
        words.add(w)
        if w.endswith("uno"):
            words |= {w[:-3] + "un", w[:-3] + "una"}
        if "ientos" in w:
            words.add(w.replace("ientos", "ientas"))
    return words


def ordinal_words(n: int) -> set:
    """Spanish ordinals 1..30 in both genders (primer, decimotercera, vigesimo primero...)."""
    if n in _ORDINALS:
        return set(_ORDINALS[n])
    if n == 10:
        return {"decimo", "decima"}
    if n == 11:
        return {"undecimo", "undecima"} | {f"decimo{s}" for s in _ORDINALS[1]} | {f"decimo {s}" for s in _ORDINALS[1]}
    if n == 12:
        return {"duodecimo", "duodecima"} | {f"decimo{s}" for s in _ORDINALS[2]} | {f"decimo {s}" for s in _ORDINALS[2]}
    if 13 <= n <= 19:
        return {f"decimo{s}" for s in _ORDINALS[n - 10]} | {f"decimo {s}" for s in _ORDINALS[n - 10]}
    if n == 20:
        return {"vigesimo", "vigesima"}
    if 21 <= n <= 29:
        tail = ordinal_words(n - 20)
        return {f"vigesimo {s}" for s in tail} | {f"vigesima {s}" for s in tail} | {f"vigesimo{s}" for s in tail}
    if n == 30:
        return {"trigesimo", "trigesima"}
    return set()


def _alternation(words: Iterable[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


def int_pattern(value: int) -> str:
    """Digits of ``value``, allowing a thousands separator (17520, 17.520, 17 520)."""
    digits = str(abs(value))
    groups = []
    while digits:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    return r"(?<![0-9])" + r"[.,\s]?".join(groups) + r"(?![0-9])"


# ---------------------------------------------------------------- mentions

_ENTITY = {"activity": r"actividad(?:es)?", "task": r"(?:tareas?|pasos?|tasks?)"}
_CODE_PREFIX = {"activity": "a", "task": "t"}


def id_mention(text: str, kind: str, number: int) -> str:
    """'strict', 'loose' or 'missing' mention of activity/task ``number`` in normalised text."""
    prefix, entity = _CODE_PREFIX[kind], _ENTITY[kind]
    num = rf"0*{number}(?![0-9])"
    words = _alternation(cardinal_words(number))
    ords = _alternation(ordinal_words(number))

    strict = [
        rf"(?<![a-z0-9]){prefix}-?{num}",
        rf"\b{entity}\s+(?:(?:numero|n\.?o|no\.|#)\s*)?(?:{prefix}-?)?{num}",
    ]
    if words:
        strict.append(rf"\b{entity}\s+(?:numero\s+)?(?:{words})\b")
    if ords:
        strict += [rf"\b(?:{ords})\s+{entity}\b", rf"\b{entity}\s+(?:{ords})\b"]
    if any(re.search(p, text) for p in strict):
        return "strict"

    has_entity = re.search(rf"\b{entity}\b", text) or re.search(rf"(?<![a-z0-9]){prefix}-?[0-9]", text)
    number_forms = [rf"(?<![0-9.,]){num}"]
    if words:
        number_forms.append(rf"\b(?:{words})\b")
    if ords:
        number_forms.append(rf"\b(?:{ords})\b")
    if has_entity and any(re.search(p, text) for p in number_forms):
        return "loose"
    return "missing"


_ORDER_TERMS = [
    "preced", "antes", "bloque", "depend", "orden", "anterior", "requisito", "despues", "luego",
    "secuencia", "sigue", "tras", "primero", "previ",
]
# Synonyms prescribed by the humaniser prompt, plus close variants (regex fragments, normalised text).
FIELD_TERMS: Dict[str, List[str]] = {
    "Teams": ["equipo", "cuadrilla", "teams"],
    "Simulation_period": ["horizonte", "ventana", "periodo global", "simula", "periodo total"],
    "runId": ["run", "ejecucion", "identificador", "corrida", r"id\b", "codigo"],
    "T_period": ["frecuencia", "periodo", "ciclo", "intervalo", "periodicidad", "cada"],
    "T_wait": ["espera", "demora", "margen", "esperar"],
    "Start_disp": ["desplazamiento", "retraso", "inicio", "diferid", "arranque", "desfase", "comienz", "empie", "empez"],
    "Team": ["equipo", "cuadrilla", "team"],
    "Team members": ["dotacion", "personal", "operari", "tamano", "miembro", "integrante", "persona", "trabajador", "gente", "tecnico"],
    "Shift_duration": ["turno", "jornada"],
    "Activity_Order_Enforced": ["orden", "secuencia", "ruta", "estricta", "obligatori"],
    "Activity_Order_Before": _ORDER_TERMS,
    "Duration": ["duracion", "dura", "tiempo", "hora"],
    "Requires_Shutdown": ["parada", "apag", "paro", "deten", "shutdown", "parar", "detencion"],
    "Cost_per_hour": ["cost", "tarifa", "precio", "euro", "dolar", r"\$", "€"],
    "Order_Enforced": ["orden", "secuencia", "obligatori", "estricta"],
    "Order_Before": _ORDER_TERMS,
}
_TRUE_CUES = ["activ", "habilit", "requier", "requiera", "necesit", "implic", "obligatori", "forz", "exig", r"si\b", "true", "enciend", "marca"]
_FALSE_CUES = [r"\bno\b", "desactiv", "deshabilit", r"\bsin\b", "false", "quit", "elimin", "libre", "opcional", "ya no", "apaga el"]
OPERATION_TERMS = {
    "SET": ["cambi", "ajust", "dej", "actualiz", "pon", "asign", "activ", "desactiv", "fij", "establec", "sub", "baj", "modific", "configur", "marca", "haz", "pas"],
    "DELETE": ["borr", "elimin", "quit", "suprim", "sac", "retir", "descart"],
    "APPEND": ["anad", "agreg", "inclu", "sum", "depend", "nueva", "tambien", "haz que", "restriccion", "regla", "antes"],
    "REMOVE_ITEM": ["quit", "elimin", "borr", "romp", "suprim", "sac", "retir", "ya no", "deshaz"],
}
LITERAL_KEYS = [k for k in FIELD_TERMS if "_" in k or k == "runId"]

# Warnings: reported, never flag or drop a request.
# "X precede Y" cues put the predecessor first; "Y depends on X" cues put it last.
_FORWARD_CUES = ["antes", "preced", "requisito para", "bloque", "previ"]
_BACKWARD_CUES = ["despues", r"tras\b", "depend", "sigue a", "luego de", r"esper[ae] a", "hasta que", "a continuacion de"]
TIME_FIELDS = {"T_period", "T_wait", "Start_disp", "Shift_duration", "Duration", "Simulation_period"}
UNITS = {
    "hours": r"horas?|hrs?|h",
    "minutes": r"minutos?|mins?",
    "seconds": r"segundos?|segs?",
    "days": r"dias?",
    "weeks": r"semanas?",
    "months": r"mes(?:es)?",
    "years": r"anos?",
    "currency": r"euros?|€|dolares?|usd|\$",
    "percent": r"%|por\s+ciento",
}


def _any_term(text: str, terms: Iterable[str]) -> bool:
    return any(re.search(r"(?<![a-z])" + t, text) for t in terms)


def _mention_positions(text: str, kind: str, number: int) -> List[int]:
    """Start of every mention of activity/task ``number`` (code, entity + number/word/ordinal, 'la 5')."""
    prefix, entity = _CODE_PREFIX[kind], _ENTITY[kind]
    num = rf"0*{number}(?![0-9])"
    words = _alternation(cardinal_words(number))
    ords = _alternation(ordinal_words(number))
    patterns = [
        rf"(?<![a-z0-9]){prefix}-?{num}",
        rf"\b{entity}\s+(?:(?:numero|n\.?o|no\.|#)\s*)?(?:{prefix}-?)?{num}",
        rf"\b(?:la|el|los|las|del|al)\s+(?:numero\s+)?{num}",
    ]
    if words:
        patterns.append(rf"\b{entity}\s+(?:numero\s+)?(?:{words})\b")
    if ords:
        patterns += [rf"\b(?:{ords})\s+{entity}\b", rf"\b{entity}\s+(?:{ords})\b", rf"\b(?:la|el)\s+(?:{ords})\b"]
    return sorted({m.start() for p in patterns for m in re.finditer(p, text)})


def _activity_numbers(text: str) -> set:
    found = {int(m.group(1)) for m in re.finditer(r"\bactividad(?:es)?\s+(?:numero\s+)?(?:a-?)?0*(\d+)", text)}
    return found | {int(m.group(1)) for m in re.finditer(r"(?<![a-z0-9])a-?0*(\d+)(?![0-9])", text)}


def direction_warning(text: str, instruction: dict) -> Optional[str]:
    """
    For a precedence instruction (``X.Order_Before`` holds Y: X ends before Y
    starts), warn when a clause names the two in an order that inverts that
    direction: "Y ... antes ... X" or "X ... depende de / despues de ... Y".
    Clauses about another activity are skipped.
    """
    parts = instruction["path"].split(".")
    field, value = parts[-1], instruction.get("value")
    if field not in ("Order_Before", "Activity_Order_Before") or not isinstance(value, str):
        return None
    target = re.fullmatch(r"[AT]0*(\d+)", value)
    if field == "Activity_Order_Before":
        kind, source, activity = "activity", re.fullmatch(r"A0*(\d+)", parts[0]), None
    else:
        kind = "task"
        source = re.fullmatch(r"T0*(\d+)", parts[2]) if len(parts) >= 3 else None
        activity = re.fullmatch(r"A0*(\d+)", parts[0])
    if not (target and source):
        return None
    x, y = int(source.group(1)), int(target.group(1))
    for clause in re.split(r"[.;,]|\s+y\s+", text):
        if activity is not None:
            mentioned = _activity_numbers(clause)
            if mentioned and int(activity.group(1)) not in mentioned:
                continue
        xs, ys = _mention_positions(clause, kind, x), _mention_positions(clause, kind, y)
        if not (xs and ys):
            continue
        for forward, cues in ((True, _FORWARD_CUES), (False, _BACKWARD_CUES)):
            for cue in cues:
                for m in re.finditer(r"(?<![a-z])" + cue, clause):
                    before = [(p, "x") for p in xs if p < m.start()] + [(p, "y") for p in ys if p < m.start()]
                    after = [(p, "x") for p in xs if p >= m.end()] + [(p, "y") for p in ys if p >= m.end()]
                    if not (before and after):
                        continue
                    left, right = max(before)[1], min(after)[1]
                    if left != right and (left == "x") != forward:
                        first, second = (y, x) if forward else (x, y)
                        return (f"{instruction['path']} = {value} ({kind} {x} before {kind} {y}), text reads "
                                f"'{kind} {first} ... {m.group(0)} ... {kind} {second}': \"{clause.strip()}\"")
    return None


def unit_warnings(text: str, instruction: dict) -> List[str]:
    """
    Units attached to the instruction's number, which carries none. Hours on a
    time field are not reported: they are the schema's unit for times.
    """
    value = instruction.get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        return []
    field = instruction["path"].split(".")[-1]
    words = _alternation(cardinal_words(value))
    number = int_pattern(value) + (rf"|\b(?:{words})\b" if words else "")
    found = []
    for unit, pattern in UNITS.items():
        if unit == "hours" and field in TIME_FIELDS:
            continue
        match = re.search(rf"(?:{number})\s*(?:{pattern})(?![a-z])", text)
        if match is None and unit == "currency":
            match = re.search(rf"(?:€|\$|usd)\s*(?:{number})", text)
        if match:
            found.append(f"{field} = {value}: '{match.group(0).strip()}'")
    return found


def parameter_mention(text: str, field: str) -> bool:
    literal = normalize(field)
    return literal in text or literal.replace("_", " ") in text or _any_term(text, FIELD_TERMS.get(field, []))


def value_mention(text: str, field: str, operation: str, value) -> str:
    """'ok', 'weak', 'missing' or 'n/a'."""
    if operation == "DELETE" or value is None:
        return "n/a"
    if isinstance(value, bool):
        return "weak" if _any_term(text, _TRUE_CUES if value else _FALSE_CUES) else "missing"
    if isinstance(value, int):
        words = _alternation(cardinal_words(value))
        found = re.search(int_pattern(value), text) or (words and re.search(rf"\b(?:{words})\b", text))
        if found:
            return "weak" if value == 1 else "ok"
        return "weak" if value == 1 else "missing"
    if isinstance(value, str):
        code = re.fullmatch(r"([AT])0*(\d+)", value)
        if code and field in ("Activity_Order_Before", "Order_Before"):
            kind = "activity" if code.group(1) == "A" else "task"
            return "missing" if id_mention(text, kind, int(code.group(2))) == "missing" else "ok"
        team = re.fullmatch(r"Team([A-Z])", value)
        if team:
            letter = team.group(1).lower()
            return "ok" if re.search(rf"\b(?:team|equipo|cuadrilla)\s*-?\s*{letter}\b", text) else "missing"
        return "ok" if normalize(value) in text else "missing"
    return "ok" if normalize(str(value)) in text else "missing"


def check_instruction(text: str, instruction: dict) -> dict:
    """Mentions of one technical instruction in a normalised request."""
    operation = str(instruction["operation"]).split(".")[-1]
    path = instruction["path"]
    parts = path.split(".")
    field = parts[-1]
    checks: Dict[str, str] = {}

    act = re.fullmatch(r"A0*(\d+)", parts[0])
    if act:
        checks["activity"] = id_mention(text, "activity", int(act.group(1)))
    if len(parts) >= 3 and parts[1] == "tasks":
        task = re.fullmatch(r"T0*(\d+)", parts[2])
        if task:
            checks["task"] = id_mention(text, "task", int(task.group(1)))
    checks["parameter"] = "ok" if parameter_mention(text, field) else "missing"
    checks["value"] = value_mention(text, field, operation, instruction.get("value"))
    checks["operation"] = "ok" if _any_term(text, OPERATION_TERMS.get(operation, [])) else "missing"

    missing = [k for k, v in checks.items() if v == "missing" and k != "operation"]
    return {
        "instruction": f"{operation} {path}" + ("" if instruction.get("value") is None else f" = {instruction['value']}"),
        "checks": checks,
        "missing": missing,
        "ok": not missing,
    }


def check_request(request: Optional[str], instructions: List[dict]) -> dict:
    text = normalize(request)
    if not text.strip():
        return {"ok": False, "empty": True, "failures": ["empty request"], "per_instruction": [], "literal_keys": [],
                "direction_warnings": [], "unit_warnings": []}
    per_instruction = [check_instruction(text, instr) for instr in instructions]
    failures = [
        f"#{i + 1} {r['instruction']}: missing {', '.join(r['missing'])}"
        for i, r in enumerate(per_instruction) if not r["ok"]
    ]
    literal = [k for k in LITERAL_KEYS if k in (request or "")]
    direction = [f"#{i + 1} {w}" for i, instr in enumerate(instructions) if (w := direction_warning(text, instr))]
    units = [f"#{i + 1} {w}" for i, instr in enumerate(instructions) for w in unit_warnings(text, instr)]
    return {"ok": not failures, "empty": False, "failures": failures, "per_instruction": per_instruction,
            "literal_keys": literal, "direction_warnings": direction, "unit_warnings": units}


# ---------------------------------------------------------------- report

def _instructions(record: dict) -> List[dict]:
    tech = record["instruction_technical"]
    return tech if isinstance(tech, list) else [tech]


def fidelity_table(records: List[dict]) -> pd.DataFrame:
    rows = []
    for rec in records:
        instructions = _instructions(rec)
        new = check_request(rec["instruction_natural"], instructions)
        orig = check_request(rec["instruction_natural_original"], instructions)
        rows.append({
            "axis": rec["axis"],
            "level": rec["level"],
            "sample_idx": rec["sample_idx"],
            "n_instructions": len(instructions),
            "new_ok": new["ok"],
            "new_empty": new["empty"],
            "new_n_failed": len(new["failures"]),
            "new_failures": " | ".join(new["failures"]),
            "new_literal_keys": " ".join(new["literal_keys"]),
            "new_direction_warnings": " | ".join(new["direction_warnings"]),
            "new_unit_warnings": " | ".join(new["unit_warnings"]),
            "orig_ok": orig["ok"],
            "orig_n_failed": len(orig["failures"]),
            "orig_failures": " | ".join(orig["failures"]),
            "orig_direction_warnings": " | ".join(orig["direction_warnings"]),
            "orig_unit_warnings": " | ".join(orig["unit_warnings"]),
            "new_chars": len(rec["instruction_natural"] or ""),
            "orig_chars": len(rec["instruction_natural_original"] or ""),
            "format_ok": (rec.get("format_check") or {}).get("ok"),
        })
    return pd.DataFrame(rows)


def review_pairs(records: List[dict], table: pd.DataFrame, n: int, seed: int) -> str:
    rng = random.Random(seed)
    chosen = sorted(rng.sample(range(len(records)), min(n, len(records))),
                    key=lambda i: (records[i]["axis"], records[i]["level"], records[i]["sample_idx"]))
    lines = [f"# Original vs re-humanised requests ({len(chosen)} random pairs, seed {seed})", ""]
    for k, i in enumerate(chosen, 1):
        rec, row = records[i], table.iloc[i]
        lines += [
            f"## {k}. {rec['axis']} level {rec['level']}, sample {rec['sample_idx']}",
            "",
            "Technical: " + "; ".join(check_instruction("", instr)["instruction"] for instr in _instructions(rec)),
            "",
            f"- Original ({rec.get('humanizer_original', 'gpt-oss:20b')}): {rec['instruction_natural_original']}",
            f"- New ({rec['humanizer_model']}): {rec['instruction_natural']}",
            f"- Fidelity new: {'ok' if row['new_ok'] else row['new_failures']}",
            f"- Fidelity original: {'ok' if row['orig_ok'] else row['orig_failures']}",
            f"- Warnings new: {_warnings(row, 'new')}",
            f"- Warnings original: {_warnings(row, 'orig')}",
            "",
        ]
    return "\n".join(lines)


def _warnings(row, prefix: str) -> str:
    parts = [f"{label}: {row[f'{prefix}_{col}']}" for label, col in
             (("direction", "direction_warnings"), ("units", "unit_warnings")) if row[f"{prefix}_{col}"]]
    return "; ".join(parts) or "none"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fidelity check of re-humanised requests")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--requests", default=None, help="requests_<model>.jsonl (default: the only one in the run dir)")
    parser.add_argument("--n-review", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = resolve_run_dir(args.run_dir)
    requests_path = find_requests_file(run_dir, args.requests)
    slug = requests_path.stem[len("requests_"):]
    records = read_jsonl(requests_path)

    table = fidelity_table(records)
    csv_path = run_dir / f"fidelity_{slug}.csv"
    table.to_csv(csv_path, index=False)
    review = review_pairs(records, table, args.n_review, args.seed)
    md_path = run_dir / f"review_pairs_{slug}.md"
    md_path.write_text(review, encoding="utf-8")

    print(review)
    print("\nFlagged requests (new / original), per level:")
    for (axis, level), g in table.groupby(["axis", "level"]):
        print(f"  {axis:12s} L{level:>3}: new {int((~g['new_ok']).sum()):>2}/{len(g)}   original {int((~g['orig_ok']).sum()):>2}/{len(g)}")
    print(f"  total          : new {int((~table['new_ok']).sum())}/{len(table)}   original {int((~table['orig_ok']).sum())}/{len(table)}")
    missing = Counter(
        part.split("missing ")[-1]
        for failures in table.loc[~table["new_ok"], "new_failures"] for part in failures.split(" | ") if part
    )
    if missing:
        print("  missing in new requests: " + ", ".join(f"{k} x{v}" for k, v in missing.most_common()))
    print("\nWarnings (nothing is flagged or dropped for them), new / original:")
    for label, col in (("possible inverted precedence", "direction_warnings"), ("unit added", "unit_warnings")):
        print(f"  {label:28s}: new {int((table[f'new_{col}'] != '').sum())}/{len(table)}   "
              f"original {int((table[f'orig_{col}'] != '').sum())}/{len(table)}")
    for _, row in table[(table["new_direction_warnings"] != "") | (table["new_unit_warnings"] != "")].iterrows():
        print(f"  {row['axis']} L{row['level']} #{row['sample_idx']}: {_warnings(row, 'new')}")
    print(f"\nTable  -> {csv_path}\nReview -> {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
