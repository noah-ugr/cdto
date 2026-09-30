"""
Author: Noah Masegosa Caceres 
Center: @ugr

OptimizerAgent: Extrae objetivos de KPI mediante lenguaje natural y ejecuta optimizadores.

Metodos principales:
- optimize: Toma la consulta del usuario, extrae los parámetros de KPI y ejecuta el optimizador seleccionado.
"""

import copy
import os
import sys
import json
import subprocess
from typing import Any, Dict, Tuple, Optional
from input_agent.src.models import Colors, ModificationBatch
from input_agent.src.llm import LLMService
from input_agent.src.tools import kpi_orchestrator
from config.paths import SHARED_DICTS_JSON

# Variables de decisión de la IWO. La formulación que carga iwo-new-single.py
# (optimizers/formulations/CostMinimization_underAvailability _TaskConstraints.py) define
# x = [Crew_size, T_shift_hours, Start_disp[Act_1..M], T_wait[Act_1..M]] con sus límites, y
# escribe Crew_size y T_shift_hours en todas las actividades, como Team members y Shift_duration.
DECISION_FIELDS = ("Team members", "Shift_duration", "Start_disp", "T_wait")


def _algorithm_activities(current_config: Dict) -> Dict[str, str]:
    """ActIDn -> código de actividad, con la numeración de la entrada de la IWO. Se importa aquí
    porque la correspondencia es la del engine, que solo hace falta con el optimizador."""
    from utils.mapping_utils import map_to_algorithm_format

    _, mapping = map_to_algorithm_format(current_config)
    return mapping["activities"]


def decision_values(algorithm_config: Dict, current_config: Dict) -> Dict[str, Dict[str, Any]]:
    """Variables de decisión de la configuración que deja la IWO (formato del algoritmo, ActIDn),
    por actividad de current_config. ActIDn es la n-ésima actividad de current_config, como en
    utils/mapping_utils.map_to_algorithm_format."""
    activities = algorithm_config.get("PNIpnt") if isinstance(algorithm_config.get("PNIpnt"), dict) else algorithm_config
    values = {}
    for act_id, act_code in _algorithm_activities(current_config).items():
        algo_act = activities.get(act_id)
        if not isinstance(algo_act, dict):
            raise ValueError(f"La IWO no devolvió {act_id} ({act_code}).")
        missing = [field for field in DECISION_FIELDS if field not in algo_act]
        if missing:
            raise ValueError(f"La IWO no devolvió {missing} para {act_id} ({act_code}).")
        values[act_code] = {field: algo_act[field] for field in DECISION_FIELDS}
    return values


def build_s_star(current_config: Dict, algorithm_config: Dict) -> Dict:
    """S*: la configuración actual con solo las variables de decisión de la IWO sustituidas. Se
    conserva todo lo demás: tareas con Requires_Shutdown, precedencias, flags y Simulation_period."""
    s_star = copy.deepcopy(current_config)
    for act_code, fields in decision_values(algorithm_config, current_config).items():
        s_star[act_code].update(fields)
    return s_star


def decision_batch(current_config: Dict, s_star: Dict) -> ModificationBatch:
    """Batch de SET con cada variable de decisión que S* cambia respecto a la configuración actual."""
    instructions = [
        {"operation": "SET", "path": f"{act_code}.{field}", "value": s_star[act_code][field]}
        for act_code in _algorithm_activities(current_config).values()
        for field in DECISION_FIELDS
        if s_star[act_code].get(field) != current_config[act_code].get(field)
    ]
    return ModificationBatch(
        thought_process="Variables de decisión de la IWO (S*) sobre la configuración actual.",
        instructions=instructions,
    )


