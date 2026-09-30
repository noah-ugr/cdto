"""
Dataset Generator para medir Accuracy vs Completeness.

Genera JSONs de COMPLEJIDAD FIJA con COMPLETENESS VARIABLE (1-15 instrucciones).
Las instrucciones pueden ser INDEPENDIENTES o DEPENDIENTES.

Por ejemplo:
- Completeness 1: 1 instrucción simple
- Completeness 5: 5 instrucciones (mixtas: independientes y dependientes)
- Completeness 15: 15 instrucciones coherentes

Estructura de output JSONL:
{
    "complexity_nodes": <int>,
    "activities_count": <int>,
    "tasks_per_act_count": <int>,
    "completeness": <int (1-15)>,
    "instruction_type": "mixed" | "independent" | "dependent",
    "json_base": <dict>,
    "instructions_technical": [<list of Instruction dicts>],
    "instructions_natural": <str (SINGLE humanized query)>,
    "json_gt": <dict (ground truth after applying all instructions)>
}
"""

import json
import random
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor

root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from input_agent.src.models import OpType, Instruction, ModificationBatch
from input_agent.src.PetriNetConfig import PetriConfigEngine
from input_agent.src.llm import LLMService


def pick_one(items):
    """Selecciona un elemento sin usar random.choice."""
    return items[random.randrange(len(items))]


def rand_bool(probability: float = 0.5) -> bool:
    """Genera booleanos usando probabilidad explícita."""
    return random.random() < probability


def generate_base_json(num_activities: int, tasks_per_act: int) -> Dict[str, Any]:
    """
    Genera un JSON sintético imitando la estructura exacta del PDF.
    Incluye los tres niveles: Global, Activity-Level y Task-Level.
    """
    base_json = {
        "runId": random.randint(1, 1000),
        "Teams": random.randint(1, 20),
        "Simulation_period": random.randint(480, 10080)
    }
    
    act_ids = [f"A{str(a).zfill(3)}" for a in range(1, num_activities + 1)]
    
    for a, act_id in enumerate(act_ids):
        act_data = {
            "tasks": {},
            "T_period": random.randint(240, 4320),
            "T_wait": random.randint(1, 48),
            "Start_disp": random.randint(1, 120),
            "Team": f"Team{chr(64+(a+1))}",              
            "Team members": random.randint(1, 12),
            "Shift_duration": random.randint(6, 14),
            "Activity_Order_Enforced": rand_bool(),
            "Activity_Order_Before": []
        }
        
        if a < num_activities - 1 and random.random() < 0.5:
            act_data["Activity_Order_Before"].append(act_ids[a + 1])
        
        task_ids = [f"T{str(t).zfill(3)}" for t in range(1, tasks_per_act + 1)]
        
        for t, task_id in enumerate(task_ids):
            task_data = {
                "Duration": random.randint(1, 48),
                "Requires_Shutdown": rand_bool(),
                "Cost_per_hour": random.randint(25, 500),
                "Order_Enforced": rand_bool(),
                "Order_Before": []                            
            }
            
            if t < tasks_per_act - 1:
                task_data["Order_Before"].append(task_ids[t + 1])
                if t < tasks_per_act - 2 and random.random() < 0.3:
                    task_data["Order_Before"].append(task_ids[t + 2])
                
            act_data["tasks"][task_id] = task_data
            
        base_json[act_id] = act_data
        
    return base_json


def generate_atomic_instruction(
    base_json: Dict[str, Any],
    instruction_type: str = "independent",
    blacklist: Set[str] = None
) -> Instruction:
    """
    Genera una instrucción atómica única sin duplicados.
    
    Args:
        base_json: JSON base
        instruction_type: "independent", "dependent_append", "dependent_remove"
        blacklist: Set de instrucciones ya generadas (como strings hash)
    
    Returns:
        Instruction única
    """
    if blacklist is None:
        blacklist = set()
    
    max_attempts = 100
    for attempt in range(max_attempts):
        instruction = _try_generate_instruction(base_json, instruction_type)
        instr_hash = _hash_instruction(instruction)
        
        if instr_hash not in blacklist:
            return instruction
    
    # Fallback: una instrucción simple válida
    return _fallback_instruction(base_json)


