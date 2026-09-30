import json
import random
import sys
from pathlib import Path
from typing import Dict, Any, List
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

def generate_atomic_instruction(base_json: Dict[str, Any]) -> Instruction:
    """
    Genera de forma segura una instrucción atómica abarcando
    parámetros globales, de actividad y de tarea.
    """
    act_ids = [k for k in base_json.keys() if k.startswith('A')]
    target_act = pick_one(act_ids)
    task_ids = list(base_json[target_act]["tasks"].keys())
    target_task = pick_one(task_ids)
    
    modifying_ops = [OpType.SET, OpType.DELETE, OpType.APPEND, OpType.REMOVE_ITEM]
    op_choice = pick_one(modifying_ops)
    
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
            
        else:
            fields = {
                "Duration": random.randint(1, 72),
                "Requires_Shutdown": rand_bool(),
                "Cost_per_hour": random.randint(25, 1000),
                "Order_Enforced": rand_bool()
            }
            field = pick_one(list(fields.keys()))
            return Instruction(operation=OpType.SET, path=f"{target_act}.tasks.{target_task}.{field}", value=fields[field])

    elif op_choice == OpType.DELETE:
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

    elif op_choice == OpType.APPEND:
        act_candidates  = [a for a in act_ids  if a != target_act  and a not in base_json[target_act].get("Activity_Order_Before", [])]
        task_candidates = [t for t in task_ids if t != target_task and t not in base_json[target_act]["tasks"][target_task].get("Order_Before", [])]

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
            # Truly no list candidates anywhere → random scalar SET
            fallback_fields = {
                "T_period": random.randint(120, 10080),
                "T_wait": random.randint(1, 72),
                "Start_disp": random.randint(1, 120),
                "Team members": random.randint(1, 12),
                "Shift_duration": random.randint(6, 16),
            }
            f = pick_one(list(fallback_fields.keys()))
            return Instruction(operation=OpType.SET, path=f"{target_act}.{f}", value=fallback_fields[f])

    elif op_choice == OpType.REMOVE_ITEM:
        # Collect ALL removable (path, value) pairs across the entire JSON
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

        # Nothing removable anywhere → fall back to APPEND to add a dependency
        current_vals = base_json[target_act].get("Activity_Order_Before", [])
        candidates = [a for a in act_ids if a != target_act and a not in current_vals]
        if candidates:
            return Instruction(
                operation=OpType.APPEND,
                path=f"{target_act}.Activity_Order_Before",
                value=pick_one(candidates)
            )
        # Last resort: SET a valid scalar
        fallback_fields = {
            "T_period": random.randint(120, 10080),
            "T_wait": random.randint(1, 72),
            "Start_disp": random.randint(1, 120),
            "Team members": random.randint(1, 12),
            "Shift_duration": random.randint(6, 16),
        }
        f = pick_one(list(fallback_fields.keys()))
        return Instruction(operation=OpType.SET, path=f"{target_act}.{f}", value=fallback_fields[f])