class OptimizerAgent:
    """Extrae objetivos de KPI y ejecuta optimizadores (IWO o QGA)."""
    
    def __init__(self, llm: LLMService):
        self.llm = llm
    
    def optimize(
        self, 
        user_query: str, 
        optimizer_type: Optional[str] = None,
        json_input: Optional[Dict] = None
    ) -> Tuple[bool, Dict, Optional[Dict], str]:
        """
        Ejecuta el flujo completo de optimización.
        
        Args:
            user_query: Consulta del usuario en lenguaje natural
            optimizer_type: "iwo" o "qga". Si None, se detecta automáticamente
            json_input: Entrada JSON opcional para el optimizador
        Returns:
            Tuple de (success, extracted_kpis, optimized_config, message)
        """
        try:
            if not optimizer_type:
                optimizer_type = self._detect_optimizer(user_query)
            
            print(f"\n{Colors.CYAN}🎯 Iniciando optimización con {optimizer_type.upper()}...{Colors.RESET}")
            
            print(f"{Colors.CYAN}🔍 Extrayendo parámetros de KPI...{Colors.RESET}")
            extracted_kpis = kpi_orchestrator(user_query, self.llm)
            
            if not extracted_kpis:
                return (
                    False, 
                    {}, 
                    None, 
                    "No se pudieron extraer parámetros de KPI de la consulta"
                )
            
            print(f"{Colors.GREEN}✅ KPIs extraídos: {list(extracted_kpis.keys())}{Colors.RESET}")
            
            success, config, msg = self._run_optimizer(optimizer_type, extracted_kpis, json_input)
            
            return (success, extracted_kpis, config, msg)
            
        except Exception as e:
            error_msg = f"Error en optimización: {str(e)}"
            print(f"{Colors.RED}{error_msg}{Colors.RESET}")
            return (False, {}, None, error_msg)
    
    def _detect_optimizer(self, query: str) -> str:
        """Detecta qué optimizador usar basándose en la query."""
        query_lower = query.lower()
        if "qga" in query_lower or "quantum" in query_lower:
            return "qga"
        return "iwo"  # Default
    
    def _run_optimizer(self, optimizer_type: str, extracted_kpis: Optional[Dict] = None, json_input: Optional[Dict] = None) -> Tuple[bool, Optional[Dict], str]:
        """
        Ejecuta el optimizador especificado como subproceso.
        
        Args:
            optimizer_type: Tipo de optimizador ("iwo" o "qga")
            extracted_kpis: Diccionario de KPIs extraídos para pasar al subproceso
            json_input: Entrada JSON opcional para el optimizador

        Returns:
            Tuple de (success, optimized_config, message)
        """
        optimizer_files = {
            "iwo": "iwo-new-single.py",
            "qga": "QGA-new-single.py"
        }
        
        optimizer_file = optimizer_files.get(optimizer_type)
        if not optimizer_file:
            return (False, None, f"Optimizador '{optimizer_type}' no válido")

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        optimizer_path = os.path.join(project_root, "optimizers", "algorithms", optimizer_file)
        
        if not os.path.exists(optimizer_path):
            return (False, None, f"Archivo de optimizador no encontrado: {optimizer_path}")
        
        print(f"{Colors.CYAN}🚀 Ejecutando optimizador {optimizer_type.upper()}...{Colors.RESET}")
        print(f"{Colors.DIM}(Esto puede tardar varios minutos...){Colors.RESET}")
        
        try:
            # Preparar variables de entorno
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env["OPTIMIZERS_FORMULATIONS_DIR"] = os.path.join(project_root, "optimizers", "formulations")
            petrinet_main_candidates = [
                os.path.join(project_root, "core", "main.py"),
                os.path.join(project_root, "Modules", "Paramtrial_petri_net_A.py"),
            ]
            for petrinet_main_path in petrinet_main_candidates:
                if os.path.exists(petrinet_main_path):
                    env["PETRINET_MAIN"] = petrinet_main_path
                    break
            if extracted_kpis:
                env["KPI_OBJECTIVES"] = json.dumps(extracted_kpis)
            if json_input:
                env["JSON_INPUT"] = json.dumps(json_input)
            
            result = subprocess.run(
                [sys.executable, optimizer_path],
                capture_output=True,
                text=True,
                cwd=project_root,
                env=env
            )
            
            if result.returncode != 0:
                error_text = (result.stderr or result.stdout or "").strip()
                error_msg = f"Error al ejecutar optimizador: {error_text[:2000]}"
                print(f"{Colors.RED}{error_msg}{Colors.RESET}")
                return (False, None, error_msg)
            
            output_file = str(SHARED_DICTS_JSON)
            
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    optimized_config = json.load(f)

                if json_input:
                    # S* parte de la configuración actual y de la salida de la IWO solo toma las
                    # variables de decisión: tareas, precedencias, flags y horizonte se conservan.
                    optimized_config = build_s_star(json_input, optimized_config)

                print(f"{Colors.GREEN}✅ Configuración óptima cargada desde {output_file}{Colors.RESET}")
                return (True, optimized_config, f"Optimización completada exitosamente")
            else:
                warning_msg = f"Optimizador ejecutado pero no se encontró {output_file}"
                print(f"{Colors.YELLOW}⚠️ {warning_msg}{Colors.RESET}")
                print(f"{Colors.DIM}Output: {result.stdout[-500:]}{Colors.RESET}")
                return (True, None, warning_msg)
                
        except subprocess.TimeoutExpired:
            error_msg = "Timeout: el optimizador tardó más de 5 minutos"
            print(f"{Colors.RED}❌ {error_msg}{Colors.RESET}")
            return (False, None, error_msg)
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            print(f"{Colors.RED}❌ {error_msg}{Colors.RESET}")
            return (False, None, error_msg)