def _hash_instruction(instruction: Instruction) -> str:
    """Crea un hash único para la instrucción."""
    data = instruction.model_dump()
    return json.dumps(data, sort_keys=True)


def _detect_causality(instructions: List[Instruction]) -> str:
    """
    Detecta si las instrucciones tienen relaciones de causalidad.
    Heurística: si hay APPEND/REMOVE_ITEM, probablemente hay dependencias.
    """
    has_append = any(i.operation == OpType.APPEND for i in instructions)
    has_remove = any(i.operation == OpType.REMOVE_ITEM for i in instructions)
    has_sets = any(i.operation == OpType.SET for i in instructions)
    has_deletes = any(i.operation == OpType.DELETE for i in instructions)
    
    if (has_append or has_remove) and has_sets:
        return "MIXED (parametric changes + dependencies)"
    elif has_append or has_remove:
        return "DEPENDENT (mostly dependencies)"
    elif has_sets or has_deletes:
        return "INDEPENDENT (parametric changes only)"
    else:
        return "UNKNOWN"


def _fallback_natural_query(instructions: List[Instruction]) -> str:
    """
    Fallback si el LLM falla: genera una query simple pero completa.
    """
    queries = []
    for instr in instructions:
        op = instr.operation.value
        path = instr.path
        val = instr.value
        
        if op == "SET":
            queries.append(f"Pon {path} en {val}")
        elif op == "DELETE":
            queries.append(f"Borra {path}")
        elif op == "APPEND":
            queries.append(f"Añade {val} a {path}")
        elif op == "REMOVE_ITEM":
            queries.append(f"Quita {val} de {path}")
    
    return "; ".join(queries) + "."


