"""
Author: Noah Masegosa Caceres 
Center: @ugr

Objective: Herramientas auxiliares para el agente de entrada.
"""

import contextlib
import io
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from input_agent.pn_models import ACTIVITY_KEY_RE, TASK_KEY_RE
from input_agent.src.models import ModificationBatch, Colors
from input_agent.src.prompts import CONTEXT_PROMPT

def build_topology_map(flat_ids_list):
    """
    Construye un mapa de topología a partir de una lista plana de IDs con lo que cada uno precede.
    Args:
        flat_ids_list (List[Dict[str, Any]]): Lista plana de IDs con sus tipos y lo que preceden.
    Returns:
        Dict[str, Any]: Mapa de topología estructurado.
    """
    topology = {}
    
    for item in flat_ids_list:
        if item['type'] == 'Activity':
            # Creamos la entrada de la Actividad
            act_id = item['id']
            topology[act_id] = {
                "precedes": item['precedes'],
                "tasks": {} # Aquí meteremos las tareas
            }
    
    # Segunda pasada para las tareas
    for item in flat_ids_list:
        if item['type'] == 'Task':
            parent = item['parent_activity']
            task_id = item['id']
            if parent in topology:
                topology[parent]["tasks"][task_id] = item['precedes']
                
    return topology

def extract_validation_context(full_data: Dict[str, Any], modified_path: str) -> Dict[str, Any]:
    """
    Construye un subconjunto optimizado de datos para enviarlo al Validador LLM.
    
    El objetivo es reducir el consumo de tokens enviando solo la información 
    estructural relevante (topología, IDs, precedencias) en lugar de todo el JSON pesado.

    Args:
        full_data (Dict[str, Any]): El JSON completo original.
        modified_path (str): La ruta donde ocurrió el cambio principal (para enfocar la atención).

    Returns:
        Dict[str, Any]: Contexto limpio conteniendo globales, mapa de IDs y el snippet afectado.
    """
    context = {
        # Extraemos configuraciones globales (las que no empiezan por "A" de Activity)
        "globals": {k: v for k, v in full_data.items() if not k.startswith("A")},
        "valid_ids": [],
        "existing_teams": []
    }

    found_teams = set()

    # Recorremos todas las actividades (IDs que empiezan por "A") para construir el grafo de precedencias
    for a_id, a_data in full_data.items():
        if not a_id.startswith("A"): continue

        # Recolectamos equipos para validar límites de recursos (ej: no exceder max teams)
        if "Team" in a_data:
            found_teams.add(a_data["Team"])

        # Mapeo de Actividad y de lo que precede: activityCode nombra las actividades que su dueño
        # precede, que es como lo ejecuta el motor. Lista vacía sin el flag.
        a_precedes = a_data.get("activityCode", []) if a_data.get("activityDependency") else []
        
        context["valid_ids"].append({
            "id": a_id,
            "type": "Activity",
            "precedes": a_precedes
        })

        # Mapeo de Tareas dentro de la Actividad
        tasks = a_data.get("tasks", {})
        for t_id, t_data in tasks.items():
            # taskCode nombra las tareas de la actividad que su dueño precede.
            t_precedes = t_data.get("taskCode", []) if t_data.get("taskDependency") else []
            
            context["valid_ids"].append({
                "id": t_id,
                "type": "Task",
                "parent_activity": a_id,
                "precedes": t_precedes
            })

    context["existing_teams"] = list(found_teams)

    # Identificamos el fragmento específico que se modificó para ponerlo en "primer plano"
    root_key = modified_path.split('.')[0] 
    
    if root_key.startswith("A") and root_key in full_data:
        # Si el cambio fue dentro de una actividad existente, enviamos esa actividad completa
        context["focus_snippet"] = { root_key: full_data[root_key] }
    else:
        # Si se creó algo nuevo o fue un cambio global, marcamos flag especial
        context["focus_snippet"] = { "note": "The change affects global settings or a new entity." }

    return context

# ============== VALIDADOR DETERMINISTA ==============

DOMINIO = "DOMINIO"
RED_DE_PETRI = "RED DE PETRI"

# Regla -> grupo. DOMINIO: tipos, dominios y relaciones que fija la semántica del plan de
# mantenimiento. RED DE PETRI: lo que la instanciación de la red o el simulador necesitan para estar
# bien definidos. Ver el docstring de deterministic_validator.
RULES = {
    "campos_esquema": DOMINIO,
    "tipos": DOMINIO,
    "equipos": DOMINIO,
    "ids": DOMINIO,
    "limites": DOMINIO,
    "referencias": DOMINIO,
    "rangos": DOMINIO,
    "sanity_batch": DOMINIO,
    "campos_fuera_de_nivel": DOMINIO,
    "campos_leidos": RED_DE_PETRI,
    "no_vacia": RED_DE_PETRI,
    "dom_real": RED_DE_PETRI,
    "dom_int": RED_DE_PETRI,
    "turno_minimo": RED_DE_PETRI,
    "prec_tipos": RED_DE_PETRI,
    "prec_aciclica": RED_DE_PETRI,
}

