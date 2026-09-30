"""
Author: Noah Masegosa Caceres 
Center: @ugr

ChatAgent: Maneja la interacción con el usuario, formulando respuestas claras y contextuales.
    - generate_response: Toma la consulta del usuario, el historial de mensajes y el contexto relevante para generar una respuesta coherente y útil utilizando el LLM.

"""

from input_agent.src.llm import LLMService
from input_agent.src.prompts import CHATBOT_PROMPT


class ChatAgent:
    """Maneja la interacción con el usuario, formulando respuestas claras y contextuales."""
    def __init__(self, llm: LLMService):
        self.llm = llm

    def generate_response(self, query: str, message_history: list, context_info: str) -> str:
        if isinstance(message_history, list):
            normalized_history = "\n".join(str(item) for item in message_history)
        else:
            normalized_history = str(message_history)

        chat_ctx = (
            "### USER QUERY\n"
            f"{query}\n\n"
            "### TECHNICAL EXECUTION LOG\n"
            f"{normalized_history}\n\n"
            "### DETAILED CONTEXT\n"
            f"{context_info}"
        )
        response = self.llm.llm(CHATBOT_PROMPT, chat_ctx)
        return response