def _try_generate_instruction(base_json: Dict[str, Any], instruction_type: str) -> Instruction:
    """Genera una instrucción aleatoria del tipo especificado."""
    act_ids = [k for k in base_json.keys() if k.startswith('A')]
    target_act = pick_one(act_ids)
    task_ids = list(base_json[target_act]["tasks"].keys())
    target_task = pick_one(task_ids)
    
    if instruction_type == "independent":
        # SET, DELETE operations sin dependencias
        op_choice = pick_one([OpType.SET, OpType.DELETE])
        
        if op_choice == OpType.SET:
            level_choice = pick_one(["Global", "Activity", "Task"])
            
            if level_choice == "Global":
                field = pick_one(["Teams", "Simulation_period", "runId"])
                if field == "Teams":
                    val = random.randint(1, 30)
                elif field == "Simulation_period":
                    val = random.randint(480, 17520)
                else:  # runId
                    val = random.randint(1, 10000)
                return Instruction(operation=OpType.SET, path=field, value=val)
                
            elif level_choice == "Activity":
                fields = {
                    "T_period": random.randint(120, 10080),
                    "T_wait": random.randint(1, 72),
                    "Start_disp": random.randint(1, 120),
                    "Team": pick_one(["TeamA", "TeamB", "TeamC", "TeamD", "TeamE", "TeamF"]),
                    "Team members": random.randint(1, 12),
                    "Shift_duration": random.randint(6, 16),
                    "Activity_Order_Enforced": rand_bool()
                }
                field = pick_one(list(fields.keys()))
                return Instruction(operation=OpType.SET, path=f"{target_act}.{field}", value=fields[field])
                
            else:  # Task
                fields = {
                    "Duration": random.randint(1, 72),
                    "Requires_Shutdown": rand_bool(),
                    "Cost_per_hour": random.randint(25, 1000),
                    "Order_Enforced": rand_bool()
                }
                field = pick_one(list(fields.keys()))
                return Instruction(operation=OpType.SET, path=f"{target_act}.tasks.{target_task}.{field}", value=fields[field])
        
        else:  # DELETE
            level_choice = pick_one(["Activity", "Task"])
            if level_choice == "Activity":
                field = pick_one([
                    "T_period", "T_wait", "Start_disp",
                    "Team", "Team members", "Shift_duration",
                    "Activity_Order_Enforced", "Activity_Order_Before"
                ])
                path = f"{target_act}.{field}"
            else:
                field = pick_one([
                    "Duration", "Requires_Shutdown",
                    "Cost_per_hour", "Order_Enforced", "Order_Before"
                ])
                path = f"{target_act}.tasks.{target_task}.{field}"
            return Instruction(operation=OpType.DELETE, path=path, value=None)
    
    elif instruction_type == "dependent_append":
        # APPEND instrucciones: agregar a listas
        act_candidates = [
            a for a in act_ids
            if a != target_act and a not in base_json[target_act].get("Activity_Order_Before", [])
        ]
        task_candidates = [
            t for t in task_ids
            if t != target_task and t not in base_json[target_act]["tasks"][target_task].get("Order_Before", [])
        ]

        prefer_act = random.random() < 0.5
        if prefer_act and act_candidates:
            return Instruction(operation=OpType.APPEND, path=f"{target_act}.Activity_Order_Before", value=pick_one(act_candidates))
        elif not prefer_act and task_candidates:
            return Instruction(operation=OpType.APPEND, path=f"{target_act}.tasks.{target_task}.Order_Before", value=pick_one(task_candidates))
        elif act_candidates:
            return Instruction(operation=OpType.APPEND, path=f"{target_act}.Activity_Order_Before", value=pick_one(act_candidates))
        elif task_candidates:
            return Instruction(operation=OpType.APPEND, path=f"{target_act}.tasks.{target_task}.Order_Before", value=pick_one(task_candidates))
        else:
            # No hay candidatos para listas -> fallback válido de SET escalar
            fallback_fields = {
                "T_period": random.randint(120, 10080),
                "T_wait": random.randint(1, 72),
                "Start_disp": random.randint(1, 120),
                "Team members": random.randint(1, 12),
                "Shift_duration": random.randint(6, 16),
            }
            f = pick_one(list(fallback_fields.keys()))
            return Instruction(operation=OpType.SET, path=f"{target_act}.{f}", value=fallback_fields[f])
    
    elif instruction_type == "dependent_remove":
        # REMOVE_ITEM: quitar de listas
        removable = []
        for a_id in act_ids:
            for item in base_json[a_id].get("Activity_Order_Before", []):
                removable.append((f"{a_id}.Activity_Order_Before", item))
            for t_id, t_data in base_json[a_id]["tasks"].items():
                for item in t_data.get("Order_Before", []):
                    removable.append((f"{a_id}.tasks.{t_id}.Order_Before", item))
        
        if removable:
            path, val = pick_one(removable)
            return Instruction(operation=OpType.REMOVE_ITEM, path=path, value=val)
        else:
            # Nada removible en listas -> intentar APPEND para crear dependencia
            current_vals = base_json[target_act].get("Activity_Order_Before", [])
            candidates = [a for a in act_ids if a != target_act and a not in current_vals]
            if candidates:
                return Instruction(
                    operation=OpType.APPEND,
                    path=f"{target_act}.Activity_Order_Before",
                    value=pick_one(candidates)
                )

            # Último recurso: SET escalar válido
            fallback_fields = {
                "T_period": random.randint(120, 10080),
                "T_wait": random.randint(1, 72),
                "Start_disp": random.randint(1, 120),
                "Team members": random.randint(1, 12),
                "Shift_duration": random.randint(6, 16),
            }
            f = pick_one(list(fallback_fields.keys()))
            return Instruction(operation=OpType.SET, path=f"{target_act}.{f}", value=fallback_fields[f])
    
    else:
        raise ValueError(f"Tipo de instrucción desconocido: {instruction_type}")


def _fallback_instruction(base_json: Dict[str, Any]) -> Instruction:
    """Fallback a une instrucción simple válida."""
    act_ids = [k for k in base_json.keys() if k.startswith('A')]
    target_act = pick_one(act_ids)
    
    fallback_fields = {
        "T_period": random.randint(120, 10080),
        "T_wait": random.randint(1, 72),
        "Start_disp": random.randint(1, 120),
        "Team members": random.randint(1, 12),
        "Shift_duration": random.randint(6, 16),
    }
    f = pick_one(list(fallback_fields.keys()))
    return Instruction(operation=OpType.SET, path=f"{target_act}.{f}", value=fallback_fields[f])


