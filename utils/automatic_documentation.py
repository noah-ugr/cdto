"""
Extractor de índices (i, j) desde inputs de estructura de actividades y tareas.

Este módulo proporciona funciones para convertir identificadores legibles
(A001, T002, etc.) a índices numéricos, facilitando la generación parametrizada
de redes de Petri.

Precedencias: taskCode y activityCode nombran lo que su dueño precede, que es lo que ejecuta el
motor (utils/mapping_utils.py las copia en Order_Before/Activity_Order_Before, y la red las lee
como "el dueño antes que cada entrada"). Con S_0, A001.T003 precedes T001 and T002, y A002
precedes A001.
"""

from typing import Dict, List, Tuple, Optional


def _join_ids(ids: List[str]) -> str:
    """'T001', 'T001 and T002', 'T001, T002 and T003'."""
    ids = list(ids)
    if len(ids) <= 1:
        return "".join(ids)
    return f"{', '.join(ids[:-1])} and {ids[-1]}"


def extract_activity_task_indices(input_data: Dict) -> Dict[int, List[int]]:
    """
    Extrae los índices (i, j) de actividades y tareas del input.
    
    Convierte identificadores como "A001", "A002" a índices numéricos (1, 2, ...)
    y "T001", "T002" a índices numéricos (1, 2, ...).
    
    Args:
        input_data (Dict): Diccionario con estructura de actividades y tareas
        
    Returns:
        Dict[int, List[int]]: Mapeo {i: [j1, j2, ...]} donde:
                              - i es el índice de actividad (1-based)
                              - [j1, j2, ...] es lista de índices de tareas (1-based)
                              
    Ejemplo:
        >>> input_data = {
        ...     "A001": {"tasks": {"T001": {...}, "T003": {...}}, ...},
        ...     "A002": {"tasks": {"T001": {...}, "T002": {...}}, ...}
        ... }
        >>> extract_activity_task_indices(input_data)
        {1: [1, 3], 2: [1, 2]}
    """
    global_keys = {"runId", "Teams", "Simulation_period"}
    activity_task_mapping = {}
    
    for key, value in input_data.items():
        # Ignorar parámetros globales
        if key in global_keys:
            continue
        
        # Verificar que sea una actividad (contiene "tasks")
        if isinstance(value, dict) and "tasks" in value:
            try:
                # Extraer índice numérico: "A001" -> 1, "A042" -> 42
                activity_idx = int(key[1:])
                
                # Extraer índices de tareas
                task_indices = []
                for task_key in value["tasks"].keys():
                    try:
                        # Extraer índice numérico: "T001" -> 1, "T042" -> 42
                        task_idx = int(task_key[1:])
                        task_indices.append(task_idx)
                    except (ValueError, IndexError):
                        # Tareas con formato no estándar, ignorar
                        continue
                
                activity_task_mapping[activity_idx] = sorted(task_indices)
            except (ValueError, IndexError, KeyError):
                # Actividades con formato no estándar, ignorar
                continue
    
    return activity_task_mapping


def extract_with_codes(input_data: Dict) -> Dict[str, Dict[str, List[str]]]:
    """
    Extrae actividades y tareas preservando los códigos originales.
    
    Args:
        input_data (Dict): Diccionario con estructura de actividades y tareas
        
    Returns:
        Dict[str, Dict[str, List[str]]]: Estructura {activity_code: {task_codes}}
                              
    Ejemplo:
        >>> extract_with_codes(input_data)
        {'A001': ['T001', 'T003'], 'A002': ['T001', 'T002']}
    """
    global_keys = {"runId", "Teams", "Simulation_period"}
    activity_task_mapping = {}
    
    for key, value in input_data.items():
        if key in global_keys:
            continue
        
        if isinstance(value, dict) and "tasks" in value:
            task_codes = list(value["tasks"].keys())
            activity_task_mapping[key] = sorted(task_codes)
    
    return activity_task_mapping

