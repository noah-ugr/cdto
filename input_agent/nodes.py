
import contextlib
import copy
import os
import operator
import tempfile
from typing import Annotated, List, Dict, Any, TypedDict, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, AIMessage
from langchain_core.runnables import RunnableConfig
import pandas as pd

from input_agent.src.llm import LLMService
from input_agent.src.models import ModificationBatch, Colors, ChatResponse
from input_agent.src.PetriNetConfig import PetriConfigEngine
from input_agent.src.narrativeProcess import load_kpis_from_stats, compute_kpi_delta
from input_agent.src.tools import RED_DE_PETRI, find_unresolved_routes, format_violation, retrieve_context_data

from input_agent.sub_agents.planner import PlannerAgent
from input_agent.sub_agents.feedback import FeedbackAgent, ValidatorEngine
from input_agent.sub_agents.orchester import OrchesterAgent
from input_agent.sub_agents.chat import ChatAgent
from input_agent.sub_agents.optimizer import OptimizerAgent, decision_batch

import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# delay=True: agent_debug.log se abre (y se vacía, mode='w') con el primer mensaje, no al importar el módulo.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.FileHandler('agent_debug.log', mode='w', encoding='utf-8', delay=True)]
)
logger = logging.getLogger(__name__)
console = Console()

class PetriState(TypedDict):
    # Memoria Conversacional
    messages: Annotated[List[AnyMessage], add_messages] 
    context_data: str
    final_response: str

    # Configuración Petri Net
    original_config: Dict[str, Any]
    current_config: Dict[str, Any]

    # Orquestación (Cola de Tareas)
    task_queue: List[str]            
    current_task: Optional[str]      
    execution_log: Annotated[List[str], operator.add]
    turn_log_start: int  # índice de execution_log donde empieza la consulta actual

    # Datos Transitorios
    proposed_plan: Optional[Dict[str, Any]]
    simulation_ready: bool 
    simulation_paths: Dict[str, str]
    delta: Dict[str, Any]

    validation_errors: List[str]
    validation_violations: List[Dict[str, str]]  # {"rule", "group", "path", "detail"}
    correction_history: List[str]
    retry_count: int

    #Episodic Memory
    episodic_config: Dict[str, Any]
    episodic_loop: bool
    episodic_paths: Dict[str, str]
    episodic_report: str
    episodic_delta: Dict[str, Any]  # delta entre S_k y el candidato rechazado
    episodic_reference_kpis: Dict[str, float]  # KPIs de S_k, contra los que se compara el candidato rechazado

    # Baseline xAI report (from initial JSON)
    baseline_report: str
    baseline_kpis: Dict[str, float]
    current_kpis: Dict[str, float]
    kpi_delta: Dict[str, Dict[str, Any]]
    reference_config: Dict[str, Any]  # configuración anterior a la optimización: referencia de los KPI de S*
    reference_kpis: Dict[str, float]  # KPIs de reference_config, calculados por el simulador
    report: str
    xai_failed: bool  # el xAI falló en esta consulta: /chat responde con success false

    # Benchmark Mode (skip deterministic validation)
    skip_deterministic_validation: bool

    # Token accounting for benchmark/diagnostics
    token_usage: Dict[str, int]

