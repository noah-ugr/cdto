"""
Author: Noah Masegosa Caceres 
Center: @ugr

Objective: Motor para aplicar cambios en la configuración del Petri Net.

This module provides a comprehensive engine for managing and modifying Petri Net configurations
stored as JSON structures. It supports CRUD operations, structural reindexing with reference
updates, read-only value retrieval, and delta computation for change tracking and xAI integration.
"""

from typing import Any, Dict, List, Tuple, Union
import copy
from input_agent.src.models import ModificationBatch, OpType

class PetriConfigEngine:
    """
    Motor de aplicación de cambios sobre la configuración JSON.
    
    Esta clase actúa como un intérprete de las instrucciones generadas por el LLM,
    navegando por la estructura anidada del JSON y aplicando operaciones CRUD de forma segura.
    """

    def __init__(self, json_data: Dict[str, Any]):
        """
        Inicializa el motor con los datos base.

        Args:
            json_data (Dict[str, Any]): El diccionario JSON original.
        """
        self.data = copy.deepcopy(json_data)
        self.original_data = copy.deepcopy(json_data)

    def _navigate_to_parent(self, path_str: str) -> Tuple[Union[Dict, List], str]:
        """
        Navega a través del JSON usando una ruta de puntos ("A.B.C") para encontrar el contenedor padre.

        Args:
            path_str (str): Ruta completa (ej: "A001.tasks.0").

        Returns:
            Tuple[Union[Dict, List], str]: 
                - Referencia al objeto contenedor (padre).
                - La clave o índice final dentro de ese contenedor.

        Raises:
            KeyError: Si alguna parte intermedia de la ruta no existe.
        """
        keys = path_str.split('.')
        current = self.data
        
        # Iteramos hasta el penúltimo elemento para situarnos en el padre del objetivo
        for key in keys[:-1]:
            # Nota: Aquí se asume navegación por claves de string. 
            if isinstance(current, dict) and key not in current:
                raise KeyError(f"La ruta '{key}' no existe en {path_str}")
            
            # Avanzamos un nivel en la profundidad del JSON
            current = current[key]
            
        return current, keys[-1]

    def apply_batch(self, batch: ModificationBatch) -> Dict[str, Any]:
        """
        Ejecuta secuencialmente una lista de instrucciones sobre la copia local de los datos.

        Args:
            batch (ModificationBatch): El objeto con las instrucciones y el razonamiento.

        Returns:
            Dict[str, Any]: El estado final del JSON modificado.
        """
        
        for instr in batch.instructions:
            try:
                # Obtenemos la referencia al objeto que contiene el dato a modificar
                parent, key = self._navigate_to_parent(instr.path)
                
                # --- Operación SET ---
                if instr.operation == OpType.SET:
                    # Si el padre es una lista, la clave debe interpretarse como índice entero
                    if isinstance(parent, list):
                        idx = int(key)
                        if idx < len(parent):
                            parent[idx] = instr.value
                        else:
                            print(f"Error: Índice {idx} fuera de rango en {instr.path}")
                    else:
                        # Si es diccionario, asignación directa
                        parent[key] = instr.value

                # --- Operación DELETE ---
                elif instr.operation == OpType.DELETE:
                    # Eliminamos la clave del diccionario
                    if isinstance(parent, dict) and key in parent:
                        del parent[key]

                # --- Operación APPEND ---
                elif instr.operation == OpType.APPEND:
                    # Si la lista no existe, la creamos (comportamiento upsert)
                    if isinstance(parent, dict) and key not in parent:
                        parent[key] = []
                    
                    # Verificamos que el objetivo sea realmente una lista
                    if isinstance(parent[key], list):
                        parent[key].append(instr.value)
                    else:
                        print(f"Error: {instr.path} no es una lista, no se puede hacer APPEND.")

                # --- Operación REMOVE_ITEM ---
                elif instr.operation == OpType.REMOVE_ITEM:
                    # Elimina un valor por contenido (no por índice)
                    if key in parent and isinstance(parent[key], list):
                        if instr.value in parent[key]:
                            parent[key].remove(instr.value)
            
            except Exception as e:
                print(f"Error ejecutando {instr.operation} en {instr.path}: {e}")

        return self.data
    
    def get_value(self, path_str: str) -> str:
        """
        Recupera el valor de una ruta específica de forma segura (Read-Only).
        Útil para que el Context Agent verifique el estado actual antes de decidir.

        Args:
            path_str (str): Ruta completa (ej: "A001.tasks.T001.Duration").

        Returns:
            Any: El valor encontrado (int, str, list, dict) o None si no existe.
        """

        path_str = path_str
        keys = path_str.split('.')
        current = self.data

        try:
            for key in keys:
                if isinstance(current, list):
                    # Intentamos convertir la key a indice entero
                    idx = int(key)
                    current = current[idx]
                elif isinstance(current, dict):
                    current = current[key]
                else:
                    # Intentamos acceder a una propiedad de algo que no es contenedor
                    return None
            
            return current

        except (KeyError, IndexError, ValueError):
            # Esto permite al Agente decir "No encontré ese dato".
            return None
    
    def reindex_structure(self):
        """
        Renumera los IDs temporales de Actividades y Tareas a su formato canónico (Axxx / Txxx) y
        ACTUALIZA REFERENCIAS.

        El Planner crea IDs temporales al insertar una entidad entre otras: el ID de la entidad
        anterior + "_new" (p. ej. "A002_new", "T001_new"). Esta función les da su ID canónico.

        Garantías:
        1. Renombrado en dos fases: primero se calcula el mapa completo {id_antiguo: id_nuevo} y
           después se reconstruye el contenedor, así que nunca se pisa una clave existente.
        2. Un mapa de renumeración de tareas por actividad: renumerar las tareas de una actividad
           no cambia las referencias de las demás.
        3. Se actualizan las referencias de las cuatro listas: Activity_Order_Before y activityCode
           (IDs de actividad) y Order_Before y taskCode (IDs de tarea de la misma actividad).

        Orden: cada ID temporal va justo después de su ID base (A002 < A002_new < A003) y los IDs
        canónicos posteriores se desplazan lo imprescindible para dejarle sitio. Solo se renumera
        si hay IDs temporales: no se rellenan huecos y una configuración sin IDs temporales queda
        intacta. Nunca se asigna un ID que alguna lista referencia sin que exista (una entidad
        borrada): esa referencia colgante se conserva para que el validador la detecte. Las claves
        que no son ni canónicas ni temporales no se tocan. Sin campos perdidos ni duplicados.

        Modifica self.data en el sitio y lo devuelve.
        """
        import re

        def referenced_ids(value):
            if isinstance(value, list):
                return {x for x in value if isinstance(x, str)}
            return {value} if isinstance(value, str) else set()

        def renumbering(keys, prefix, reserved):
            """Mapa {clave: clave canónica} de las claves canónicas y temporales; vacío si no hay
            ninguna temporal."""
            pattern = re.compile(rf"^{prefix}(\d{{3}})(_new\w*)?$")
            ordered = []
            for key in keys:
                match = pattern.match(str(key))
                if match:
                    ordered.append((int(match.group(1)), match.group(2) or "", key))
            if not any(suffix for _, suffix, _ in ordered):
                return {}
            mapping, previous = {}, 0
            for number, suffix, key in sorted(ordered):
                new_number = previous + 1 if suffix else max(previous + 1, number)
                while f"{prefix}{new_number:03d}" in reserved:
                    new_number += 1
                mapping[key] = f"{prefix}{new_number:03d}"
                previous = new_number
            return mapping

        def rebuild(container, mapping):
            """Segunda fase: reconstruye el dict con las claves renombradas en orden canónico, en la
            posición de la primera de ellas, sin tocar el resto de claves."""
            items = list(container.items())
            renamed = sorted(
                ((mapping[k], v) for k, v in items if k in mapping),
                key=lambda kv: int(kv[0][1:]),
            )
            rebuilt, placed = {}, False
            for key, value in items:
                if key not in mapping:
                    rebuilt[key] = value
                elif not placed:
                    rebuilt.update(renamed)
                    placed = True
            container.clear()
            container.update(rebuilt)

        def remap(value, changes):
            if isinstance(value, list):
                return [changes.get(x, x) if isinstance(x, str) else x for x in value]
            if isinstance(value, str):
                return changes.get(value, value)
            return value

        activities = [a for a in self.data.values() if isinstance(a, dict)]

        # Fase 1: mapas completos (actividades y, por separado, las tareas de cada actividad).
        activity_refs = set()
        for activity in activities:
            for field in ("Activity_Order_Before", "activityCode"):
                activity_refs |= referenced_ids(activity.get(field))
        activity_map = renumbering(
            self.data.keys(), "A", {r for r in activity_refs if r not in self.data}
        )

        task_maps = []
        for activity in activities:
            tasks = activity.get("tasks")
            if not isinstance(tasks, dict):
                continue
            task_refs = set()
            for task in tasks.values():
                if isinstance(task, dict):
                    for field in ("Order_Before", "taskCode"):
                        task_refs |= referenced_ids(task.get(field))
            task_map = renumbering(tasks.keys(), "T", {r for r in task_refs if r not in tasks})
            if task_map:
                task_maps.append((activity, task_map))

        if not activity_map and not task_maps:
            return self.data

        # Fase 2: reconstrucción y actualización de referencias.
        id_map = {"activities": {}, "tasks": {}}
        for activity, task_map in task_maps:
            changes = {k: v for k, v in task_map.items() if k != v}
            rebuild(activity["tasks"], task_map)
            for task in activity["tasks"].values():
                if isinstance(task, dict):
                    for field in ("Order_Before", "taskCode"):
                        if field in task:
                            task[field] = remap(task[field], changes)
            owner = next((k for k, v in self.data.items() if v is activity), "?")
            id_map["tasks"][owner] = changes

        if activity_map:
            changes = {k: v for k, v in activity_map.items() if k != v}
            rebuild(self.data, activity_map)
            for activity in activities:
                for field in ("Activity_Order_Before", "activityCode"):
                    if field in activity:
                        activity[field] = remap(activity[field], changes)
            id_map["activities"] = changes
            id_map["tasks"] = {changes.get(k, k): v for k, v in id_map["tasks"].items()}

        print(f"🔄 Reindexando referencias: {id_map}")
        return self.data

    def compute_delta(self, modified_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula la diferencia (delta) entre el JSON original y el modificado,
        incluyendo altas, cambios y eliminaciones.
        """

        delta = {
            "global_changes": {},
            "deleted_global": {},

            "new_activities": [],
            "deleted_activities": [],

            "new_tasks": {},
            "deleted_tasks": {},

            "activity_values": {},
            "task_values": {}
        }

        # -------------------------
        # 1) Cambios globales + bajas globales
        # -------------------------
        original_global_keys = {k for k in self.original_data.keys() if not k.startswith("A")}
        modified_global_keys = {k for k in modified_data.keys() if not k.startswith("A")}

        # Nuevos o modificados
        for key in modified_global_keys:
            original_value = self.original_data.get(key)
            modified_value = modified_data.get(key)
            if original_value != modified_value:
                delta["global_changes"][key] = self._compute_value_change(original_value, modified_value)

        # Eliminados
        for key in original_global_keys - modified_global_keys:
            delta["deleted_global"][key] = {"old": self.original_data[key], "new": None}

        # -------------------------
        # 2) Actividades nuevas/modificadas
        # -------------------------
        original_activities = {k for k in self.original_data.keys() if k.startswith("A")}
        modified_activities = {k for k in modified_data.keys() if k.startswith("A")}

        # Altas de actividad
        for a_key in modified_activities - original_activities:
            delta["new_activities"].append(a_key)

        # Bajas de actividad
        for a_key in original_activities - modified_activities:
            delta["deleted_activities"].append(a_key)

        # Comparación de actividades existentes en ambos
        for a_key in modified_activities & original_activities:
            a_data = modified_data.get(a_key, {})
            original_a_data = self.original_data.get(a_key, {})

            if not isinstance(a_data, dict) or not isinstance(original_a_data, dict):
                continue

            activity_param_changes = {}
            task_changes_for_activity = {}
            new_tasks_in_activity = []
            deleted_tasks_in_activity = []

            # ---- Campos de actividad (excepto "tasks"), incluyendo eliminados
            a_fields_mod = {k for k, v in a_data.items() if k != "tasks" and not isinstance(v, dict)}
            a_fields_org = {k for k, v in original_a_data.items() if k != "tasks" and not isinstance(v, dict)}
            for field in a_fields_mod | a_fields_org:
                old_val = original_a_data.get(field)
                new_val = a_data.get(field)
                if field in a_fields_org and field not in a_fields_mod:
                    activity_param_changes[field] = {"old": old_val, "new": None}
                elif old_val != new_val:
                    activity_param_changes[field] = self._compute_value_change(old_val, new_val)

            # ---- Tareas
            tasks_dict = a_data.get("tasks", {})
            original_tasks_dict = original_a_data.get("tasks", {})
            if not isinstance(tasks_dict, dict):
                tasks_dict = {}
            if not isinstance(original_tasks_dict, dict):
                original_tasks_dict = {}

            mod_task_ids = set(tasks_dict.keys())
            org_task_ids = set(original_tasks_dict.keys())

            # Nuevas tareas
            for t_key in mod_task_ids - org_task_ids:
                new_tasks_in_activity.append(t_key)

            # Tareas eliminadas
            for t_key in org_task_ids - mod_task_ids:
                deleted_tasks_in_activity.append(t_key)

            # Tareas existentes: comparar campos incluyendo eliminados
            for t_key in mod_task_ids & org_task_ids:
                t_data = tasks_dict.get(t_key, {})
                original_t_data = original_tasks_dict.get(t_key, {})
                if not isinstance(t_data, dict) or not isinstance(original_t_data, dict):
                    continue

                task_param_changes = {}
                all_fields = set(t_data.keys()) | set(original_t_data.keys())
                for field_key in all_fields:
                    old_val = original_t_data.get(field_key)
                    new_val = t_data.get(field_key)

                    if field_key in original_t_data and field_key not in t_data:
                        task_param_changes[field_key] = {"old": old_val, "new": None}
                    elif old_val != new_val:
                        task_param_changes[field_key] = self._compute_value_change(old_val, new_val)

                if task_param_changes:
                    task_changes_for_activity[t_key] = task_param_changes

            if activity_param_changes:
                delta["activity_values"][a_key] = activity_param_changes

            if new_tasks_in_activity:
                delta["new_tasks"][a_key] = new_tasks_in_activity

            if deleted_tasks_in_activity:
                delta["deleted_tasks"][a_key] = deleted_tasks_in_activity

            if task_changes_for_activity:
                delta["task_values"][a_key] = task_changes_for_activity

        return delta

    def _compute_value_change(self, old_val: Any, new_val: Any) -> Dict[str, Any]:
        """
        Calcula el cambio entre dos valores, incluyendo porcentaje si son números.

        Args:
            old_val: Valor original (puede ser None)
            new_val: Valor modificado

        Returns:
            Dict con "old", "new", y "change_percent" si aplica.
        """
        change_info = {"old": old_val, "new": new_val}
        
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            if old_val != 0:
                percent_change = ((new_val - old_val) / abs(old_val)) * 100
                change_info["change_percent"] = round(percent_change, 2)
            elif old_val == 0 and new_val != 0:
                change_info["change_percent"] = None
        
        return change_info