def create_index_registry(input_data: Dict) -> Dict:
    """
    Crea un registro completo de índices con múltiples formatos.
    
    Proporciona un diccionario consolidado con todas las opciones de indexación
    para facilitar la conversión entre formatos.
    
    Args:
        input_data (Dict): Diccionario con estructura de actividades y tareas
        
    Returns:
        Dict: Registro con las siguientes claves:
              - 'numeric': {i: [j1, j2, ...]} con índices extraídos de códigos
              - 'codes': {activity_code: [task_codes]}
              - 'sequential': {activity_code: seq_i, (activity_code, task_code): (seq_i, seq_j)}
              - 'reverse_numeric': {code: i} mapeos inversos para actividades
              - 'task_reverse_numeric': {(activity_i, code): j} mapeos inversos para tareas
    """
    numeric = extract_activity_task_indices(input_data)
    codes = extract_with_codes(input_data)

    
    return {
        'numeric': numeric,
        'codes': codes
    }


def generate_petri_net_documentation(input_data: Dict) -> str:
    """
    Genera la documentación completa de la red de Petri basada en el input específico.
    
    Crea un markdown con todos los elementos de la red (lugares, transiciones, arcos)
    personalizados con los ÍNDICES REALES del input (expandiendo {i} y {j}).
    
    Args:
        input_data (Dict): Input con estructura de actividades y tareas
        
    Returns:
        str: Documentación markdown completa generada dinámicamente con índices expandidos
    """
    registry = create_index_registry(input_data)
    activity_indices = registry['numeric']
    
    # Construir lista de actividades y tareas para iteración
    activities = []
    for i in sorted(activity_indices.keys()):
        tasks = activity_indices[i]
        activities.append((i, tasks))
    
    # Función auxiliar para generar TODOS los lugares específicos por actividad
    def generate_all_places():
        lines = []
        lines.append("### Per-Activity Places\n")
        for i, tasks in activities:
            lines.append(f"\n**Activity {i} (A{str(i).zfill(3)})**:")
            lines.append(f"- $p1{i}$: activity ready to start.")
            lines.append(f"- $p02{i}$: activity in the task loop state.")
            lines.append(f"- $p8{i}$: activity completion place.")
            lines.append(f"- $p00{i}$: initial place for activity {i}.")
            lines.append(f"- $p{i}0$: initial state within activity {i} subnet.")
        return "\n".join(lines)
    
    # Función para generar TODOS los lugares de tarea
    def generate_all_task_places():
        lines = []
        lines.append("### Per-Task Places\n")
        for i, tasks in activities:
            lines.append(f"\n**Activity {i}**:")
            for j in tasks:
                lines.append(f"- $p7{j}{i}$: internal task place for task {j} in activity {i}.")
        return "\n".join(lines)
    
    # Función para generar TODAS las transiciones por actividad
    def generate_all_transitions():
        lines = []
        lines.append("### Activity-Level Transitions\n")
        for i, tasks in activities:
            lines.append(f"\n**Activity {i}**:")
            lines.append(f"- $t{i}0$: activation of activity {i}.")
            lines.append(f"- $t{i}1$: entry into the task loop.")
            lines.append(f"- $t{i}2$: completion and return to $p{i}0$.")
            lines.append(f"- $t0006{i}$: maintenance loop transition.")
            lines.append(f"- $t0008{i}$: completion transition feeding $p8{i}$ and buffer places.")
        return "\n".join(lines)
    
    # Función para generar TODAS las transiciones de tareas
    def generate_all_task_transitions():
        lines = []
        lines.append("### Task-Level Transitions\n")
        for i, tasks in activities:
            lines.append(f"\n**Activity {i}**:")
            for j in tasks:
                lines.append(f"- $t0007{j}{i}$: execution of task {j} in activity {i}.")
        return "\n".join(lines)
    
    # Función para TODOS los flujos de actividad
    def generate_all_activity_flows():
        lines = []
        lines.append("### Activity Flow Arcs (Detailed)\n")
        for i, tasks in activities:
            flow = f"p00{i} \\rightarrow t00{i} \\rightarrow p1{i} \\rightarrow t{i}1 \\rightarrow p02{i} \\rightarrow t{i}2 \\rightarrow p{i}0"
            lines.append(f"\n**Activity {i}**:\n$$\n{flow}\n$$")
        return "\n".join(lines)
    
    # Función para TODOS los flujos de tareas
    def generate_all_task_flows():
        lines = []
        lines.append("### Task Flow Arcs (Detailed)\n")
        for i, tasks in activities:
            for j in tasks:
                lines.append(f"\n**Task {j} in Activity {i}**:\n$$\np02{i} \\leftrightarrow t0007{j}{i} \\leftrightarrow p7{j}{i}\n$$")
        return "\n".join(lines)
    
    # Función para generar tabla de resumen de configuración
    def generate_config_summary():
        lines = ["| Activity | Tasks | T_period | T_wait | Start_disp | Team |"]
        lines.append("|----------|-------|----------|--------|-----------|------|")
        
        global_keys = {"runId", "Teams", "Simulation_period"}
        for key, value in input_data.items():
            if key in global_keys:
                continue
            if isinstance(value, dict) and "tasks" in value:
                task_count = len(value.get("tasks", {}))
                t_period = value.get("T_period", "N/A")
                t_wait = value.get("T_wait", "N/A")
                start_disp = value.get("Start_disp", "N/A")
                team = value.get("Team", "N/A")
                lines.append(f"| {key} | {task_count} | {t_period} | {t_wait} | {start_disp} | {team} |")
        
        return "\n".join(lines)
    
    # Función para generar tabla de tareas
    def generate_tasks_summary():
        lines = ["| Activity | Task | Duration | Requires_Shutdown | Precedes |"]
        lines.append("|----------|------|----------|------------------|----------|")
        
        global_keys = {"runId", "Teams", "Simulation_period"}
        for key, value in input_data.items():
            if key in global_keys:
                continue
            if isinstance(value, dict) and "tasks" in value:
                tasks = value.get("tasks", {})
                for task_name, task_data in tasks.items():
                    duration = task_data.get("Duration", "N/A")
                    requires_shutdown = task_data.get("Requires_Shutdown", False)
                    precedes = ", ".join(task_data.get("taskCode", [])) if task_data.get("taskDependency") else "None"
                    lines.append(f"| {key} | {task_name} | {duration} | {requires_shutdown} | {precedes} |")
        
        return "\n".join(lines)
    
    # Construir documento markdown completo
    markdown = f"""# Documentación de Red de Petri - Configuración Específica

## Resumen de la Configuración

### Parámetros Globales

- **Simulation Period**: {input_data.get('Simulation_period', 'N/A')} horas
- **Teams Available**: {input_data.get('Teams', 'N/A')}
- **Run ID**: {input_data.get('runId', 'N/A')}

### Actividades y Tareas

{generate_config_summary()}

### Detalles de Tareas

{generate_tasks_summary()}

---

## Configuración de Lugares

### Lugares Genéricos

- $p3$: team-capacity pool.
- $p4$: maintenance lock / allocation place.
- $p5$: work-state indicator.
- $p6$: break-state indicator.
- $p0$: global "system operational" place.

{generate_all_places()}

{generate_all_task_places()}

### Buffer Places

Para comunicación inter-actividad:
"""
    
    for i in sorted(activity_indices.keys()):
        markdown += f"\n- `pbuff{i}`: buffer place for activity A{str(i).zfill(3)}."
    
    markdown += f"""

### Initial Markings

"""
    
    for i, tasks in activities:
        markdown += f"- $p00{i} = 1$: initial marking for activity {i}.\n"
    
    markdown += f"""
- $p0 = 1$: global operational state.
- $p5 = 1$: initially in work state.

---

## Configuración de Transiciones

### Atomic (Global) Transitions

- $t3$: allocation of workers (team allocation).
- $t4$: transition from break to work state.
- $t5$: transition from work to break state.
- $t9$: global reset transition.

{generate_all_transitions()}

{generate_all_task_transitions()}

### Tabla Consolidada de Transiciones

| Transition | Activity | Meaning |
|----------|----------|---------|
"""
    
    for i, tasks in activities:
        markdown += f"| $t00{i}$ | {i} | Activate activity {i} |\n"
        markdown += f"| $t{i}0$ | {i} | Entry to activity {i} subnet |\n"
        markdown += f"| $t{i}1$ | {i} | Enter task loop in activity {i} |\n"
        markdown += f"| $t{i}2$ | {i} | Complete activity {i} |\n"
        markdown += f"| $t0006{i}$ | {i} | Maintenance loop in activity {i} |\n"
        markdown += f"| $t0008{i}$ | {i} | Completion (feeds pbuff{i}) |\n"
        for j in tasks:
            markdown += f"| $t0007{j}{i}$ | {i} | Execute task {j} |\n"

    markdown += f"""

---

## Configuración de Arcos

{generate_all_activity_flows()}

{generate_all_task_flows()}

### Task Flow with Team Weights

Para cada tarea $j$ en actividad $i$, los arcos desde $p3$ son ponderados según los requisitos específicos del input.

### Maintenance and System Behavior

- Ciclo de trabajo/descanso: $p5 \\rightarrow t5 \\rightarrow p6 \\rightarrow t4 \\rightarrow p5$
- Reset global $t9$: reinicia $p3$, $p4$, $p6$ e inicializa $p5$ y todos los $p{i}0$

### Precedence Constraints (Task-Level)

"""
    
    for key, value in input_data.items():
        if isinstance(value, dict) and "tasks" in value:
            tasks = value.get("tasks", {})
            for task_name, task_data in tasks.items():
                if task_data.get("taskDependency"):
                    successors = task_data.get("taskCode", [])
                    task_idx = int(task_name[1:])
                    act_idx = int(key[1:])
                    markdown += f"\n**{key}.{task_name}** precedes {_join_ids(successors)}\n"
                    for successor in successors:
                        succ_idx = int(successor[1:])
                        markdown += (
                            f"- Arc: $p7{task_idx}{act_idx} \\rightarrow t0007{succ_idx}{act_idx}$ "
                            f"({successor} runs only after {task_name} has run)\n"
                        )
    
    markdown += f"""

### Precedence Constraints (Activity-Level)

"""
    
    for key, value in input_data.items():
        if isinstance(value, dict) and "tasks" in value:
            if value.get("activityDependency"):
                act_idx = int(key[1:])
                successors = value.get("activityCode", [])
                markdown += f"\n**{key}** precedes {_join_ids(successors)}\n"
                for successor in successors:
                    succ_idx = int(successor[1:])
                    markdown += (
                        f"- Inhibitor arc: $p02{act_idx} \\rightarrow t{succ_idx}1$ "
                        f"(activity {succ_idx} cannot enter its task loop while activity {act_idx} is in its task loop)\n"
                    )
                    markdown += (
                        f"- Arc: $pbuff{act_idx} \\rightarrow t{succ_idx}1$ "
                        f"(activity {succ_idx} enters its task loop with the token activity {act_idx} leaves when it completes its tasks)\n"
                    )
    
    markdown += f"""

### Buffer Communication Between Activities

"""
    
    for i in sorted(activity_indices.keys()):
        markdown += f"- $t0008{i} \\rightarrow pbuff{i}$: produces token when activity {i} completes.\n"
    
    markdown += f"""

### Arc Enrichment Metadata

All arcs are enriched with:
- **ActivityID**: Activity identifier (A001, A002, etc.)
- **TaskID**: Task identifier (T001, T002, etc.)
- **Team**: Team assigned
- **T_period**: Repetition period
- **T_wait**: Waiting time
- **Start_disp**: Start displacement

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Activities | {len(activity_indices)} |
| Total Tasks | {sum(len(tasks) for _, tasks in activities)} |
| Activities that precede others | {sum(1 for key, value in input_data.items() if isinstance(value, dict) and value.get('activityDependency'))} |
| Buffer Places | {len(activity_indices)} |
| Generic Places | 5 |
"""
    
    return markdown