def get_llm():
    provider = (
        os.getenv("BENCHMARK_LLM_PROVIDER")
        or os.getenv("LLM_PROVIDER")
        or os.getenv("LLM_MODE")
        or "openai_compatible"
    )
    model_name = os.getenv("BENCHMARK_LLM_MODEL") or os.getenv("LLM_MODEL")
    base_url = os.getenv("BENCHMARK_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")

    llm_seed = None
    seed_raw = os.getenv("BENCHMARK_LLM_SEED") or os.getenv("LLM_SEED")
    if seed_raw not in (None, ""):
        try:
            llm_seed = int(seed_raw)
        except ValueError:
            llm_seed = None

    llm_temperature = 0.0
    temp_raw = os.getenv("BENCHMARK_LLM_TEMPERATURE") or os.getenv("LLM_TEMPERATURE")
    if temp_raw not in (None, ""):
        try:
            llm_temperature = float(temp_raw)
        except ValueError:
            llm_temperature = 0.0

    llm_timeout = None
    timeout_raw = os.getenv("BENCHMARK_LLM_TIMEOUT") or os.getenv("LLM_TIMEOUT")
    if timeout_raw not in (None, ""):
        try:
            llm_timeout = float(timeout_raw)
        except ValueError:
            llm_timeout = None

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    else:
        api_key = (
            os.getenv("OPENAI_COMPATIBLE_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OLLAMA_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
        )

    return LLMService(
        mode=provider,
        api_key=api_key,
        temperature=llm_temperature,
        seed=llm_seed,
        model=model_name,
        base_url=base_url,
        timeout=llm_timeout,
    )

def node_orchestrator(state: PetriState):
    logger.info(f"\n{Colors.HEADER}--- 🧠 ORQUESTANDO AGENTES ---{Colors.RESET}")

    user_msg = state["messages"][-1].content

    orchester = OrchesterAgent(get_llm())
    agent_queue = orchester.orchestrate(user_msg)

    return {
        "task_queue": agent_queue.steps,
        "retry_count": 0,
        "validation_violations": [],
        "episodic_delta": {},
        "episodic_reference_kpis": {},
        "reference_config": {},
        "reference_kpis": {},
        # execution_log acumula todas las consultas del hilo (operator.add): el chat solo lee desde aquí.
        "turn_log_start": len(state.get("execution_log", [])),
        "report": "",
        "episodic_report": "",
        "xai_failed": False,
        "correction_history": [],
        "context_data": ""
        }

def node_dispatcher(state: PetriState):
    """
    TRÁFICO: Saca la siguiente tarea de la cola y la activa.
    """
    queue = state.get("task_queue", [])
    
    if not queue:
        logger.info(f"\n{Colors.GREEN}🏁 Todas las tareas completadas. Esperando al usuario...{Colors.RESET}")
        return {"current_task": "__end__"}
    
    next_task = queue[0]
    remaining = queue[1:]
    
    logger.info(f"\n{Colors.BOLD}➡️ Despachando Agente: {next_task.upper()} (Pendientes: {len(remaining)}){Colors.RESET}")
    
    return {
        "current_task": next_task,
        "task_queue": remaining
    }

def node_chat(state: PetriState):
    """
    The only node that prints directly to the user.
    Its role is to humanize outcomes, not repeat technical reports.
    """
    logger.info("--- Chat Agent: generating final response ---")
    
    user_query = state["messages"][-1].content
    # Only this turn's log: execution_log accumulates every query of the thread.
    turn_logs = state.get("execution_log", [])[state.get("turn_log_start", 0):]
    logs = "\n- ".join(turn_logs)
    
    # Detect whether xAI or temporal_xai already ran in this turn.
    xai_executed = any(
        "xAI" in log or "✅ xAI" in log or "Temporal xAI" in log or "temporal_xai" in log
        or "Análisis temporal completado" in log
        for log in turn_logs
    )
    
    # Keep config summary short; this is just chat context.
    config_summary = "(Updated configuration available)" if state.get("current_config") else "(No changes)"

    xai_report = state.get("report", "")
    episodic_report = state.get("episodic_report", "")
    baseline_report = state.get("baseline_report", "")

    context_sections = [
        f"Config summary: {config_summary}",
        f"Validation errors: {state.get('validation_errors', [])}",
    ]

    # Critical rule: if xAI already ran, keep chat ultra-brief.
    if xai_executed:
        context_sections.append("IMPORTANT: A detailed xAI report has already been shown to the user. Do not repeat it. Provide only a human summary and clear next steps in 2-3 sentences.")
        current_report = episodic_report or xai_report
        if current_report:
            context_sections.append(f"Report of this query (for reference only): {current_report[:2000]}...")
    else:
        if baseline_report:
            context_sections.append(f"Baseline Report (for reference only): {baseline_report[:300]}...")
        if xai_report:
            context_sections.append(f"xAI Report (for reference only): {xai_report[:300]}...")
        if episodic_report:
            context_sections.append(f"Episodic Report (for reference only): {episodic_report[:300]}...")

    detailed_context = "\n\n".join(context_sections)

    chat_agent = ChatAgent(get_llm())
    response_data = chat_agent.generate_response(
        query=user_query,
        message_history=logs,
        context_info=detailed_context
    )

    if isinstance(response_data, dict) and response_data.get("error"):
        fallback_response = (
            "I could not structure the chat response right now, but the technical flow finished.\n\n"
            f"Technical detail: {response_data.get('error')}"
        )
        chat = ChatResponse(response=fallback_response)
    else:
        chat = ChatResponse(**response_data)

    md_response = Markdown(chat.response)
    
    console.print("\n")
    console.print(Panel(
        md_response, 
        title="[bold cyan]CDTO[/bold cyan]", 
        subtitle="[dim]Operator Assistant[/dim]",
        border_style="cyan",
        expand=False
    ))
    console.print("\n")

    return {
        "final_response": chat.response,
        "messages": [AIMessage(content=chat.response)],
        "execution_log": []
    }

def node_context(state: PetriState):
    """Lee el JSON base para dar contexto al usuario"""
    engine = PetriConfigEngine(state["current_config"])
    context = retrieve_context_data(get_llm(), state["messages"][-1].content, engine)
    return {"context_data": context, "execution_log": [f"Context updated with relevant information: {context[:200]}..."]}

def node_planner(state: PetriState):
    """Genera el JSON de cambios (ModificationBatch) pero NO lo aplica."""
    logger.info("--- 📝 PLANNER: Generando propuesta ---")

    planner_llm = get_llm()
    planner = PlannerAgent(planner_llm)
    
    msgs_content = [m.content for m in state["messages"][-5:]]
    full_context_query = "\n".join(msgs_content)
    history = "\n".join(state.get("correction_history", []))
    
    plan = planner.create_plan(
        user_query=full_context_query,
        context_str=state.get("context_data", ""),
        history_str=history
    )

    planner_usage = planner_llm.get_last_token_usage()
    existing_usage = state.get("token_usage", {"prompt": 0, "completion": 0, "total": 0})
    combined_usage = {
        "prompt": int(existing_usage.get("prompt", 0)) + int(planner_usage.get("prompt", 0)),
        "completion": int(existing_usage.get("completion", 0)) + int(planner_usage.get("completion", 0)),
        "total": int(existing_usage.get("total", 0)) + int(planner_usage.get("total", 0)),
    }
    
    logger.info(f"Plan propuesto: {plan}")

    return {
        "proposed_plan": plan,
        "execution_log": [f"Planner generó un plan de {len(plan)} pasos."],
        "token_usage": combined_usage,
    }

def node_executor(state: PetriState):
    """
    Intenta aplicar los cambios. Si falla, reprograma la cola.
    """
    logger.info(f"{Colors.CYAN}--- ⚙️ EXECUTOR: Validando y Aplicando ---{Colors.RESET}")
    
    proposed_plan = state.get("proposed_plan")
    if not proposed_plan:
        logger.warning("⚠️ No hay plan propuesto. Saltando...")
        return {"task_queue": [], "execution_log": ["Executor recibió una tarea vacía."]}

    if isinstance(proposed_plan, dict) and proposed_plan.get("error"):
        planner_error = str(proposed_plan.get("error"))
        logger.warning(f"⚠️ Planner devolvió error estructural: {planner_error}")
        return {
            "task_queue": [],
            "validation_errors": [f"Planner Error: {planner_error}"],
            "proposed_plan": None,
            "execution_log": ["Executor abortó porque el Planner devolvió un error de estructura."]
        }

    if not isinstance(proposed_plan, dict) or "instructions" not in proposed_plan:
        logger.warning("⚠️ Plan inválido recibido por Executor.")
        return {
            "task_queue": [],
            "validation_errors": ["Planner Error: plan inválido (faltan instrucciones)."],
            "proposed_plan": None,
            "execution_log": ["Executor abortó por plan inválido."]
        }

    if not proposed_plan.get("instructions"):
        logger.warning("⚠️ Planner no generó instrucciones aplicables.")
        return {
            "task_queue": [],
            "validation_errors": ["No se pudo generar una instrucción aplicable. Especifica el valor o la variable objetivo con más precisión."],
            "proposed_plan": None,
            "execution_log": ["Executor no aplicó cambios porque el plan llegó sin instrucciones."]
        }

    try:
        batch = ModificationBatch(**state["proposed_plan"])
    except Exception as e:
        logger.error(f"🔥 Error Crítico: {e}")
        return {"task_queue": [], "validation_errors": [str(e)], "execution_log": [f"Executor falló con error crítico: {e}"]}
    return _apply_batch(state, batch, actor="Executor")

def _apply_batch(state: PetriState, batch: ModificationBatch, actor: str) -> Dict[str, Any]:
    """Camino de todo cambio de configuración: rutas, copia de trabajo, chequeo determinista y
    commit o rechazo. Si el candidato solo viola reglas de DOMINIO se simula (simulator, xai,
    feedback); si viola alguna de RED DE PETRI o limites, solo pasa al feedback. Lo usan el
    executor (batches del planner) y el optimizador (S* como SET de las variables de decisión)."""
    try:
        skip_validation = state.get("skip_deterministic_validation", False)

        # Antes de aplicar nada: todas las rutas del batch tienen que resolver.
        if not skip_validation:
            unresolved = find_unresolved_routes(state["current_config"], batch)
            if unresolved:
                errors = [f"Ruta no resuelta ({u['kind']}): {u['operation']} {u['path']} {u['message']}".strip() for u in unresolved]
                logger.error(f"🔥 Error Crítico: rutas que no resuelven, no se aplica el batch. {errors}")
                return {"task_queue": [], "validation_errors": errors, "execution_log": [f"{actor} abortó sin aplicar el batch: rutas que no resuelven: {errors}"]}

        temp_engine = PetriConfigEngine(state["original_config"])
        temp_engine.data = copy.deepcopy(state["current_config"])
        new_data = temp_engine.apply_batch(batch)

        if skip_validation:
            logger.info(f"{Colors.YELLOW}⚠️  [BENCHMARK MODE] Saltando validación determinista.{Colors.RESET}")
            delta_struct = temp_engine.compute_delta(new_data)
            return {
                "current_config": new_data,
                "proposed_plan": None,
                "delta": delta_struct,
                "validation_errors": [],
                "retry_count": 0,
                "execution_log": [f"{actor} aplicó los cambios (benchmark mode, sin validación). Instrucciones: {batch.instructions}. "]
            }
        
        # Los IDs temporales del Planner (A002_new, T001_new) pasan a su formato canónico antes del chequeo.
        temp_engine.reindex_structure()

        validator = ValidatorEngine()
        is_valid, violations = validator.validate(batch, temp_engine, previous_config=state["current_config"])
        issues = [format_violation(v) for v in violations]

        if is_valid:
            logger.info(f"{Colors.GREEN}✅ Éxito: Configuración actualizada.{Colors.RESET}")
            delta_struct = temp_engine.compute_delta(new_data)
            logger.info(f"Delta computado: {delta_struct}")
            return {
                "current_config": new_data,
                "proposed_plan": None,
                "delta": delta_struct,
                "validation_errors": [],
                "validation_violations": [],
                "retry_count": 0,
                "execution_log": [f"{actor} aplicó los cambios exitosamente. Configuración actualizada con estas instrucciones: {batch.instructions}. "]
            }
        else:
            logger.warning(f"❌ Esa configuración que intentas poner no es válida. {issues}")

            if state["retry_count"] >= 3:
                logger.warning(f"💀 Se rindió tras 3 intentos. Abortando tareas restantes.")
                return {"task_queue": [], "validation_errors": issues, "validation_violations": violations, "execution_log": [f"{actor} abortó después de 3 intentos fallidos. Últimos issues: {issues}"]}

            # Delta entre la configuración actual (S_k) y el candidato rechazado, para la rutina de diagnóstico.
            episodic_delta = PetriConfigEngine(state["current_config"]).compute_delta(new_data)

            # No se simula el candidato si viola alguna regla de RED DE PETRI (la red no está bien
            # definida) o limites (protección contra entradas desmesuradas, que simularlo anularía).
            # El feedback recibe las violaciones estructuradas.
            if any(v["group"] == RED_DE_PETRI or v["rule"] == "limites" for v in violations):
                return {
                    "validation_errors": issues,
                    "validation_violations": violations,
                    "episodic_delta": episodic_delta,
                    "retry_count": state["retry_count"] + 1,
                    "task_queue": ["feedback"],
                    "episodic_loop": False,
                    "execution_log": [f"{actor} detectó violaciones que impiden simular el candidato (RED DE PETRI o limites): {issues}. No se simula el candidato rechazado; las violaciones pasan al feedback. Intento #{state['retry_count'] + 1}."]
                }

            # Solo reglas de DOMINIO: se mantiene el diseño anterior y se simula el candidato rechazado.
            logger.info(f"🔄 Inyectando sub-rutina de corrección...")
            
            recovery_steps = ["simulator", "xai", "feedback"]
            new_queue = recovery_steps

            return {
                "validation_errors": issues,
                "validation_violations": violations,
                "episodic_delta": episodic_delta,
                "retry_count": state["retry_count"] + 1,
                "task_queue": new_queue,
                "episodic_config": new_data,
                "episodic_loop": True,
                "execution_log": [f"{actor} detectó errores de validación: {issues}. Reprogramando tareas de recuperación: {recovery_steps}. Intento #{state['retry_count'] + 1}."]
            }

    except Exception as e:
        logger.error(f"🔥 Error Crítico: {e}")
        return {"task_queue": [], "validation_errors": [str(e)], "execution_log": [f"{actor} falló con error crítico: {e}"]}


def replacement_batch(current_config: Dict[str, Any], new_config: Dict[str, Any]) -> ModificationBatch:
    """Batch que convierte current_config en new_config: SET de cada clave de primer nivel nueva o
    cambiada y DELETE de las que desaparecen. Si así no quedara el orden de claves de new_config
    (el orden de las actividades fija su numeración en la red), se borran y se escriben todas."""
    kept_order = [key for key in current_config if key in new_config] + [key for key in new_config if key not in current_config]
    if kept_order == list(new_config):
        deleted = [key for key in current_config if key not in new_config]
        written = [key for key in new_config if key not in current_config or current_config[key] != new_config[key]]
    else:
        deleted, written = list(current_config), list(new_config)
    instructions = [{"operation": "DELETE", "path": key} for key in deleted]
    instructions += [{"operation": "SET", "path": key, "value": copy.deepcopy(new_config[key])} for key in written]
    return ModificationBatch(thought_process="Sustitución directa de la configuración.", instructions=instructions)

def apply_configuration(current_config: Dict[str, Any], new_config: Dict[str, Any], original_config: Dict[str, Any]) -> Dict[str, Any]:
    """Sustitución directa de la configuración (/config/update) por el camino de todo cambio: chequeo y
    commit, o rechazo con las violaciones. Devuelve la actualización de _apply_batch."""
    state = {"current_config": current_config, "original_config": original_config, "retry_count": 0}
    return _apply_batch(state, replacement_batch(current_config, new_config), actor="Config update")

def _feedback_from_violations(state: PetriState, episodic_store) -> Dict[str, Any]:
    """Feedback de un rechazo sin simulación (RED DE PETRI o limites): diagnostica a partir de las violaciones estructuradas,
    sin simulación, y actualiza la Memoria Episódica."""
    logger.info(f"{Colors.CYAN}--- 🩺 FEEDBACK: Diagnosticando violaciones (candidato no simulado) ---{Colors.RESET}")
    violations = state["validation_violations"]
    query = state["messages"][-1].content

    feedback_agent = FeedbackAgent(get_llm())
    analysis = feedback_agent.analyze_error(
        query=query, validation_issues=violations, episodic_report="", delta=state.get("episodic_delta")
    )

    csv_path = (state.get("episodic_paths") or {}).get("manual_csv")
    if csv_path:
        try:
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            pd.DataFrame([{"User Query": query, "Validation Errors": str(violations), "Diagnosis": str(analysis.diagnosis)}]).to_csv(
                csv_path, mode='a', header=not os.path.exists(csv_path), index=False, encoding='utf-8'
            )
        except Exception as e:
            logger.warning(f"{Colors.RED}⚠️ Error escribiendo CSV: {e}{Colors.RESET}")

    if episodic_store:
        try:
            episodic_store.add_fresh_memory(user_query=query, error_msg=str(violations), report=str(analysis.diagnosis))
        except Exception as e:
            logger.warning(f"{Colors.YELLOW}⚠️ No se pudo actualizar vector store: {e}{Colors.RESET}")

    msg = f"Intento #{state['retry_count']}: {analysis.diagnosis}. Sugerencia: {analysis.suggestion}"
    return {"correction_history": state.get("correction_history", []) + [msg], "execution_log": [f"Feedback Agent diagnosticó las violaciones del candidato no simulado. Diagnóstico: {analysis.diagnosis}. Sugerencia: {analysis.suggestion}"]}

def node_feedback(state: PetriState, config: RunnableConfig):
    """
    Analiza por qué falló el executor y actualiza la Memoria Episódica.
    """
    episodic_store = config["configurable"].get("episodic_store")

    # Rechazo sin simulación (RED DE PETRI o limites): no hubo simulación del candidato (el executor deja episodic_loop=False).
    if state.get("validation_violations") and not state.get("episodic_loop"):
        return _feedback_from_violations(state, episodic_store)

    if state["episodic_loop"]:
        
        logger.info(f"{Colors.CYAN}--- 🩺 FEEDBACK: Analizando Causa-Raíz (Forensic Mode) ---{Colors.RESET}")
        
        feedback_agent = FeedbackAgent(get_llm())
        analysis = feedback_agent.analyze_error(
            query=state["messages"][-1].content,
            validation_issues=state.get("validation_violations") or state["validation_errors"],
            episodic_report=state["episodic_report"],
            delta=state.get("episodic_delta"),
        )
        
        csv_path = state["episodic_paths"]["manual_csv"]
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        new_row_data = {
            "User Query": state["messages"][-1].content,
            "Validation Errors": str(state["validation_errors"]), 
            "Diagnosis": str(analysis.diagnosis)
        }
        
        try:
            df_log = pd.DataFrame([new_row_data])
            write_header = not os.path.exists(csv_path)
            
            df_log.to_csv(
                csv_path, 
                mode='a',
                header=write_header, 
                index=False,
                encoding='utf-8'
            )
            logger.info(f"{Colors.GREEN}💾 Log guardado en disco: '{csv_path}'{Colors.RESET}")
            
        except Exception as e:
            logger.warning(f"{Colors.RED}⚠️ Error escribiendo CSV: {e}{Colors.RESET}")

        if episodic_store:
            try:
                episodic_store.add_fresh_memory(
                    user_query=state["messages"][-1].content,
                    error_msg=str(state["validation_errors"]),
                    report=str(analysis.diagnosis)
                )
                logger.info(f"{Colors.CYAN}🧠 Memoria Vectorial actualizada (Gatekeeper informado).{Colors.RESET}")
            except Exception as e:
                logger.warning(f"{Colors.YELLOW}⚠️ No se pudo actualizar vector store: {e}{Colors.RESET}")

        msg = f"Intento #{state['retry_count']}: {analysis.diagnosis}. Sugerencia: {analysis.suggestion}"
        current_history = state.get("correction_history", [])
        logger.info(f"\n{Colors.YELLOW}🔎 REPORTE DE SIMULACIÓN PREDICTIVA{Colors.RESET}")
        logger.info(f"He analizado tu configuración y {Colors.BOLD}esto es lo que pasaría si la aplicamos:{Colors.RESET}")
        logger.info(f"\n{Colors.RED}❌ CONSECUENCIA:{Colors.RESET}") 
        logger.info(f"   {analysis.diagnosis}")
        
        logger.info(f"\n{Colors.GREEN}✅ CÓMO ARREGLARLO:{Colors.RESET}")
        logger.info(f"   {analysis.suggestion}")
        
        logger.info(f"\n{Colors.CYAN}🧠 (He aprendido de este error. Si vuelves a intentarlo igual, te avisaré antes.){Colors.RESET}\n")
        
        return {"correction_history": current_history + [msg], "execution_log": [f"Feedback Agent diagnosticó el error y generó una sugerencia. Último diagnóstico: {analysis.diagnosis}. Sugerencia: {analysis.suggestion}"]}

    else:
        logger.info(f"{Colors.CYAN}--- 🩺 FEEDBACK: Diagnosticando error de validación simple ---{Colors.RESET}")
        
        feedback_agent = FeedbackAgent(get_llm())
        delta_context = str(state.get("delta", {}))[:500] if state.get("delta") else "Sin delta disponible"
        analysis = feedback_agent.analyze_error(
            query=state["messages"][-1].content,
            validation_issues=state["validation_errors"],
            delta_info=delta_context
        )
        
        msg = f"Intento #{state['retry_count']}: {analysis.diagnosis}. Sugerencia: {analysis.suggestion}"
        return {"correction_history": [msg], "execution_log": [f"Feedback Agent diagnosticó el error simple. Diagnóstico: {analysis.diagnosis}. Sugerencia: {analysis.suggestion}"]}  
    
def _reference_kpis(config: Dict[str, Any]) -> Dict[str, float]:
    """KPIs de la configuración de referencia: S_k en la rutina de diagnóstico, la configuración
    anterior a la optimización tras el optimizador. Se simula en un directorio temporal para no pisar
    las salidas de la simulación principal, que el xAI lee del directorio de IO."""
    from input_agent.src.fresh_simulation import run_petrinets_simulation_fresh

    with tempfile.TemporaryDirectory(prefix="cdto_ref_", ignore_cleanup_errors=True) as io_dir:
        run_petrinets_simulation_fresh(input=config, info=None, silence=True, io_dir=io_dir)
        # Misma estructura que config/paths.py: <IO_DIR>/outputs/results/general_outputs_all.json
        return load_kpis_from_stats(os.path.join(io_dir, "outputs", "results", "general_outputs_all.json"))

def node_simulator(state: PetriState):
    """Se encarga de simular la PetriNet con los cambios del usuario ya integrados y validados"""
    logger.info(f"\n{Colors.GREEN}--- 🚀 INICIANDO SIMULADOR ---{Colors.RESET}")

    try:
        # Proceso nuevo por simulación: la red se reconstruye desde la configuración actual.
        from input_agent.src.fresh_simulation import run_petrinets_simulation_fresh

        target_config = state["episodic_config"] if state["episodic_loop"] else state["current_config"]
        mode_text = "Episódica" if state["episodic_loop"] else "Estándar"
        target_paths = state["episodic_paths"] if state["episodic_loop"] else state["simulation_paths"]

        with console.status(f"[bold green]Simulando ({mode_text})...[/bold green]", spinner="dots"):
            # Rutina de diagnóstico: el candidato rechazado se compara con S_k, no con S_0. Tras el
            # optimizador, S* se compara con la configuración anterior a la optimización.
            if state["episodic_loop"]:
                reference_kpis = _reference_kpis(state["current_config"])
                reference_text = "la configuración vigente (S_k)"
            elif state.get("reference_config"):
                reference_kpis = _reference_kpis(state["reference_config"])
                reference_text = "la configuración anterior a la optimización"
            else:
                reference_kpis = state.get("baseline_kpis", {})
                reference_text = "baseline"
            run_petrinets_simulation_fresh(input=target_config, info=None, silence=True)

        current_kpis = load_kpis_from_stats(target_paths.get("stats_json", ""))
        kpi_delta = compute_kpi_delta(reference_kpis, current_kpis) if reference_kpis else {}

        logger.info("--- ✅ SIMULACIÓN COMPLETADA ---")

        update = {
            "simulation_ready": True,
            "validation_errors": [],
            "current_kpis": current_kpis,
            "kpi_delta": kpi_delta,
            "execution_log": [
                f"Simulación ({mode_text}) ejecutada exitosamente.",
                f"KPIs detectados: {len(current_kpis)}.",
                f"Delta KPI calculado contra {reference_text}: {len(kpi_delta)} métricas."
            ]
        }
        if state["episodic_loop"]:
            update["episodic_reference_kpis"] = reference_kpis
        elif state.get("reference_config"):
            update["reference_kpis"] = reference_kpis
        return update

    except Exception as e:
        logger.error(f"Simulación fallida: {e}")
        return {
            "validation_errors": [f"Simulation Failed: {str(e)}"], 
            "execution_log": [f"Error crítico durante la simulación: {e}"]
        }

def node_xai(state: PetriState):
    """xAI agent que ofrece un overview general al usuario de KPI's obtenidos y 
    de la evolución temporal de los tokens. Enriquecido con delta de cambios."""
    logger.info(f"\n{Colors.MAGENTA}--- 🕵️ xAI FORENSIC ANALYSIS ---{Colors.RESET}")
    
    if not state.get("simulation_ready"):
        logger.warning(f"{Colors.YELLOW}⚠️  No hay simulación reciente. Por favor ejecuta 'simular' primero.{Colors.RESET}")
        console.print(f"\n{Colors.YELLOW}⚠️ No puedo explicar resultados sin una simulación previa. Primero ejecuta una simulación.{Colors.RESET}\n")
        return {"execution_log": ["xAI no se ejecutó porque no hay simulación reciente."]}

    try:
        from input_agent.src.narrativeProcess import xAI_simulation
        
        delta_info = state.get("delta", {})

        baseline_report = state.get("baseline_report", "")
        baseline_kpis = state.get("baseline_kpis", {})
        current_kpis = state.get("current_kpis", {})
        kpi_delta = state.get("kpi_delta", {})

        with console.status(f"[bold magenta]Generando análisis xAI...[/bold magenta]", spinner="dots"):
            if state["episodic_loop"]:
                paths = state.get("episodic_paths", {})
                # Delta entre S_k y el candidato rechazado, y las violaciones estructuradas.
                paths["delta"] = state.get("episodic_delta") or delta_info
                logger.info(f"Delta disponible para xAI (candidato rechazado frente a S_k): {paths['delta']}")
                paths["validation_violations"] = state.get("validation_violations", [])
                paths["baseline_report"] = baseline_report
                # La tabla de KPI compara el candidato con S_k (kpi_delta ya está calculado contra S_k).
                reference_kpis = state.get("episodic_reference_kpis")
                paths["baseline_kpis"] = reference_kpis or baseline_kpis
                if reference_kpis:
                    paths["kpi_reference"] = "current configuration S_k (before the rejected change)"
                else:
                    paths.pop("kpi_reference", None)
                paths["current_kpis"] = current_kpis
                paths["kpi_delta"] = kpi_delta
                episodic_report = xAI_simulation(input_data=paths)
                if not episodic_report:
                    return _xai_failed("el análisis episódico no devolvió informe.")

                console.print("\n")
                console.print(Panel(
                    Markdown(episodic_report),
                    title="[bold magenta]🕵️ xAI FORENSIC ANALYSIS (Episodic)[/bold magenta]",
                    subtitle="[dim]Causal Analysis Report[/dim]",
                    border_style="magenta",
                    expand=False
                ))
                console.print("\n")

                return {
                    "episodic_report": episodic_report,
                    "current_kpis": current_kpis,
                    "kpi_delta": kpi_delta,
                    "execution_log": [f"✅ xAI análisis episódico completado. Reporte mostrado arriba."]
                }
            else:
                paths = state.get("simulation_paths", {})
                paths["delta"] = delta_info  # Inyectar delta en metadatos
                logger.info(f"Delta disponible para xAI: {delta_info}")
                paths["baseline_report"] = baseline_report
                # Tras el optimizador, la tabla de KPI compara S* con la configuración anterior a la
                # optimización (kpi_delta ya está calculado contra ella).
                reference_kpis = state.get("reference_kpis")
                paths["baseline_kpis"] = reference_kpis or baseline_kpis
                if reference_kpis:
                    paths["kpi_reference"] = "configuration before the optimization"
                else:
                    paths.pop("kpi_reference", None)
                paths["current_kpis"] = current_kpis
                paths["kpi_delta"] = kpi_delta
                report = xAI_simulation(input_data=paths)
                if not report:
                    return _xai_failed("el análisis no devolvió informe.")

                console.print("\n")
                console.print(Panel(
                    Markdown(report),
                    title="[bold magenta]🕵️ xAI FORENSIC ANALYSIS[/bold magenta]",
                    subtitle="[dim]Causal Analysis Report[/dim]",
                    border_style="magenta",
                    expand=False
                ))
                console.print("\n")

                return {
                    "report": report,
                    "current_kpis": current_kpis,
                    "kpi_delta": kpi_delta,
                    "execution_log": [f"✅ xAI análisis completado. Reporte mostrado arriba."]
                }
        
    except ImportError:
         logger.warning(f"{Colors.RED}❌ Error: No se pudo importar 'xAI_simulation'.{Colors.RESET}")
         console.print(f"\n{Colors.RED}❌ Error: No se pudo importar el módulo xAI_simulation.{Colors.RESET}\n")
         return {"xai_failed": True, "execution_log": ["xAI no se pudo ejecutar porque no se pudo importar el módulo necesario."]}
    except Exception as e:
        logger.warning(f"Error en xAI: {e}")
        console.print(f"\n{Colors.RED}❌ Error en xAI: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        return {"xai_failed": True, "execution_log": [f"xAI falló con error: {e}"]}

def _xai_failed(detail: str) -> Dict[str, Any]:
    """xAI_simulation no devolvió informe (captura sus propios errores y devuelve None): el fallo
    queda en el log y en execution_log, y /chat responde con success false."""
    logger.error(f"❌ xAI falló: {detail}")
    console.print(f"\n{Colors.RED}❌ xAI falló: {detail}{Colors.RESET}\n")
    return {"xai_failed": True, "execution_log": [f"❌ xAI falló: {detail}"]}

def node_optimizer(state: PetriState):
    """Nodo de optimización de KPIs mediante lenguaje natural. S* (la configuración actual con las
    variables de decisión de la IWO) se aplica como un batch, por el mismo camino que el executor:
    copia de trabajo, chequeo y commit o rechazo, con las mismas consecuencias en la cola."""
    logger.info(f"\n{Colors.CYAN}--- 🎯 OPTIMIZER: Optimizando configuración ---{Colors.RESET}")

    user_query = state["messages"][-1].content

    optimizer_agent = OptimizerAgent(get_llm())

    with console.status(f"[bold cyan]Ejecutando optimización...[/bold cyan]", spinner="dots"):
        success, extracted_kpis, s_star, message = optimizer_agent.optimize(user_query, json_input=state["current_config"])

    execution_log = []
    if extracted_kpis:
        execution_log.append(f"✅ KPIs extraídos: {list(extracted_kpis.keys())}")

    if not success:
        execution_log.append(f"❌ {message}")
        logger.error(message)
        console.print(f"\n{Colors.RED}❌ {message}{Colors.RESET}\n")
        return {"execution_log": execution_log}

    execution_log.append(f"✅ {message}")
    if not s_star:
        console.print(f"\n{Colors.YELLOW}⚠️ {message}{Colors.RESET}\n")
        return {"execution_log": execution_log}

    batch = decision_batch(state["current_config"], s_star)
    if not batch.instructions:
        execution_log.append("La IWO no cambia ninguna variable de decisión: la configuración actual se mantiene.")
        return {"execution_log": execution_log}

    update = _apply_batch(state, batch, actor="Optimizer")
    update["execution_log"] = execution_log + update.get("execution_log", [])
    if "current_config" in update:
        # S* se simula y se explica antes del chat, frente a la configuración anterior a la optimización.
        update["delta"] = PetriConfigEngine(state["current_config"]).compute_delta(update["current_config"])
        update["reference_config"] = state["current_config"]
        remaining = [task for task in state.get("task_queue", []) if task not in ("simulator", "xai")]
        update["task_queue"] = ["simulator", "xai"] + remaining
        console.print("\n")
        console.print(Panel(
            f"[bold green]Optimización completada y S* aplicado tras el chequeo[/bold green]\n\n"
            f"KPIs extraídos: {list(extracted_kpis.keys())}\n"
            f"Variables de decisión cambiadas: {[i.path for i in batch.instructions]}",
            title="[bold cyan]🎯 OPTIMIZATION COMPLETE[/bold cyan]",
            border_style="cyan",
            expand=False
        ))
        console.print("\n")
    return update

def node_temporal_xai(state: PetriState):
    """Nodo de análisis temporal xAI: responde preguntas específicas sobre momentos temporales en la simulación."""
    logger.info(f"\n{Colors.MAGENTA}--- 🕰️ TEMPORAL xAI: Análisis temporal específico ---{Colors.RESET}")
    
    if not state.get("simulation_ready"):
        logger.warning(f"{Colors.YELLOW}⚠️ No hay simulación reciente para analizar temporalmente.{Colors.RESET}")
        console.print(f"\n{Colors.YELLOW}⚠️ No puedo analizar momentos temporales sin una simulación previa. Primero ejecuta una simulación.{Colors.RESET}\n")
        return {"execution_log": ["Temporal xAI no se ejecutó porque no hay simulación reciente."]}
    
    try:
        from input_agent.src.wiki import TXTWiki
        from input_agent.src.traceProcessor import TraceProcessor
        from input_agent.sub_agents.temporal_xai import TemporalXAIAgent
        
        user_query = state["messages"][-1].content
        
        # Determinar rutas según el tipo de simulación
        if state.get("episodic_loop"):
            paths = state.get("episodic_paths", {})
        else:
            paths = state.get("simulation_paths", {})
        
        # Extraer rutas necesarias
        M_k_path = paths.get('trace_csv', 'trace.csv')
        stats_json = paths.get('stats_json', 'stats.json')
        pdf_path = paths.get('manual_pdf', 'manual.pdf')
        dynamic_doc_path = paths.get('dynamic_documentation_txt', 'dynamic_doc.txt')  # Usar TXT para temporal xAI
        
        # Contexto de delta y baseline
        delta_info = state.get("delta", {})
        baseline_report = state.get("baseline_report", "")
        
        logger.info(f"Temporal xAI analyzing: M_k={M_k_path}, Stats={stats_json}, PDF={pdf_path}, Dynamic Doc={dynamic_doc_path}")
        
        with console.status(f"[bold magenta]Analizando ventana temporal...[/bold magenta]", spinner="dots"):
            # Inicializar componentes
            wiki = TXTWiki(dynamic_doc_path)
            trace_processor = TraceProcessor(M_k_path, stats_json)
            temporal_agent = TemporalXAIAgent(get_llm(), wiki)
            
            # Ejecutar análisis temporal
            temporal_report = temporal_agent.run(
                user_query=user_query,
                trace_processor=trace_processor,
                delta_context=delta_info if delta_info else None,
                baseline_report=baseline_report
            )
        
        if temporal_report:
            console.print("\n")
            console.print(Panel(
                Markdown(temporal_report),
                title="[bold magenta]🕰️ TEMPORAL ANALYSIS[/bold magenta]",
                subtitle="[dim]Focused Temporal Window Report[/dim]",
                border_style="magenta",
                expand=False
            ))
            console.print("\n")
            
            return {
                "report": temporal_report,
                "execution_log": [f"✅ Análisis temporal completado. Reporte mostrado arriba."]
            }
        else:
            console.print(f"\n{Colors.YELLOW}⚠️ No se pudo generar el reporte temporal.{Colors.RESET}\n")
            return {"execution_log": ["Temporal xAI completado pero no generó reporte."]}
    
    except ImportError as ie:
        logger.warning(f"{Colors.RED}❌ Error: No se pudieron importar módulos necesarios: {ie}{Colors.RESET}")
        console.print(f"\n{Colors.RED}❌ Error: Falta un módulo necesario para temporal xAI: {ie}{Colors.RESET}\n")
        return {"execution_log": [f"Temporal xAI falló por falta de módulos: {ie}"]}
    except Exception as e:
        logger.warning(f"Error en Temporal xAI: {e}")
        console.print(f"\n{Colors.RED}❌ Error en Temporal xAI: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        return {"execution_log": [f"Temporal xAI falló con error: {e}"]}

