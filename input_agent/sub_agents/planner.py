"""
Author: Noah Masegosa Caceres 
Center: @ugr

PlannerAgent: Traduce lenguaje natural a DSL (ModificationBatch) para que el agente de modificación ejecute los cambios.

Metodos principales:
- create_plan: Toma la consulta del usuario, el contexto actual y el historial de errores para generar un plan de acción
    en formato JSON con el proceso de pensamiento y las instrucciones detalladas.
"""

import textwrap
from typing import Dict
from input_agent.src.models import Colors
from input_agent.src.llm import LLMService
from input_agent.src.prompts import PLANNER_PROMPT


class PlannerAgent:
    """Traduce lenguaje natural a DSL (ModificationBatch)."""
    def __init__(self, llm: LLMService):
        self.llm = llm

    def create_plan(self, user_query: str, context_str: str, history_str: str) -> Dict:
        
        planner_input = user_query
        if context_str:
            planner_input = textwrap.dedent(f"""
            --- CONTEXTO ACTUAL (READ-ONLY) ---
            {context_str}
            --- INSTRUCCIÓN DEL USUARIO ---
            {user_query}
            """)
        
        if history_str:
            planner_input = f"--- ERRORES PREVIOS ---\n{history_str}\n--- NUEVA ORDEN ---\n{planner_input}"

        plan_json = self.llm.llm(PLANNER_PROMPT, planner_input)
        print(f"{Colors.CYAN}🤖 Pensamiento: {plan_json.get('thought_process')}{Colors.RESET}")
        print(f"{Colors.CYAN}📋 Instrucción planificada: {plan_json.get('instructions')}{Colors.RESET}")
        return plan_json