def generate_petri_net_documentation_txt(input_data: Dict) -> str:
    """
    Genera la documentación de la red de Petri en formato TXT plano (Index Cards).
    Diseñado específicamente para ser ingerido por un Chunker de RAG separando por '\n---\n'.
    """
    registry = create_index_registry(input_data)
    activity_indices = registry['numeric']
    
    activities = []
    for i in sorted(activity_indices.keys()):
        tasks = activity_indices[i]
        activities.append((i, tasks))
        
    lines = []

    # ==========================================
    # 1. GLOBAL CONFIGURATION
    # ==========================================
    lines.append("ID: GLOBAL_CONFIG")
    lines.append("TYPE: Metadata")
    lines.append(f"SIMULATION_PERIOD: {input_data.get('Simulation_period', 'N/A')} hours")
    lines.append(f"TEAMS_AVAILABLE: {input_data.get('Teams', 'N/A')}")
    lines.append(f"RUN_ID: {input_data.get('runId', 'N/A')}")
    lines.append("---")

    # ==========================================
    # 2. GENERIC PLACES
    # ==========================================
    generic_places = {
        "p3": "team-capacity pool.",
        "p4": "maintenance lock / allocation place.",
        "p5": "work-state indicator.",
        "p6": "break-state indicator.",
        "p0": "global system operational place."
    }
    for pid, desc in generic_places.items():
        lines.append(f"ID: {pid}")
        lines.append("TYPE: Generic Place")
        lines.append(f"MEANING: {desc}")
        if pid == "p0" or pid == "p5":
            lines.append("INITIAL_MARKING: 1")
        lines.append("---")

    # ==========================================
    # 3. ACTIVITY & TASK PLACES
    # ==========================================
    for i, tasks in activities:
        act_id = f"A{str(i).zfill(3)}"
        
        # Activity Places
        act_places = {
            f"p1{i}": "activity ready to start.",
            f"p02{i}": "activity in the task loop state.",
            f"p8{i}": "activity completion place.",
            f"p00{i}": f"initial place for activity {i}. INITIAL_MARKING: 1",
            f"p{i}0": f"initial state within activity {i} subnet.",
            f"pbuff{i}": f"buffer place for activity {act_id}."
        }
        for pid, desc in act_places.items():
            lines.append(f"ID: {pid}")
            lines.append("TYPE: Activity Place")
            lines.append(f"ACTIVITY: {act_id}")
            lines.append(f"MEANING: {desc}")
            lines.append("---")
            
        # Task Places
        for j in tasks:
            lines.append(f"ID: p7{j}{i}")
            lines.append("TYPE: Task Place")
            lines.append(f"ACTIVITY: {act_id}")
            lines.append(f"TASK: T{str(j).zfill(3)}")
            lines.append(f"MEANING: internal task place for task {j} in activity {i}.")
            lines.append("---")

    # ==========================================
    # 4. ATOMIC TRANSITIONS
    # ==========================================
    atomic_transitions = {
        "t3": "allocation of workers (team allocation).",
        "t4": "transition from break to work state.",
        "t5": "transition from work to break state.",
        "t9": "global reset transition."
    }
    for tid, desc in atomic_transitions.items():
        lines.append(f"ID: {tid}")
        lines.append("TYPE: Atomic Transition")
        lines.append(f"MEANING: {desc}")
        lines.append("---")

    # ==========================================
    # 5. ACTIVITY & TASK TRANSITIONS
    # ==========================================
    for i, tasks in activities:
        act_id = f"A{str(i).zfill(3)}"
        
        # Activity Transitions
        act_trans = {
            f"t00{i}": f"activate activity {i}",
            f"t{i}0": f"activation of activity {i} subnet.",
            f"t{i}1": "entry into the task loop.",
            f"t{i}2": f"completion and return to p{i}0.",
            f"t0006{i}": "maintenance loop transition.",
            f"t0008{i}": f"completion transition feeding p8{i} and pbuff{i}."
        }
        for tid, desc in act_trans.items():
            lines.append(f"ID: {tid}")
            lines.append("TYPE: Activity Transition")
            lines.append(f"ACTIVITY: {act_id}")
            lines.append(f"MEANING: {desc}")
            lines.append("---")
            
        # Task Transitions
        for j in tasks:
            lines.append(f"ID: t0007{j}{i}")
            lines.append("TYPE: Task Transition")
            lines.append(f"ACTIVITY: {act_id}")
            lines.append(f"TASK: T{str(j).zfill(3)}")
            lines.append(f"MEANING: execution of task {j} in activity {i}.")
            lines.append("---")

    # ==========================================
    # 6. ARCS & FLOWS
    # ==========================================
    for i, tasks in activities:
        act_id = f"A{str(i).zfill(3)}"
        
        # Activity Flow
        lines.append(f"ID: FLOW_ACT_{i}")
        lines.append("TYPE: Activity Flow Path")
        lines.append(f"ACTIVITY: {act_id}")
        lines.append(f"PATH: p00{i} -> t00{i} -> p1{i} -> t{i}1 -> p02{i} -> t{i}2 -> p{i}0")
        lines.append("---")
        
        # Task Flows
        for j in tasks:
            lines.append(f"ID: FLOW_TSK_{j}_{i}")
            lines.append("TYPE: Task Flow Path")
            lines.append(f"ACTIVITY: {act_id}")
            lines.append(f"TASK: T{str(j).zfill(3)}")
            lines.append(f"PATH: p02{i} <-> t0007{j}{i} <-> p7{j}{i}")
            lines.append("---")

    # Maintenance Cycle
    lines.append("ID: FLOW_MAINTENANCE")
    lines.append("TYPE: System Flow Path")
    lines.append("PATH: p5 -> t5 -> p6 -> t4 -> p5")
    lines.append("---")

    # ==========================================
    # 7. PRECEDENCE CONSTRAINTS (the owner of taskCode/activityCode precedes each entry)
    # ==========================================
    for key, value in input_data.items():
        if isinstance(value, dict) and "tasks" in value:
            act_idx = int(key[1:])
            
            # Task level: each task in taskCode runs only after its owner has run
            tasks = value.get("tasks", {})
            for task_name, task_data in tasks.items():
                if task_data.get("taskDependency"):
                    successors = task_data.get("taskCode", [])
                    task_idx = int(task_name[1:])
                    for successor in successors:
                        succ_idx = int(successor[1:])
                        lines.append(f"ID: PREC_{key}_{task_name}_BEFORE_{successor}")
                        lines.append("TYPE: Precedence Arc")
                        lines.append(f"ACTIVITY: {key}")
                        lines.append(f"FROM: p7{task_idx}{act_idx}")
                        lines.append(f"TO: t0007{succ_idx}{act_idx}")
                        lines.append(f"MEANING: {key}.{task_name} precedes {successor}: {successor} runs only after {task_name} has run.")
                        lines.append("---")
                        
            # Activity level: each activity in activityCode waits for its owner
            if value.get("activityDependency"):
                successors = value.get("activityCode", [])
                for successor in successors:
                    succ_idx = int(successor[1:])
                    lines.append(f"ID: PREC_{key}_BEFORE_{successor}")
                    lines.append("TYPE: Inhibitor Arc")
                    lines.append(f"FROM: p02{act_idx}")
                    lines.append(f"TO: t{succ_idx}1")
                    lines.append(f"MEANING: {key} precedes {successor}: {successor} cannot enter its task loop while {key} is in its task loop.")
                    lines.append("---")
                    lines.append(f"ID: BUFF_{key}_BEFORE_{successor}")
                    lines.append("TYPE: Precedence Arc")
                    lines.append(f"FROM: pbuff{act_idx}")
                    lines.append(f"TO: t{succ_idx}1")
                    lines.append(f"MEANING: {key} precedes {successor}: {successor} enters its task loop with the token {key} leaves in pbuff{act_idx} when it completes its tasks.")
                    lines.append("---")

    return "\n".join(lines)