def generate_instruction_batch(
    base_json: Dict[str, Any],
    completeness: int
) -> Tuple[List[Instruction], str]:
    """
    Genera un lote de 'completeness' instrucciones sin duplicados.
    Mezcla instrucciones independientes y dependientes con estructura causal.
    
    Estrategia:
    - Las instrucciones dependientes siguen a independientes para crear secuencias lógicas
    - Ej: "Crea restricción de que T002 dependa de T001" (causal)
    
    Args:
        base_json: JSON base
        completeness: número de instrucciones (1-15)
    
    Returns:
        (lista de instrucciones, tipo de batch)
    """
    instructions = []
    blacklist: Set[str] = set()
    
    # Decidir mezcla basada en completeness
    # - Completeness bajo: mayormente independientes
    # - Completeness alto: más combinaciones lógicas
    
    if completeness <= 3:
        independent_ratio = 1.0  # Todo independiente
    elif completeness <= 5:
        independent_ratio = 0.7
    elif completeness <= 10:
        independent_ratio = 0.5
    else:
        independent_ratio = 0.4
    
    # Generar secuencia estructurada:
    # Primero generar independientes, luego dependientes que se construyan sobre ellos
    
    num_independent = max(1, int(completeness * independent_ratio))
    num_dependent = completeness - num_independent
    
    # Fase 1: Instrucciones independientes
    for i in range(num_independent):
        instruction = generate_atomic_instruction(base_json, "independent", blacklist)
        instructions.append(instruction)
        blacklist.add(_hash_instruction(instruction))
    
    # Fase 2: Instrucciones dependientes
    # Estas pueden referenciar actividades/tareas modificadas ya
    for i in range(num_dependent):
        # Alternar entre APPEND y REMOVE para variedad
        instr_type = "dependent_append" if i % 2 == 0 else "dependent_remove"
        instruction = generate_atomic_instruction(base_json, instr_type, blacklist)
        instructions.append(instruction)
        blacklist.add(_hash_instruction(instruction))
    
    # Determinar tipo de batch
    if num_dependent == 0:
        batch_type = "independent"
    elif num_independent == 0:
        batch_type = "dependent"
    else:
        batch_type = "mixed"
    
    return instructions, batch_type


