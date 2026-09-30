"""
Author: Noah Masegosa Caceres 
Center: @ugr

FeedbackAgent: Diagnostica errores y sugiere correcciones en lenguaje natural.
    - analyze_error: Toma la consulta del usuario y los errores de validación, y devuelve
        un diagnóstico claro con sugerencias de corrección.

ValidatorEngine: Encapsula la validación determinista de Python.
    - validate: Ejecuta la validación determinista, devolviendo un estado de validez y la lista de violaciones
        estructuradas (regla, grupo, ruta, detalle).

JSONContextHandler: Gestiona la recuperación de información del JSON base.
    - retrieve: Dado una consulta, recupera información relevante del JSON utilizando el LLM para interpretar la
        consulta y extraer datos del motor de configuración.
"""

import json
from typing import Optional, Tuple

from input_agent.src.PetriNetConfig import PetriConfigEngine
from input_agent.src.llm import LLMService
from input_agent.src.models import Colors, FeedbackResponse, ModificationBatch
from input_agent.src.prompts import FEEDBACK_AGENT_PROMPT, FEEDBACK_AGENT_PROMPT_EPISODIC
from input_agent.src.tools import deterministic_validator, retrieve_context_data


class FeedbackAgent:
    """Diagnostica errores y sugiere correcciones en lenguaje natural."""
    def __init__(self, llm: LLMService):
        self.llm = llm

    def analyze_error(self, query: str, validation_issues: list, episodic_report: str, delta: dict = None) -> FeedbackResponse:
        # delta: cambio entre la configuración actual y el candidato rechazado, si se conoce.
        delta_line = f"\nRejected Candidate Delta (vs current configuration): {json.dumps(delta, ensure_ascii=False)}" if delta else ""
        if episodic_report:
            feedback_ctx = f"User Query: {query}\nValidation Errors: {json.dumps(validation_issues)}{delta_line}\n Episodic Report: {episodic_report}"
            fb_resp = self.llm.llm(FEEDBACK_AGENT_PROMPT_EPISODIC, feedback_ctx)
            return FeedbackResponse(**fb_resp)
        else:
            feedback_ctx = f"User Query: {query}\nValidation Errors: {json.dumps(validation_issues)}{delta_line}"
            fb_resp = self.llm.llm(FEEDBACK_AGENT_PROMPT, feedback_ctx)
            return FeedbackResponse(**fb_resp)
    
class ValidatorEngine:
    """
    Encapsula la validación determinista de Python.

    Devuelve (es_valida, violaciones), con cada violación como {"rule", "group", "path", "detail"}.
    Las condiciones del esquema PetriInput están en las reglas de deterministic_validator
    (input_agent/src/tools.py). La versión anterior (deterministic_validator + PetriInput) está en el
    commit e0f1d0a: git show e0f1d0a:input_agent/sub_agents/feedback.py.
    """
    @staticmethod
    def validate(batch: ModificationBatch, engine: PetriConfigEngine, previous_config: Optional[dict] = None) -> Tuple[bool, list]:
        # previous_config: configuración antes del batch (S_k); solo cambia el detalle de referencias.
        return deterministic_validator(batch, engine, previous_config)

class JSONContextHandler:
    """Gestiona la recuperación de información del JSON base."""
    def __init__(self, llm: LLMService):
        self.llm = llm

    def retrieve(self, query: str, engine: PetriConfigEngine) -> str:
        results = retrieve_context_data(self.llm, query, engine)
        print(f"\n{Colors.GREEN}✅ INFORMACIÓN RECUPERADA:{Colors.RESET}")
        print(results)
        return results