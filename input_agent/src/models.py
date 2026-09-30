"""
Author: Noah Masegosa Caceres 
Center: @ugr

Objective: Code for the models used in the input agent.
"""

from typing import List, Any, Optional, Dict
from pydantic import BaseModel
from enum import Enum


class OpType(str, Enum):
    """
    Enumeración de las operaciones soportadas para modificar el JSON.
    """
    SET = "SET"                 # Establecer o reemplazar un valor (para dicts o listas por índice).
    DELETE = "DELETE"           # Eliminar una clave de un diccionario.
    APPEND = "APPEND"           # Añadir un elemento al final de una lista.
    REMOVE_ITEM = "REMOVE_ITEM" # Eliminar una ocurrencia específica de un valor en una lista.
    GET = "GET"                 # Operación de solo lectura (no modifica nada).

class Instruction(BaseModel):
    """
    Modelo que representa una única instrucción de cambio.
    
    Attributes:
        operation (OpType): Tipo de operación a realizar.
        path (str): Ruta en notación de puntos (ej: "A001.tasks.T001.duration").
        value (Optional[Any]): Valor a insertar o eliminar. Puede ser nulo para DELETE.
    """
    operation: OpType
    path: str
    value: Optional[Any] = None 

class ModificationBatch(BaseModel):
    """
    Modelo que agrupa la respuesta del Agente Planificador.
    
    Attributes:
        thought_process (str): Explicación del razonamiento del LLM (Cadena de Pensamiento).
        instructions (List[Instruction]): Lista ordenada de cambios a aplicar.
    """
    thought_process: str
    instructions: List[Instruction]

class ValidationStatus(str, Enum):
    """Estado del resultado de la validación semántica."""
    PASS = "PASS"
    FAIL = "FAIL"

class FeedbackResponse(BaseModel):
    """
    Modelo para la respuesta del Agente de Feedback tras un fallo determinista.
    """
    diagnosis: str  # Explicación clara del error técnico
    suggestion: str # Propuesta de mejora o nueva query para el usuario

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    MAGENTA = '\033[35m'
    DIM = '\033[2m'

class StepNarrative(BaseModel):
    """
    Modelo para representar la narrativa generada para cada paso.
    """
    narrative: str

class FullNarrative(BaseModel):
    """
    Modelo para representar la narrativa final consolidada.
    """
    report: str

class ChatResponse(BaseModel):
    """
    Modelo para representar la respuesta generada por el ChatAgent.
    """
    response: str

# ============== KPI OPTIMIZATION MODELS ==============

class AvailabilityOutput(BaseModel):
    AVAILABILITY_TARGET: Optional[float] = None
    AVAILABILITY_PENALTY: Optional[float] = None

class RequirementsOutput(BaseModel):
    REQUIRED_ACTIVITIES: Optional[List[str]] = None
    REQUIRED_PENALTY: Optional[float] = None

class CostOutput(BaseModel):
    COST_REF_EUR: Optional[float] = None
    DEFAULT_TASK_COST_PER_HOUR: Optional[float] = None
    COST_MODE: Optional[str] = None

class BoundariesOutput(BaseModel):
    MIN_SHIFT_H: Optional[float] = None
    MAX_SHIFT_H: Optional[float] = None
    T_WAIT_MIN: Optional[float] = None
    T_WAIT_MAX: Optional[float] = None

class EnvironmentOutput(BaseModel):
    SIMULATION_PERIOD_HOURS: Optional[float] = None
    CONFIG_MAIN_FILE: Optional[str] = None
    CONFIG_SHARED_JSON: Optional[str] = None

class OptimizerGlobalConfig(BaseModel):
    """Modelo contenedor que agrupa las respuestas de los 5 subagentes de optimización."""
    availability: AvailabilityOutput
    requirements: RequirementsOutput
    cost: CostOutput
    boundaries: BoundariesOutput
    environment: EnvironmentOutput

    def get_active_updates(self) -> dict:
        """Aplana la estructura jerárquica y elimina los valores None."""
        flat_updates = {}
        for _, submodel_inst in self:
            for key, value in submodel_inst:
                if value is not None:
                    flat_updates[key] = value
        return flat_updates