GLOBAL_FIELDS = ("runId", "Teams", "Simulation_period")
READ_ACTIVITY_FIELDS = ("tasks", "T_period", "T_wait", "Start_disp", "Team members", "Shift_duration")
READ_TASK_FIELDS = ("Duration",)
DELAY_FIELDS = ("T_period", "T_wait", "Start_disp", "Shift_duration")
# Campos conocidos del modelo por nivel [E, P:126-135, M].
ACTIVITY_LEVEL_FIELDS = {
    "tasks", "T_period", "T_wait", "Start_disp", "Team", "Team members", "Shift_duration",
    "Activity_Order_Enforced", "Activity_Order_Before", "activityDependency", "activityCode",
}
TASK_LEVEL_FIELDS = {"Duration", "Requires_Shutdown", "Cost_per_hour", "Order_Enforced", "Order_Before", "taskDependency", "taskCode"}
MAX_ACTIVITIES = 1000
MAX_TASKS_PER_ACTIVITY = 1000

INTEGER_FIELDS = {"runId", "Teams", "Team members"}
NUMBER_FIELDS = {"Simulation_period", "T_period", "T_wait", "Start_disp", "Shift_duration", "Duration", "Cost_per_hour"}
BOOL_FIELDS = {"Requires_Shutdown", "Order_Enforced", "Activity_Order_Enforced", "taskDependency", "activityDependency"}
STRING_FIELDS = {"Team"}
STRING_LIST_FIELDS = {"Order_Before", "Activity_Order_Before", "taskCode", "activityCode"}
# Campos que el esquema declara Optional (admiten null). El resto de campos opcionales, no.
NULLABLE_FIELDS = {"taskDependency", "activityDependency", "taskCode", "activityCode"}
# Campos obligatorios: su null lo decide campos_leidos o campos_esquema, no tipos.
REQUIRED_FIELDS = set(GLOBAL_FIELDS) | set(READ_ACTIVITY_FIELDS) | set(READ_TASK_FIELDS) | {"Team", "Requires_Shutdown"}


@dataclass(frozen=True)
class Violation:
    """Subestructura ofensora: regla incumplida, grupo, ruta en la configuración y detalle."""

    rule: str
    path: str
    detail: str

    @property
    def group(self) -> str:
        return RULES[self.rule]

    def to_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "group": self.group, "path": self.path, "detail": self.detail}

    def __str__(self) -> str:
        return format_violation(self.to_dict())


def format_violation(violation: Dict[str, str]) -> str:
    return f"[{violation['rule']} | {violation['group']}] {violation['path'] or '<root>'}: {violation['detail']}"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_float(value: Any) -> Optional[float]:
    """Conversión a float, como la hace la traducción a la red; None si no se puede o no es finito."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _as_exact_int(value: Any) -> Optional[int]:
    """int(v), como la red lee un peso de arco, siempre que no trunque nada."""
    number = _as_float(value)
    if number is None:
        return None
    try:
        integer = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return integer if integer == number else None


# Textos que se leen como un flag activo o inactivo; cualquier otro valor cuenta por su veracidad.
FLAG_TRUE_TEXTS = {"1", "true", "t", "yes", "y"}
FLAG_FALSE_TEXTS = {"0", "false", "f", "no", "n", ""}


def _flag_on(value: Any) -> bool:
    """Flag leído como lo lee la construcción de la red: un booleano tal cual, un número si no es
    0, un texto según FLAG_TRUE_TEXTS / FLAG_FALSE_TEXTS (sin mayúsculas ni espacios) y, si no,
    por su veracidad."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in FLAG_TRUE_TEXTS:
            return True
        if text in FLAG_FALSE_TEXTS:
            return False
    return bool(value)


def _present(container: Dict[str, Any], field: str) -> bool:
    return field in container and container[field] is not None


# Los detalles de las violaciones están en inglés y dicen qué campo apunta a qué, con las rutas en
# forma corta (A002.T002 en lugar de A002.tasks.T002).

def _label(path: str) -> str:
    return path.replace(".tasks.", ".")


def _show(value: Any) -> str:
    """Valor tal como aparece en el JSON de la configuración (repr si no es serializable)."""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a text"
    if isinstance(value, (list, tuple)):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return type(value).__name__


def _declared_activities(config: Dict[str, Any]) -> Dict[str, Any]:
    """Claves con formato de actividad y cualquier dict con 'tasks', que la traducción a la red
    trata como actividad aunque su clave no tenga ese formato."""
    return {
        key: value
        for key, value in config.items()
        if key not in GLOBAL_FIELDS
        and (ACTIVITY_KEY_RE.match(str(key)) or (isinstance(value, dict) and "tasks" in value))
    }


# --- campos_leidos (RED) y campos_esquema (DOMINIO) ------------------------------------------