def humanize_instruction_batch(
    instructions: List[Instruction],
    json_base: Dict[str, Any],
    llm: LLMService
) -> str:
    """
    Convierte un lote de instrucciones técnicas en UNA SOLA consulta natural.
    Genera un párrafo coherente que encadena todas las instrucciones de manera natural.
    """
    
    BATCH_HUMANIZER_PROMPT = """Eres un normalizador semántico para mantenimiento industrial (Industria 5.0).

        PRINCIPIO CLAVE: "COLOQUIAL PERO COMPLETO EN UN SOLO PÁRRAFO"
        - Debes redactar como hablaría un operario real en planta: natural, directo y con contexto operativo.
        - La instrucción debe incluir TODA la información necesaria para ejecutar TODOS los cambios de la lista sin ambigüedad.
        - No uses claves técnicas literales del esquema en la frase final (evita `Duration`, `Order_Before`, `Start_disp`, etc.).
        - IMPORTANTE: Debes generar un único párrafo fluido y coherente, no una lista de puntos.

        OBJETIVO
        - Recibirás una LISTA de instrucciones técnicas con `operation`, `path` y `value`.
        - Devuelve una solicitud humana única en español que conserve EXACTAMENTE la intención de todo el conjunto.

        SEMÁNTICA OFICIAL (OBLIGATORIA)
        1) SET
        - Establece o reemplaza un valor numérico, booleano o string.
        - Exprésalo como ajuste concreto: "cambia", "ajusta", "deja", "actualiza", "pon", "asigna", "activa/desactiva" (si es booleano).

        2) DELETE
        - Elimina el campo completo de la configuración.
        - No significa poner a cero ni vaciar parcialmente.
        - Exprésalo como: "borra el parámetro de...", "elimina la restricción de...", "quita el dato de...".

        3) APPEND
        - Agrega un único elemento a una lista existente (normalmente dependencias).
        - En precedencias (`Order_Before`), representa "X debe terminar antes de que empiece Y".
        - Exprésalo como adición: "añade a...", "haz que ahora también dependa de...".

        4) REMOVE_ITEM
        - Quita un único elemento específico de una lista.
        - No borra el campo completo, solo rompe un enlace o quita un item.
        - OBLIGATORIO: En precedencias, mantén la dirección correcta. Exprésalo como: "quita la regla que obligaba a que [PATH] terminara antes de empezar [VALUE]", "elimina la dependencia de que [PATH] vaya antes que [VALUE]".

        REGLAS DE ESTILO (OBLIGATORIAS)
        - Usa lenguaje de piso de planta, claro y ejecutable.
        - Emplea sinónimos industriales obligatorios según el nivel del parámetro:

        [NIVEL GLOBAL]
        - Teams -> "equipos totales", "cuadrillas disponibles en fábrica", "número de equipos"
        - Simulation_period -> "horizonte de simulación", "ventana de tiempo a simular", "periodo global"

        [NIVEL DE ACTIVIDAD]
        - T_period -> "frecuencia de mantenimiento", "periodo entre intervenciones", "ciclo de repetición"
        - T_wait -> "tiempo de espera", "demora antes de repetir", "margen de espera"
        - Start_disp -> "desplazamiento inicial", "retraso del primer inicio", "inicio diferido de la campaña"
        - Team -> "equipo asignado", "cuadrilla encargada"
        - Team members -> "dotación", "personal asignado", "cantidad de operarios", "tamaño de la cuadrilla"
        - Shift_duration -> "duración del turno", "largo del turno", "horas por turno"
        - Activity_Order_Enforced -> "forzar orden de actividades", "activar secuencia estricta", "obligatoriedad de la ruta"
        - Activity_Order_Before -> "precede a la actividad", "va antes que la actividad", "bloquea a"

        [NIVEL DE TAREA]
        - Duration -> "duración", "tiempo de ejecución", "tiempo de proceso", "tiempo operativo"
        - Requires_Shutdown -> "requiere parada", "necesita apagar la máquina", "implica paro de línea"
        - Cost_per_hour -> "costo por hora", "tarifa horaria", "costo operativo"
        - Order_Enforced -> "forzar orden de tareas", "hacer obligatoria la secuencia de tareas"
        - Order_Before -> "precede a la tarea", "va antes que la tarea", "es requisito para"

        - Puedes referirte a IDs de forma humana cuando sea natural:
        - `A001` -> "actividad 1" / "primera actividad" / "actividad A-001"
        - `T002` -> "tarea 2" / "segunda tarea" / "paso 2"
        
        - REGLA DE ORO PARA DEPENDENCIAS (Order_Before / Activity_Order_Before):
        La clave significa "Ordenado Antes De". Por tanto, el elemento en el `path` es SIEMPRE el PREDECESOR y el elemento en el `value` es SIEMPRE el SUCESOR.
        Fórmula mental obligatoria: "[PATH] debe terminar antes de que empiece [VALUE]".
        ERROR CRÍTICO A EVITAR: NUNCA trates el `value` como un requisito previo. NUNCA digas "A002 debe terminar antes de A001" si el path es A001.

        ESTRATEGIA DE ENCADENAMIENTO (PÁRRAFO COHERENTE)
        - Si las instrucciones son INDEPENDIENTES: Únelas con conectores simples ("y", "además", "también").
        Ej: "Cambia X, borra Y y además ajusta Z".
        - Si las instrucciones son DEPENDIENTES (causales): Explica el motivo del cambio o la secuencia lógica.
        Ej: "Como la tarea 1 ahora dura más, ajusta su tiempo a 10 horas y haz que la tarea 2 dependa de ella".
        - Si son MIXTAS: Mezcla ambos estilos para que suene como una orden de trabajo real.

        VARIEDAD EN LA APERTURA:
        - ¡PROHIBIDO empezar siempre con "Oye,"! Alterna entre:
        - Directo al verbo: "Cambia...", "Ajusta...", "Borra..."
        - Peticiones: "Por favor,", "Necesito que", "Hazme un favor,"
        - Conversacionales: "Mira,", "Apunta que", "Anota por ahí".

        - Longitud: Un solo párrafo, máximo 4 frases para cubrir toda la lista.
        - Cero ambigüedad: Siempre debe quedar claro qué se cambia en qué lugar.

        PROHIBIDO
        - Frases vagas: "cambia eso", "arréglalo".
        - Listas numeradas o con viñetas.
        - Jerga técnica: "path", "OpType", "JSON", nombres de claves con guiones bajos.

        SALIDA
        - Responde SOLO JSON válido con este formato exacto:
        {"natural_query": "..."}
        - Sin markdown, sin explicación adicional.
        """

    # Construir contexto detallado
    act_ids = [k for k in json_base.keys() if k.startswith('A')]
    
    instructions_text = "\n".join([
        f"  {i+1}. {instr.operation} | Path: {instr.path} | Value: {instr.value}"
        for i, instr in enumerate(instructions)
    ])
    
    # Detectar causalidad en instrucciones
    causality_hint = _detect_causality(instructions)
    
    context_detail = f"""
        Total de instrucciones: {len(instructions)}
        Tipo de instrucciones: {causality_hint}
        Actividades totales: {len(act_ids)}
        Equipos globales: {json_base.get('Teams', 'N/A')}
        
        Instrucciones técnicas:
        {instructions_text}
        """
    
    user_input = f"""
        {context_detail}

        Convierte TODAS estas {len(instructions)} instrucciones a UN SOLO párrafo natural coherente.
        Mantén exactamente la intención de cada cambio, pero hazlo sonar como un operario pidiendo cambios en planta.
        """

    try:
        response = llm.llm(BATCH_HUMANIZER_PROMPT, user_input)
        natural_query = response.get("natural_query", "")
        return natural_query
    
    except Exception as e:
        print(f"⚠️ Error en humanización de lote: {e}")
        # Fallback: generar query manual
        return _fallback_natural_query(instructions)