if __name__ == "__main__":
    # Ejemplo de uso
    sample_input = {
        "runId": 25,
        "Teams": 1,
        "Simulation_period": 2000,
        "A001": {
            "tasks": {
                "T001": {"Duration": 10, "Requires_Shutdown": False},
                "T002": {"Duration": 30, "Requires_Shutdown": True},
                "T003": {"Duration": 40, "Requires_Shutdown": False, "taskDependency": True, "taskCode": ["T001", "T002"]}
            },
            "T_period": 480,
            "T_wait": 2,
            "Start_disp": 3,
            "Team": "TeamA",
            "Team members": 2,
            "Shift_duration": 8
        },
        "A002": {
            "tasks": {
                "T001": {"Duration": 80, "Requires_Shutdown": False},
                "T002": {"Duration": 100, "Requires_Shutdown": False, "taskDependency": True, "taskCode": ["T001"]},
                "T003": {"Duration": 60, "Requires_Shutdown": True, "taskDependency": True, "taskCode": ["T001"]},
                "T004": {"Duration": 10, "Requires_Shutdown": False, "taskDependency": True, "taskCode": ["T002", "T003"]}
            },
            "T_period": 720,
            "T_wait": 4,
            "Start_disp": 1,
            "Team": "TeamA",
            "Team members": 2,
            "Shift_duration": 8,
            "activityDependency": True,
            "activityCode": ["A001"]
        }
    }
    
    print("=== Índices numéricos (1-based) ===")
    print(extract_activity_task_indices(sample_input))
    
    print("\n=== Con códigos originales ===")
    print(extract_with_codes(sample_input))
    
    print("\n=== Registro completo ===")
    registry = create_index_registry(sample_input)
    for key, value in registry.items():
        print(f"{key}: {value}")
    
    print("\n\n=== DOCUMENTACIÓN GENERADA (primeras 100 líneas) ===")
    doc = generate_petri_net_documentation(sample_input)
    lines = doc.split('\n')
    for line in lines:
        print(line)