def _check_fields(config, declared) -> List[Violation]:
    out = []

    def missing(container, field, path, rule, owner):
        if field not in container:
            out.append(Violation(rule, path, f"{owner} has no {field} field"))
        elif container[field] is None:
            out.append(Violation(rule, path, f"{owner} has {field} = null"))

    for field in GLOBAL_FIELDS:
        missing(config, field, field, "campos_leidos", "the configuration")
    for aid, activity in declared.items():
        if not isinstance(activity, dict):
            out.append(Violation("campos_leidos", aid, f"{aid} is {_json_type(activity)}, not an object, so the translation to the Petri net drops it"))
            continue
        for field in READ_ACTIVITY_FIELDS:
            missing(activity, field, f"{aid}.{field}", "campos_leidos", aid)
        missing(activity, "Team", f"{aid}.Team", "campos_esquema", aid)
        tasks = activity.get("tasks")
        if tasks is None:
            continue
        if not isinstance(tasks, dict):
            out.append(Violation("campos_leidos", f"{aid}.tasks", f"{aid}.tasks is {_json_type(tasks)}, not an object of tasks"))
            continue
        for tid, task in tasks.items():
            path = f"{aid}.tasks.{tid}"
            if not isinstance(task, dict):
                out.append(Violation("campos_leidos", path, f"{aid}.{tid} is {_json_type(task)}, not an object"))
                continue
            for field in READ_TASK_FIELDS:
                missing(task, field, f"{path}.{field}", "campos_leidos", f"{aid}.{tid}")
            missing(task, "Requires_Shutdown", f"{path}.Requires_Shutdown", "campos_esquema", f"{aid}.{tid}")
    return out


# --- no_vacia (RED) ------------------------------------------------------------------------------

def _check_no_vacia(declared, usable) -> List[Violation]:
    if not declared:
        return [Violation("no_vacia", "", "the configuration has no activities")]
    return [Violation("no_vacia", f"{aid}.tasks", f"{aid} has no tasks") for aid, act in usable.items() if not act["tasks"]]


# --- dom_real, turno_minimo, dom_int (RED) ----------------------------------------------------------

def _check_dom_real(config, declared) -> List[Violation]:
    out = []
    if _present(config, "Simulation_period"):
        value = config["Simulation_period"]
        number = _as_float(value)
        if number is None or number <= 0:
            out.append(Violation("dom_real", "Simulation_period", f"Simulation_period is {_show(value)}; it must be a finite number > 0"))
    for aid, activity in declared.items():
        if not isinstance(activity, dict):
            continue
        for field in DELAY_FIELDS:
            if _present(activity, field):
                value = activity[field]
                number = _as_float(value)
                if number is None or number < 0:
                    out.append(Violation("dom_real", f"{aid}.{field}", f"{aid}.{field} is {_show(value)}; it must be a finite number >= 0"))
    return out


def _check_turno_minimo(declared) -> List[Violation]:
    out = []
    for aid, activity in declared.items():
        if isinstance(activity, dict) and _present(activity, "Shift_duration"):
            number = _as_float(activity["Shift_duration"])
            if number is not None and 0 <= number < 1:
                out.append(Violation("turno_minimo", f"{aid}.Shift_duration", f"{aid}.Shift_duration is {_show(activity['Shift_duration'])}; it must be >= 1 (hours)"))
    return out


def _check_dom_int(declared, usable) -> List[Violation]:
    out = []

    def check(container, field, path):
        if _present(container, field):
            value = container[field]
            integer = _as_exact_int(value)
            if integer is None or integer < 1:
                out.append(Violation("dom_int", path, f"{_label(path)} is {_show(value)}; it must be an integer >= 1"))

    for aid, activity in declared.items():
        if isinstance(activity, dict):
            check(activity, "Team members", f"{aid}.Team members")
    for aid, activity in usable.items():
        for tid, task in activity["tasks"].items():
            if isinstance(task, dict):
                check(task, "Duration", f"{aid}.tasks.{tid}.Duration")
    return out


# --- tipos (DOMINIO) -------------------------------------------------------------------------------

def _type_error(field: str, value: Any) -> Optional[str]:
    """Requisito de tipo que value incumple, o None si lo cumple."""
    if value is None:
        if field in REQUIRED_FIELDS or field in NULLABLE_FIELDS:
            return None
        return "it cannot be null"
    if field in INTEGER_FIELDS:
        if not _is_number(value) or not math.isfinite(value) or not float(value).is_integer():
            return "it must be an integer"
    elif field in NUMBER_FIELDS:
        if not _is_number(value):
            return "it must be a number"
    elif field in BOOL_FIELDS:
        if not isinstance(value, bool):
            return "it must be true or false"
    elif field in STRING_FIELDS:
        if not isinstance(value, str):
            return "it must be a text"
    elif field in STRING_LIST_FIELDS:
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            return "it must be a list of IDs (texts)"
    return None


def _check_tipos(config, declared) -> List[Violation]:
    out = []

    def check(container, path_prefix):
        for field, value in container.items():
            error = _type_error(field, value)
            if error:
                path = f"{path_prefix}{field}"
                out.append(Violation("tipos", path, f"{_label(path)} is {_show(value)}; {error}"))

    check({k: config[k] for k in GLOBAL_FIELDS if k in config}, "")
    for aid, activity in declared.items():
        if not isinstance(activity, dict):
            continue
        check(activity, f"{aid}.")
        tasks = activity.get("tasks")
        if isinstance(tasks, dict):
            for tid, task in tasks.items():
                if isinstance(task, dict):
                    check(task, f"{aid}.tasks.{tid}.")
    return out


# --- equipos, ids, limites, rangos (DOMINIO) -------------------------------------------------------