def humanize_instruction(instruction: Instruction, json_base: Dict[str, Any], llm: LLMService) -> str:
    """
    Convierte una instrucción técnica en lenguaje natural usando un LLM.
    Esto simula cómo un usuario real pediría ese cambio.
    """
    
    HUMANIZER_PROMPT = """Eres un normalizador semántico para mantenimiento industrial (Industria 5.0).

    PRINCIPIO CLAVE: "COLOQUIAL PERO COMPLETO"
    - Debes redactar como hablaría un operario real en planta: natural, directo y con contexto operativo.
    - La instrucción debe incluir TODA la información necesaria para ejecutar el cambio sin ambigüedad.
    - No uses claves técnicas literales del esquema en la frase final (evita `Duration`, `Order_Before`, `Start_disp`, etc.).

    OBJETIVO
    - Recibirás una instrucción técnica con `operation`, `path` y `value`.
    - Devuelve una solicitud humana en español que conserve EXACTAMENTE la intención.

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
      Ejemplo: Si path="A001.Activity_Order_Before" y value="A002", significa "A001 va antes de A002".
      ERROR CRÍTICO A EVITAR: NUNCA trates el `value` como un requisito previo. NUNCA digas "A002 debe terminar antes de A001".

    - VARIEDAD EN LA APERTURA: ¡PROHIBIDO empezar siempre con "Oye,"! Eres un humano dinámico. Alterna entre diferentes formas de empezar o ve directo al grano. 
      Usa opciones como:
      - Directo al verbo: "Cambia...", "Ajusta...", "Borra..."
      - Peticiones formales/informales: "Por favor,", "Necesito que", "Hazme un favor,"
      - Conversacionales: "Mira,", "Apunta que", "Anota por ahí", "Oye," (úsalo raramente).

    - Longitud: 1 frase, máximo 2.
    - Cero ambigüedad: siempre debe quedar claro qué se cambia, dónde y a qué valor.

    EJEMPLOS SWEET SPOT (CORRECTOS)
    - Técnico: SET A001.tasks.T002.Duration = 8
      Natural: "Mira, cambia a 8 horas la duración de la segunda tarea de la actividad uno."
    - Técnico: SET A002.Start_disp = 24
      Natural: "Necesito que ajustes el retraso del primer inicio de la actividad 2 para que sea de 24 horas."
    - Técnico: SET A003.tasks.T001.Requires_Shutdown = true
      Natural: "Anota por ahí que el primer paso de la tercera actividad ahora requiere parada de línea."
    - Técnico: APPEND A002.Activity_Order_Before = A005
      Natural: "Por favor, añade una restricción para que la actividad 2 tenga que terminar antes de empezar la actividad 5."
    - Técnico: REMOVE_ITEM A005.tasks.T007.Order_Before = T003
      Natural: "Quita la dependencia que obligaba a la tarea 7 a ejecutarse antes que la tarea 3 dentro de la actividad 5."

    EJEMPLO DE ERROR A EVITAR (INCORRECTO)
    - Técnico: REMOVE_ITEM A001.Activity_Order_Before = A002
      Natural INCORRECTO (Prohibido): "Quita la regla que obliga a que la actividad 2 termine antes que la 1."
      Natural CORRECTO: "Quita la regla que obliga a que la actividad 1 termine antes de empezar la actividad 2."

    PROHIBIDO
    - Frases vagas: "cambia eso", "arréglalo", "modifica el parámetro".
    - Jerga técnica en la salida: "path", "OpType", "JSON", nombres de claves exactas con guiones bajos (ej. T_wait).
    - Invertir sujeto/objeto en precedencias.

    SALIDA
    - Responde SOLO JSON válido con este formato exacto:
    {"natural_query": "..."}
    - Sin markdown, sin explicación adicional.
    """

    instruction_dict = instruction.model_dump()
    path = instruction_dict['path']
    operation = instruction_dict['operation']
    value = instruction_dict['value']

    path_parts = path.split('.')
    scope = "GLOBAL"
    target_activity = None
    target_task = None
    field_name = path_parts[-1]
    
    if len(path_parts) >= 1 and path_parts[0].startswith('A'):
        target_activity = path_parts[0]
        scope = "ACTIVIDAD"
        
        if len(path_parts) >= 3 and path_parts[1] == 'tasks':
            target_task = path_parts[2]
            scope = "TAREA"
    
    act_ids = [k for k in json_base.keys() if k.startswith('A')]
    
    context_detail = f"""
        Alcance: {scope}
        {f"Actividad objetivo: {target_activity}" if target_activity else "Parámetro global del sistema"}
        {f"Tarea objetivo: {target_task}" if target_task else ""}
        Campo a modificar: {field_name}
        Total de actividades en el sistema: {len(act_ids)}
        Total de equipos globales: {json_base.get('Teams', 'N/A')}
        """
            
    user_input = f"""
        {context_detail}

        Instrucción técnica:
        - Operación: {operation}
        - Path completo: {path}
        - Valor: {value}

        Convierte esto a lenguaje natural ESPECIFICANDO claramente el alcance (global/actividad/tarea) y los códigos exactos:"""

    try:
        response = llm.llm(HUMANIZER_PROMPT, user_input)
        natural_query = response.get("natural_query", "")
        return natural_query
    
    except Exception as e:
        print(f"⚠️ Error en humanización: {e}")
        return "Error al generar consulta natural."


def resolve_output_path(filename: str) -> Path:
    """Resuelve la ruta de salida relativa a la raiz del repo."""
    path_obj = Path(filename)
    if path_obj.is_absolute():
        return path_obj
    return (root_dir / path_obj).resolve()


def build_complexity_schedule(max_n: int = 150) -> List[int]:
    """
    Define un barrido de complejidad escalonado para evitar saturación en N altas.

    - N bajas: granularidad fina (paso 1) hasta 50.
    - N altas: saltos más grandes en hitos fijos.
    """
    high_n_checkpoints = [60, 70, 80, 90, 100, 115, 130, 150]
    schedule = list(range(1, min(50, max_n) + 1))
    schedule.extend(n for n in high_n_checkpoints if 50 < n <= max_n)
    return sorted(set(schedule))