def apply_instructions_batch(
    json_base: Dict[str, Any],
    instructions: List[Instruction]
) -> Dict[str, Any]:
    """
    Aplica todas las instrucciones al JSON base.
    """
    batch = ModificationBatch(
        thought_process="GT Generado Sintéticamente (Completeness Batch)",
        instructions=instructions
    )
    engine = PetriConfigEngine(json_base)
    json_gt = engine.apply_batch(batch)
    return json_gt


def resolve_output_path(filename: str) -> Path:
    """Resuelve la ruta de salida relativa a la raíz del repo."""
    path_obj = Path(filename)
    if path_obj.is_absolute():
        return path_obj
    return (root_dir / path_obj).resolve()


def create_completeness_dataset(
    fixed_complexity: int = 10,
    samples_per_completeness: int = 50,
    output_filename: str = "benchmarks/datasets/benchmark_completeness.jsonl",
    max_parallel_llm: int = 4
):
    """
    Genera dataset con complejidad FIJA y completeness VARIABLE (1-15).
    
    Args:
        fixed_complexity: N = actividades * tareas (ej: 10, 20, 50)
        samples_per_completeness: cuántas muestras TOTALES por cada nivel de completeness
        output_filename: ruta de salida
    """
    
    valid_combos = []
    for num_activities in range(1, fixed_complexity + 1):
        if fixed_complexity % num_activities == 0:
            tasks_per_act = fixed_complexity // num_activities
            valid_combos.append((num_activities, tasks_per_act))
    
    if not valid_combos:
        raise ValueError(f"Complejidad {fixed_complexity} no tiene factorización válida")
    
    print(f"📊 Generando dataset con complejidad FIJA = {fixed_complexity}")
    print(f"   Combinaciones actividades x tareas: {valid_combos}")
    
    # Inicializar LLM
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    llm = LLMService(temperature=0.7)
    
    output_path = resolve_output_path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    total_samples = 15 * samples_per_completeness
    current_sample = 0
    
    def generate_sample_data(num_activities: int, tasks_per_act: int, completeness: int):
        """Genera JSON base e instrucciones, sin llamadas LLM."""
        json_base = generate_base_json(num_activities, tasks_per_act)
        instructions, batch_type = generate_instruction_batch(json_base, completeness)
        return json_base, instructions, batch_type, num_activities, tasks_per_act, completeness

    def process_sample_data(sample_data):
        """Humaniza y calcula GT para una muestra."""
        json_base, instructions, batch_type, num_activities, tasks_per_act, completeness = sample_data
        natural_query = humanize_instruction_batch(instructions, json_base, llm)
        json_gt = apply_instructions_batch(json_base, instructions)
        return {
            "complexity_nodes": fixed_complexity,
            "activities_count": num_activities,
            "tasks_per_act_count": tasks_per_act,
            "completeness": completeness,
            "instruction_type": batch_type,
            "json_base": json_base,
            "instructions_technical": [instr.model_dump() for instr in instructions],
            "instructions_natural": natural_query,
            "json_gt": json_gt
        }

    with open(output_path, 'w', encoding='utf-8') as f:
        with ThreadPoolExecutor(max_workers=max_parallel_llm) as executor:
            for completeness in range(1, 16):  # 1 a 15 instrucciones
                print(f"\n📝 Completeness = {completeness} (objetivo total: {samples_per_completeness})")

                # Repartir las muestras del nivel C entre todas las combinaciones válidas.
                # No son 50 por combinación, sino 50 en total por C.
                combos = valid_combos[:]
                random.shuffle(combos)
                base_samples = samples_per_completeness // len(combos)
                remainder = samples_per_completeness % len(combos)

                for idx, (num_activities, tasks_per_act) in enumerate(combos):
                    samples_for_combo = base_samples + (1 if idx < remainder else 0)
                    if samples_for_combo == 0:
                        continue

                    print(
                        f"  🔧 Combo: {num_activities} actividades × {tasks_per_act} tareas/actividad "
                        f"-> {samples_for_combo} muestras"
                    )

                    combo_data = [
                        generate_sample_data(num_activities, tasks_per_act, completeness)
                        for _ in range(samples_for_combo)
                    ]
                    processed_rows = list(executor.map(process_sample_data, combo_data))

                    for data_row in processed_rows:
                        f.write(json.dumps(data_row) + '\n')
                        current_sample += 1

                        if current_sample % 100 == 0:
                            print(f"    [{current_sample}/{total_samples}] Progreso: {(current_sample/total_samples)*100:.1f}%")
    
    print(f"\n✅ ¡Dataset de completeness guardado en '{output_path}'!")
    print(f"   Total de ejemplos: {total_samples}")
    print(f"   Complejidad fija: {fixed_complexity}")
    print(f"   Completeness: 1-15")
    print(f"   Tipos de instrucciones: independent, dependent, mixed")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Genera dataset con complejidad fija y completeness variable (1-15)"
    )
    parser.add_argument(
        "--complexity",
        type=int,
        default=16,
        help="Complejidad FIJA (N = actividades * tareas). Default: 16"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=50,
        help="Muestras TOTALES por cada nivel de completeness. Default: 50"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmarks/datasets/benchmark_dataset_completeness_1_16_50samples.jsonl",
        help="Archivo de salida JSONL"
    )
    parser.add_argument(
        "--max-parallel-llm",
        type=int,
        default=4,
        help="Cantidad maxima de muestras a humanizar en paralelo. Default: 4"
    )
    
    args = parser.parse_args()
    
    create_completeness_dataset(
        fixed_complexity=args.complexity,
        samples_per_completeness=args.samples,
        output_filename=args.output,
        max_parallel_llm=args.max_parallel_llm
    )