def _check_equipos(config) -> List[Violation]:
    """Condición de v1 (check_resource_limits): etiquetas Team distintas <= Teams."""
    max_teams = config.get("Teams")
    if not _is_number(max_teams):
        return []
    labels = set()
    for key, value in config.items():
        if key not in GLOBAL_FIELDS and isinstance(value, dict) and "Team" in value:
            try:
                labels.add(value["Team"])
            except TypeError:
                continue
    if len(labels) > max_teams:
        names = ", ".join(sorted(str(label) for label in labels))
        return [Violation("equipos", "Teams", f"the activities use {len(labels)} distinct Team labels ({names}) but Teams is {_show(max_teams)}")]
    return []


def _check_ids(declared) -> List[Violation]:
    out = []
    for aid, activity in declared.items():
        if not ACTIVITY_KEY_RE.match(str(aid)):
            out.append(Violation("ids", aid, f"the activity key {aid} does not have the form Axxx"))
            continue
        tasks = activity.get("tasks") if isinstance(activity, dict) else None
        if isinstance(tasks, dict):
            for tid in tasks:
                if not TASK_KEY_RE.match(str(tid)):
                    out.append(Violation("ids", f"{aid}.tasks.{tid}", f"{aid} has the task key {tid}, which does not have the form Txxx"))
    return out


def _check_limites(declared, usable) -> List[Violation]:
    out = []
    if len(declared) > MAX_ACTIVITIES:
        out.append(Violation("limites", "", f"the configuration has {len(declared)} activities; the maximum is {MAX_ACTIVITIES}"))
    for aid, activity in usable.items():
        if len(activity["tasks"]) > MAX_TASKS_PER_ACTIVITY:
            out.append(Violation("limites", f"{aid}.tasks", f"{aid} has {len(activity['tasks'])} tasks; the maximum is {MAX_TASKS_PER_ACTIVITY}"))
    return out


def _check_rangos(declared, usable) -> List[Violation]:
    out = []
    for aid, activity in declared.items():
        if not isinstance(activity, dict):
            continue
        if _is_number(activity.get("T_period")) and activity["T_period"] <= 0:
            out.append(Violation("rangos", f"{aid}.T_period", f"{aid}.T_period is {_show(activity['T_period'])}; it must be > 0"))
        if _is_number(activity.get("Shift_duration")) and activity["Shift_duration"] > 24:
            out.append(Violation("rangos", f"{aid}.Shift_duration", f"{aid}.Shift_duration is {_show(activity['Shift_duration'])}; it must be <= 24"))
    for aid, activity in usable.items():
        for tid, task in activity["tasks"].items():
            if isinstance(task, dict) and _is_number(task.get("Cost_per_hour")) and task["Cost_per_hour"] < 0:
                out.append(Violation("rangos", f"{aid}.tasks.{tid}.Cost_per_hour", f"{aid}.{tid}.Cost_per_hour is {_show(task['Cost_per_hour'])}; it must be >= 0"))
    return out


# --- campos_fuera_de_nivel (DOMINIO) ---------------------------------------------------------------

def _check_campos_fuera_de_nivel(config, declared) -> List[Violation]:
    """Campos conocidos del modelo escritos en un nivel que no les corresponde. Las claves
    desconocidas siguen permitidas (extra="allow" en el esquema)."""
    out = []
    for key in config:
        if key in ACTIVITY_LEVEL_FIELDS or key in TASK_LEVEL_FIELDS:
            level = "an activity" if key in ACTIVITY_LEVEL_FIELDS else "a task"
            out.append(Violation("campos_fuera_de_nivel", key, f"{key} is {level} field, but it is at the root of the configuration"))
    for aid, activity in declared.items():
        if not isinstance(activity, dict):
            continue
        for key in activity:
            if key in TASK_LEVEL_FIELDS or key in GLOBAL_FIELDS:
                level = "a task" if key in TASK_LEVEL_FIELDS else "a global"
                out.append(Violation("campos_fuera_de_nivel", f"{aid}.{key}", f"{aid} has {key}, which is {level} field, not an activity field"))
        tasks = activity.get("tasks")
        if isinstance(tasks, dict):
            for tid, task in tasks.items():
                if isinstance(task, dict):
                    for key in task:
                        if key in ACTIVITY_LEVEL_FIELDS or key in GLOBAL_FIELDS:
                            level = "an activity" if key in ACTIVITY_LEVEL_FIELDS else "a global"
                            out.append(Violation("campos_fuera_de_nivel", f"{aid}.tasks.{tid}.{key}", f"{aid}.{tid} has {key}, which is {level} field, not a task field"))
    return out


# --- referencias (DOMINIO) -------------------------------------------------------------------------

