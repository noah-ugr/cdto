"""
Author: Noah Masegosa Caceres 
Center: @ugr

RouterAgent: Decide la intención del usuario (Contexto, Modificación o Híbrido) para enrutar la consulta al agente adecuado.

Metodos principales:
- orchestrator: Toma la consulta del usuario y devuelve la orquestación de los agentes involucrados y el por qué de esa elección.
"""
from typing import List, Literal
from pydantic import BaseModel, Field
from input_agent.src.models import Colors
from input_agent.src.llm import LLMService
from input_agent.src.prompts import ORCHESTRATOR_PROMPT

TaskType = Literal["context", "planner", "executor", "simulator", "xai", "temporal_xai", "optimizer", "feedback"]

class OrchestratorPlan(BaseModel):
    """El plan maestro generado por el LLM."""
    reasoning: str = Field(description="Explicación estratégica del plan.")
    steps: List[TaskType] = Field(description="Secuencia de agentes a ejecutar.")

class OrchesterAgent:
    """Decide la intención del usuario: Contexto, Modificación o Híbrido."""
    def __init__(self, llm: LLMService):
        self.llm = llm

    def orchestrate(self, query: str) -> str:
        response = self.llm.llm(ORCHESTRATOR_PROMPT, query)
        orchestration = OrchestratorPlan(**response)
        print(f"{Colors.CYAN}📋 Plan Aprobado: {orchestration.steps}\n🤔 Razonamiento: {orchestration.reasoning}{Colors.RESET}")
        return orchestration