def create_benchmark_dataset(filename="benchmarks/datasets/benchmark_dataset_1_150.jsonl", max_parallel_llm=4):
    target_complexities = build_complexity_schedule(max_n=150)

    complexities = []
    for n_complexity in target_complexities:
        for num_activities in range(1, n_complexity + 1):
            if n_complexity % num_activities == 0:
                tasks_per_act = n_complexity // num_activities
                complexities.append((num_activities, tasks_per_act))

    samples_per_complexity = 50

    complexity_groups = {}
    for num_activities, tasks_per_act in complexities:
        n_complexity = num_activities * tasks_per_act
        if n_complexity not in complexity_groups:
            complexity_groups[n_complexity] = []
        complexity_groups[n_complexity].append((num_activities, tasks_per_act))

    generation_plan = []
    for n_complexity in target_complexities:
        if n_complexity not in complexity_groups:
            continue
        combos = complexity_groups[n_complexity][:]
        random.shuffle(combos)
        base_samples = samples_per_complexity // len(combos)
        remainder = samples_per_complexity % len(combos)

        for idx, (num_activities, tasks_per_act) in enumerate(combos):
            samples_for_combo = base_samples + (1 if idx < remainder else 0)
            if samples_for_combo > 0:
                generation_plan.append((num_activities, tasks_per_act, n_complexity, samples_for_combo))
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    llm = LLMService(temperature=0.7)
    
    output_path = resolve_output_path(filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Helpers para paralelización
    def generate_sample_data(num_activities, tasks_per_act, n_complexity):
        """Genera JSON base e instrucción (sin llamar al LLM)."""
        json_base = generate_base_json(num_activities, tasks_per_act)
        instruction = generate_atomic_instruction(json_base)
        return (json_base, instruction, n_complexity, num_activities, tasks_per_act)

    def humanize_with_llm(data_tuple):
        """Humaniza una instrucción usando el LLM."""
        json_base, instruction, n_complexity, num_activities, tasks_per_act = data_tuple
        natural_query = humanize_instruction(instruction, json_base, llm)
        return (json_base, instruction, n_complexity, num_activities, tasks_per_act, natural_query)

    with open(output_path, 'w', encoding='utf-8') as f:
        total_samples = sum(samples_for_combo for _, _, _, samples_for_combo in generation_plan)
        processed_count = 0
        last_progress_checkpoint = 0

        with ThreadPoolExecutor(max_workers=max_parallel_llm) as executor:
            for num_activities, tasks_per_act, n_complexity, samples_for_combo in generation_plan:
                print(f"Generando dataset N={n_complexity} con {num_activities}x{tasks_per_act} ({samples_for_combo} muestras)...")
                
                combo_data = []
                for i in range(samples_for_combo):
                    data = generate_sample_data(num_activities, tasks_per_act, n_complexity)
                    combo_data.append(data)
                
                futures = list(executor.map(humanize_with_llm, combo_data))
                
                for result in futures:
                    json_base, instruction, n_complexity, num_activities, tasks_per_act, natural_query = result
                    
                    batch = ModificationBatch(
                        thought_process="GT Generado Sintéticamente",
                        instructions=[instruction]
                    )
                    engine = PetriConfigEngine(json_base)
                    json_gt = engine.apply_batch(batch)
                    
                    data_row = {
                        "complexity_nodes": n_complexity,
                        "activities_count": num_activities,
                        "tasks_per_act_count": tasks_per_act,
                        "json_base": json_base,
                        "instruction_technical": instruction.model_dump(),
                        "instruction_natural": natural_query,
                        "json_gt": json_gt
                    }
                    f.write(json.dumps(data_row) + '\n')
                    processed_count += 1
                    
                    # Imprimir progreso cada 50 muestras
                    if processed_count // 50 > last_progress_checkpoint:
                        last_progress_checkpoint = processed_count // 50
                        print(f"  [{processed_count}/{total_samples}] Progreso: {(processed_count/total_samples)*100:.1f}%")
                
    print(f"N de complejidad incluidas: {target_complexities}")
    print(f"✅ ¡Dataset balanceado de {total_samples} ejemplos guardado en '{output_path}'!")

if __name__ == "__main__":
    create_benchmark_dataset()