def _check_referencias(usable, previous_config=None) -> List[Violation]:
    """previous_config: la configuración antes del batch (S_k), si se conoce. Con ella el detalle
    distingue una referencia a algo que el batch ha borrado ("no longer exists") de una a algo que
    no ha existido ("does not exist")."""
    previous = previous_config if isinstance(previous_config, dict) else {}
    out = []
    for aid, activity in usable.items():
        tasks = activity["tasks"]
        for field in ("Activity_Order_Before", "activityCode"):
            entries = activity.get(field)
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, str) and entry in usable:
                        continue
                    if not isinstance(entry, str):
                        detail = f"{aid} lists {_show(entry)} in {field}, which is not an activity ID"
                    else:
                        status = "no longer exists" if isinstance(previous.get(entry), dict) else "does not exist"
                        detail = f"{aid} lists {entry} in {field}, but {entry} {status}"
                    out.append(Violation("referencias", f"{aid}.{field}", detail))
        previous_activity = previous.get(aid) if isinstance(previous.get(aid), dict) else {}
        previous_tasks = previous_activity.get("tasks") if isinstance(previous_activity.get("tasks"), dict) else {}
        for tid, task in tasks.items():
            if not isinstance(task, dict):
                continue
            for field in ("Order_Before", "taskCode"):
                entries = task.get(field)
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, str) and entry in tasks:
                            continue
                        if not isinstance(entry, str):
                            detail = f"{aid}.{tid} lists {_show(entry)} in {field}, which is not a task ID"
                        else:
                            status = "no longer exists" if entry in previous_tasks else "does not exist"
                            detail = f"{aid}.{tid} lists {entry} in {field}, but {entry} {status} in {aid}"
                        out.append(Violation("referencias", f"{aid}.tasks.{tid}.{field}", detail))
    return out


# --- sanity_batch (DOMINIO): condición Sanity de v1, sobre el batch --------------------------------

def _check_sanity_batch(batch_object) -> List[Violation]:
    out = []
    if batch_object is None:
        return out
    numeric_fields = ["T_period", "T_wait", "Start_disp", "Shift_duration", "Duration"]
    for instr in batch_object.instructions:
        val = instr.value
        if not isinstance(val, dict):
            continue
        for field in numeric_fields:
            num_val = val.get(field)
            if num_val is not None and (not isinstance(num_val, (int, float)) or num_val < 0):
                out.append(Violation("sanity_batch", instr.path, f"the instruction on {instr.path} sets {field} to {_show(num_val)}; it must be a non-negative number"))
        members = val.get("Team members")
        if members is not None and (not isinstance(members, int) or members < 0):
            out.append(Violation("sanity_batch", instr.path, f"the instruction on {instr.path} sets Team members to {_show(members)}; it must be a non-negative integer"))
    return out


# --- prec_tipos y prec_aciclica (RED) --------------------------------------------------------------

def _as_list_like(value: Any) -> List[Any]:
    """Lectura de Order_Before / Activity_Order_Before como en la construcción de la red:
    None -> [], lista -> lista, escalar -> [escalar]."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _active_edges(usable) -> Tuple[List[Violation], Dict[str, List[Tuple[str, str, str]]], List[Tuple[str, str, str]]]:
    """Listas de precedencia activas, leídas con el mismo flag que la construcción de la red:
    Order_Enforced, taskDependency y activityDependency por veracidad y Activity_Order_Enforced
    como un flag (_flag_on). Devuelve los errores de forma y las aristas válidas."""
    violations: List[Violation] = []
    task_edges: Dict[str, List[Tuple[str, str, str]]] = {}
    activity_edges: List[Tuple[str, str, str]] = []

    for aid, activity in usable.items():
        tasks = activity["tasks"]
        edges = []
        for tid, task in tasks.items():
            if not isinstance(task, dict):
                continue
            lists = []
            if task.get("Order_Enforced", False) and task.get("Order_Before"):
                lists.append(("Order_Before", _as_list_like(task["Order_Before"])))
            if task.get("taskDependency", False):
                code = task.get("taskCode", [])
                if isinstance(code, (list, tuple)):
                    lists.append(("taskCode", list(code)))
                else:
                    violations.append(Violation("prec_tipos", f"{aid}.tasks.{tid}.taskCode", f"{aid}.{tid} has taskDependency = true, but its taskCode is {_show(code)}, not a list of task IDs"))
            for field, entries in lists:
                for entry in entries:
                    if isinstance(entry, str) and entry in tasks:
                        edges.append((tid, entry, f"{aid}.tasks.{tid}.{field}"))
        task_edges[aid] = edges

        if _flag_on(activity.get("Activity_Order_Enforced", False)) and activity.get("Activity_Order_Before"):
            entries = _as_list_like(activity["Activity_Order_Before"])
            not_ids = [entry for entry in entries if isinstance(entry, (list, dict, set))]
            if not_ids:
                # la construcción de la red usa cada entrada como clave
                violations.append(Violation("prec_tipos", f"{aid}.Activity_Order_Before", f"{aid} lists {_show(not_ids)} in Activity_Order_Before; these entries are not activity IDs and the Petri net cannot be built"))
            for entry in entries:
                if isinstance(entry, str) and entry in usable:
                    activity_edges.append((aid, entry, f"{aid}.Activity_Order_Before"))
        if activity.get("activityDependency", False):
            code = activity.get("activityCode", [])
            if isinstance(code, (list, tuple)):
                for entry in code:
                    if isinstance(entry, str) and entry in usable:
                        activity_edges.append((aid, entry, f"{aid}.activityCode"))
            else:
                violations.append(Violation("prec_tipos", f"{aid}.activityCode", f"{aid} has activityDependency = true, but its activityCode is {_show(code)}, not a list of activity IDs"))
    return violations, task_edges, activity_edges


def _strongly_connected_components(nodes, edges) -> List[List[str]]:
    """Tarjan iterativo."""
    adjacency = {n: [] for n in nodes}
    for before, after, _ in edges:
        adjacency[before].append(after)
    index, lowlink, on_stack, stack, components, counter = {}, {}, set(), [], [], 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, child = work.pop()
            if child == 0:
                index[node] = lowlink[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            recurse = False
            for i in range(child, len(adjacency[node])):
                succ = adjacency[node][i]
                if succ not in index:
                    work.append((node, i + 1))
                    work.append((succ, 0))
                    recurse = True
                    break
                if succ in on_stack:
                    lowlink[node] = min(lowlink[node], index[succ])
            if recurse:
                continue
            if lowlink[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return components


def _edge_text(after, path) -> str:
    """Arista (before, after, path): el campo de path, en la tarea o actividad before, lista after."""
    owner, field = _label(path).rsplit(".", 1)
    return f"{owner} lists {after} in {field}"


def _cycles(scope, edges) -> List[Violation]:
    out = []
    nodes = sorted({n for before, after, _ in edges for n in (before, after)})
    for before, after, path in edges:
        if before == after:
            owner, field = _label(path).rsplit(".", 1)
            out.append(Violation("prec_aciclica", path, f"{owner} lists itself ({after}) in {field}"))
    for component in _strongly_connected_components(nodes, edges):
        if len(component) < 2:
            continue
        members = set(component)
        cycle_edges = sorted({(b, a, p) for b, a, p in edges if b in members and a in members and b != a})
        detail = "precedence cycle among {}: {}".format(", ".join(sorted(members)), "; ".join(_edge_text(a, p) for _, a, p in cycle_edges))
        out.append(Violation("prec_aciclica", scope, detail))
    return out


# --- orquestador -----------------------------------------------------------------------------------

def check_configuration(
    config: Any, batch_object: Optional[ModificationBatch] = None, previous_config: Optional[Dict[str, Any]] = None
) -> List[Violation]:
    """Todas las violaciones de la configuración candidata (y, para sanity_batch, del batch).
    previous_config (S_k, opcional) solo cambia el detalle de referencias."""
    if not isinstance(config, dict):
        return [Violation("campos_leidos", "", f"the configuration is {_json_type(config)}, not an object")]
    declared = _declared_activities(config)
    usable = {aid: act for aid, act in declared.items() if isinstance(act, dict) and isinstance(act.get("tasks"), dict)}

    violations: List[Violation] = []
    violations += _check_fields(config, declared)
    violations += _check_no_vacia(declared, usable)
    violations += _check_dom_real(config, declared)
    violations += _check_turno_minimo(declared)
    violations += _check_dom_int(declared, usable)
    shape_violations, task_edges, activity_edges = _active_edges(usable)
    violations += shape_violations
    for aid, edges in task_edges.items():
        violations += _cycles(f"{aid}.tasks", edges)
    violations += _cycles("", activity_edges)
    violations += _check_tipos(config, declared)
    violations += _check_equipos(config)
    violations += _check_ids(declared)
    violations += _check_limites(declared, usable)
    violations += _check_referencias(usable, previous_config)
    violations += _check_rangos(declared, usable)
    violations += _check_sanity_batch(batch_object)
    violations += _check_campos_fuera_de_nivel(config, declared)
    return violations


def deterministic_validator(batch_object, engine, previous_config=None):
    """
    Validador determinista de la configuración candidata (engine.data, tras aplicar el batch y
    renumerar IDs temporales). Devuelve (es_valida, violaciones), con cada violación como
    {"rule", "group", "path", "detail"}: la subestructura ofensora. Todas las reglas se deciden
    sobre la configuración, sin construir el grafo de alcanzabilidad y sin simular; sanity_batch
    se decide además sobre el batch, como en v1. El detalle está en inglés y dice qué campo apunta
    a qué; previous_config (S_k, opcional) le permite a referencias decir si lo referenciado lo ha
    borrado el batch.

    Versión anterior (v1): reglas Resource, Sanity y Topology y el esquema PetriInput
    (input_agent/pn_models.py) en ValidatorEngine. tests/unit/v1_validator_reference.py las
    conserva, y los tests comprueban que todo lo que v1 rechazaba se sigue rechazando.

    Fuentes: [E] esquema (config/models.py = input_agent/pn_models.py); [S] samplers del dataset
    (input_agent/src/dataset_generator_*.py); [P] PLANNER_PROMPT (prompts.py); [C]
    test_inputs/catalog.md; [M] manual de variables de la red; [T] traducción a la red y simulador.

    DOMINIO (semántica del plan de mantenimiento). Si una configuración solo viola reglas de este
    grupo, el executor mantiene el diseño anterior y simula el candidato rechazado.
      campos_esquema  Team y Requires_Shutdown presentes y no null [E, M]. La red no los necesita:
                      Team es una etiqueta y Requires_Shutdown tiene un valor por defecto.
      tipos           Tipo JSON de cada campo documentado presente [E, P, M]: enteros (runId,
                      Teams, Team members: número con valor entero, 5 o 5.0), números
                      (Simulation_period, T_period, T_wait, Start_disp, Shift_duration, Duration,
                      Cost_per_hour), booleanos (Requires_Shutdown, Order_Enforced,
                      Activity_Order_Enforced, taskDependency, activityDependency: solo true o
                      false), texto (Team) y listas de IDs (Order_Before, Activity_Order_Before,
                      taskCode, activityCode). Rechaza textos y booleanos donde va un número. Solo
                      admiten null los campos que E declara Optional.
      equipos         Número de etiquetas Team distintas <= Teams [C input_25, M]. Igual que v1.
      ids             Claves de actividad con formato Axxx y, dentro de ellas, claves de tarea con
                      formato Txxx [E, P]. La condición de tareas es la de v1; la de actividades es
                      nueva. Los IDs temporales del Planner llegan ya renumerados por
                      PetriConfigEngine.reindex_structure.
      limites         Como mucho 1000 actividades y 1000 tareas por actividad, como protección
                      contra entradas desmesuradas. v1 (PetriInput) ponía 100, que el sampler supera.
                      Aunque es de DOMINIO, un candidato rechazado por limites no se simula.
      referencias     Toda entrada de Order_Before, Activity_Order_Before, taskCode y activityCode,
                      con o sin flag, es el ID de una tarea de la misma actividad o de una
                      actividad existente [M, P, S, C]. Amplía Topology de v1 (solo
                      taskCode/activityCode con el flag a True).
      rangos          T_period > 0, Shift_duration <= 24 y Cost_per_hour >= 0. Relaciones no
                      documentadas en las fuentes, añadidas por decisión.
      sanity_batch    Condición Sanity de v1 sobre los dicts de las instrucciones del batch:
                      T_period, T_wait, Start_disp, Shift_duration y Duration numéricos >= 0 y
                      Team members entero >= 0.
      campos_fuera_de_nivel
                      Ningún campo conocido del modelo está en un nivel que no le corresponde:
                      campos de actividad o de tarea en la raíz, campos de tarea o globales en la
                      actividad, y campos de actividad o globales en la tarea. La traducción a la
                      red lee cada campo en su nivel, así que esa edición no llega a la red y la
                      configuración no haría lo que declara [P]. Las claves desconocidas siguen
                      permitidas (relación i).

    RED DE PETRI (instanciación y simulador). Lo que la red necesita para estar bien definida
    [T]. Si se viola alguna, el executor no simula el candidato rechazado y pasa las violaciones
    al feedback.
      campos_leidos   runId, Teams, Simulation_period; por actividad tasks, T_period, T_wait,
                      Start_disp, Team members, Shift_duration; por tarea Duration; actividades y
                      tareas son objetos. Son los campos que lee la traducción a la red; sin
                      ellos la red no se puede construir o se construye con valores por defecto.
                      Team members y Shift_duration se exigen en todas las actividades para no
                      depender del orden en que se leen.
      no_vacia        >= 1 actividad y >= 1 tarea por actividad. Una actividad sin tareas deja una
                      transición sin arcos de entrada y el tiempo simulado no avanza.
      dom_real        T_period, T_wait, Start_disp, Shift_duration: float(v) finito >= 0;
                      Simulation_period: finito > 0. Son retardos y horizonte de la simulación: un
                      retardo negativo se simularía como 0 y con horizonte <= 0 no hay simulación.
      dom_int         Duration y Team members: int(v) == float(v) >= 1. Son pesos de arco, que la
                      red toma como enteros de al menos 1.
      turno_minimo    Shift_duration >= 1. t3 genera la cuadrilla por cada hora de turno, así que
                      con un turno de menos de una hora ninguna tarea llega a ejecutarse
                      (comprobado en la red).
      prec_tipos      Con el flag activo, taskCode y activityCode son listas, y
                      Activity_Order_Before solo tiene IDs, que la construcción de la red usa como
                      claves.
      prec_aciclica   Sin ciclos, autoprecedencia incluida, entre las precedencias activas; por
                      actividad a nivel de tareas y global a nivel de actividades. Con
                      autoprecedencia o en un ciclo, las transiciones implicadas esperan tokens que
                      solo producen ellas mismas y no se habilitan nunca (comprobado en la red).
                      Se decide sobre las cuatro listas, también las que la red no lee, así que
                      en esas la comprobación es conservadora [C].

    Relaciones consideradas y descartadas:
      a  Lista de precedencia no vacía con el flag a false: no es inválida en ninguna fuente, el
         flag solo la desactiva [M]; el sampler la genera.
      b  Duplicados en las listas: no cambian la red.
      d  Start_disp < Simulation_period: no documentada.
      e  T_wait < T_period: no documentada; T_wait tiene significados distintos según la fuente.
      g  Misma etiqueta Team, mismos Team members y Shift_duration: no documentada.
      h  Team como índice <= Teams: contradice que Team sea una etiqueta de texto [E, S, C].
      i  Claves de raíz limitadas a las globales y a IDs de actividad: E admite claves extra. Las
         claves desconocidas se permiten; los campos conocidos fuera de nivel los rechaza
         campos_fuera_de_nivel.
      k  El camino crítico cabe en la capacidad del periodo: es una heurística de planificación.
      l  Mezclar los dos formatos de precedencia: no documentada.
    """
    violations = check_configuration(engine.data, batch_object, previous_config)
    return (len(violations) == 0, [v.to_dict() for v in violations])


def find_unresolved_routes(config: Dict[str, Any], batch_object: ModificationBatch) -> List[Dict[str, Any]]:
    """
    Rutas del batch que el engine no puede resolver, comprobadas antes de aplicarlo. Se reproduce
    el batch instrucción a instrucción sobre una copia con PetriConfigEngine.apply_batch (mismo
    estado final que aplicarlo entero) y se anotan:
      engine_error         apply_batch informa de un error en la instrucción (ruta intermedia
                           inexistente, índice fuera de rango, APPEND sobre algo que no es lista)
      delete_missing       DELETE de una clave que no existe (apply_batch lo ignora en silencio)
      remove_list_missing  REMOVE_ITEM sobre una lista que no existe (idem)
    Un REMOVE_ITEM cuya lista existe pero no contiene el valor resuelve su ruta y no cuenta.
    """
    from input_agent.src.PetriNetConfig import PetriConfigEngine

    engine = PetriConfigEngine(config)
    unresolved = []
    for position, instr in enumerate(batch_object.instructions):
        node, keys = engine.data, instr.path.split(".")
        for key in keys[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
        key = keys[-1]
        kind = None
        if instr.operation.value == "DELETE" and not (isinstance(node, dict) and key in node):
            kind = "delete_missing"
        elif instr.operation.value == "REMOVE_ITEM" and not (isinstance(node, dict) and isinstance(node.get(key), list)):
            kind = "remove_list_missing"
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            engine.apply_batch(ModificationBatch(thought_process="", instructions=[instr]))
        message = printed.getvalue().strip()
        if message:
            kind = "engine_error"
        if kind:
            unresolved.append({"position": position, "operation": instr.operation.value, "path": instr.path, "kind": kind, "message": message})
    return unresolved


def retrieve_context_data(llm, query, engine):
    """
    1. Llama al LLM con CONTEXT_PROMPT.
    2. Ejecuta los GETs sobre el engine.
    3. Devuelve una cadena de texto formateada con los resultados.
    """
    print(f"{Colors.CYAN}🔍 Buscando contexto necesario...{Colors.RESET}")
    context_plan_json = llm.llm(CONTEXT_PROMPT, query)
    batch = ModificationBatch(**context_plan_json)
    instructions = batch.instructions
    
    results_text = ""
    for item in instructions:
        path = item.path
        val = engine.get_value(path)
        # Formateamos para que el LLM lo entienda bien
        entry = f"- Path: '{path}' | Current Value: {val}"
        results_text += entry + "\n"
    
    return results_text


# ============== KPI OPTIMIZATION TOOLS ==============

def kpi_orchestrator(query: str, llm_service) -> dict:
    """
    Orquesta las llamadas a múltiples agentes especializados para extraer 
    parámetros de optimización de KPI desde una consulta en lenguaje natural.
    
    Args:
        query: Consulta del usuario en lenguaje natural
        llm_service: Servicio LLM para realizar las llamadas
    
    Returns:
        dict: Diccionario con los parámetros de KPI extraídos (sin valores None)
    """
    from input_agent.src.prompts import (
        AVAILABILITY_AGENT_PROMPT,
        REQUIREMENTS_AGENT_PROMPT,
        COST_AGENT_PROMPT,
        BOUNDARIES_AGENT_PROMPT,
        ENVIRONMENT_AGENT_PROMPT
    )
    from input_agent.src.models import (
        AvailabilityOutput,
        RequirementsOutput,
        CostOutput,
        BoundariesOutput,
        EnvironmentOutput,
        OptimizerGlobalConfig
    )
    
    print(f"\n{Colors.CYAN}--- KPI ORCHESTRATOR: Analizando '{query}' ---{Colors.RESET}")
    
    # Ejecutar agentes especializados en paralelo (simulado)
    raw_avail = llm_service.llm(AVAILABILITY_AGENT_PROMPT, query)
    avail_obj = AvailabilityOutput(**raw_avail)
    
    raw_req = llm_service.llm(REQUIREMENTS_AGENT_PROMPT, query)
    req_obj = RequirementsOutput(**raw_req)
    
    raw_cost = llm_service.llm(COST_AGENT_PROMPT, query)
    cost_obj = CostOutput(**raw_cost)
    
    raw_bounds = llm_service.llm(BOUNDARIES_AGENT_PROMPT, query)
    bounds_obj = BoundariesOutput(**raw_bounds)
    
    raw_env = llm_service.llm(ENVIRONMENT_AGENT_PROMPT, query)
    env_obj = EnvironmentOutput(**raw_env)
    
    # Consolidar resultados
    master_config = OptimizerGlobalConfig(
        availability=avail_obj,
        requirements=req_obj,
        cost=cost_obj,
        boundaries=bounds_obj,
        environment=env_obj
    )
    
    # Obtener solo los cambios activos (sin None)
    active_changes = master_config.get_active_updates()
    
    print(f"{Colors.GREEN}Cambios detectados: {len(active_changes)} variables.{Colors.RESET}")
    return active_changes