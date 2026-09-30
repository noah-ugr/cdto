"""
Author: Noah Masegosa Caceres 
Center: @ugr | PhD Research in Agentic AI & Industry 5.0

=== COGNITIVE DIGITAL TWIN ORCHESTRATOR (CDTO) ===

Objective:
    To develop a self-correcting, neuro-symbolic multi-agent architecture capable of 
    managing complex Digital Twins (Petri Nets) through Natural Language.
    
    This framework addresses the "Stochastic-Deterministic Gap" in Industry 5.0:
    bridging the semantic flexibility of Large Language Models (LLMs) with the 
    strict constraints of industrial simulation engines, ensuring zero-hallucination 
    structural edits while providing causal explainability to human operators.

Research Roadmap & Modules (The "Three Pillars"):
    1. ROBUSTNESS: A 'Planner-Executor-Validator' loop implementing the 
       Reflexion pattern. It guarantees that stochastic LLM plans are validated 
       against deterministic logic (PetriConfigEngine) before application.
       
    2. EXPLAINABILITY: A Causal xAI Agent that translates low-level 
       simulation logs and validation errors into human-readable narratives, 
       empowering operators to understand bottlenecks and deadlocks.
       
    3. OPTIMIZATION: An autonomous Optimization Agent (Future Integration) 
       that iteratively tunes simulation parameters (firing times, resources) to 
       maximize KPIs based on high-level user intent.

Architecture Workflow (Configurable Graph Factory):
    The system operates as a Modular State Graph (LangGraph), allowing for 
    'Ablation Studies' by dynamically enabling/disabling components via ResearchConfig flags.

    1. Intent Routing: 
       The Router classifies user input (Modification, Simulation, Explanation) to 
       activate specific sub-graphs.

    2. Neuro-Symbolic Planning (The Brain):
       - Input: Natural Language Query + Episodic Memory (Past Errors).
       - Output: A structured Domain Specific Language (ModificationBatch). 
       - Constraint: The LLM never edits the raw JSON directly.

    3. Deterministic Execution (The Body):
       - The 'PetriConfigEngine' applies the DSL to the Digital Twin state.
       - A 'ValidatorEngine' runs strict mathematical checks (Cycles, Deadlocks, Schema).

    4. Self-Correction Loop (Reflexion):
       - If Validation Fails: The 'Feedback Agent' translates the traceback into 
         semantically rich instructions. The Planner retries (up to N times).
       - Result: Maximizes 'Structural Validity Rate' without human intervention.

    5. Simulation & Causal Analysis:
       - Runs the external Petri Net Simulator.
       - The xAI Agent performs forensic analysis on traces to explain *why* a configuration succeeded or failed (Causal Inference).

Key Features for Research:
    - Modular Architecture: Supports ablation testing (e.g., measuring success rate 
      with vs. without Feedback Loop).
    - Episodic Memory (RAG): Stores |Query|Error|Correction| vectors to prevent 
      repeating historical mistakes.
    - Human-in-the-Loop: Designed for Industry 5.0 collaboration, offering 
      interruptibility and explanation before final commit.

Current Status:
    - Phase: Proof of Concept (PoC) / Monolithic Research Prototype.
    - Implementation: Hybrid Neuro-Symbolic Agent via LangGraph.
"""

import os
import sys
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

from config.paths import EPISODIC_FAILURES_CSV, GENERAL_OUTPUTS_JSON, PETRI_VARIABLES_PDF, SIM_OUTPUT_XLSX
from input_agent.src.models import Colors
from input_agent.src.wiki import EpisodicCSVWiki
from input_agent.src.narrativeProcess import xAI_simulation, load_kpis_from_stats
from input_agent.src.fresh_simulation import run_petrinets_simulation_fresh
from input_agent.nodes import PetriState
from input_agent.nodes import (
    node_orchestrator,
    node_dispatcher,
    node_context,
    node_planner,
    node_executor,
    node_feedback,
    node_simulator,
    node_xai,
    node_temporal_xai,
    node_optimizer,
    node_chat
)

def build_interactive_graph():
    """
    Construye el Grafo de Estados con arquitectura:
    Entry -> Orchestrator -> Dispatcher <-> Workers -> End
    """
    workflow = StateGraph(PetriState)
    
    workflow.add_node("orchestrator", node_orchestrator)
    workflow.add_node("dispatcher", node_dispatcher)
    workflow.add_node("chat", node_chat)
    
    workflow.add_node("context", node_context)
    workflow.add_node("planner", node_planner)
    workflow.add_node("executor", node_executor)
    workflow.add_node("feedback", node_feedback)
    workflow.add_node("simulator", node_simulator)
    workflow.add_node("xai", node_xai)
    workflow.add_node("temporal_xai", node_temporal_xai)
    workflow.add_node("optimizer", node_optimizer)
    
    workflow.set_entry_point("orchestrator")
    workflow.add_edge("orchestrator", "dispatcher")

    def router_logic(state):
        task = state.get("current_task")
        if task == "__end__":
            return "chat"
        return task
    
    workflow.add_conditional_edges(
        "dispatcher",
        router_logic,
        {
            "planner": "planner",
            "executor": "executor",
            "feedback": "feedback",
            "simulator": "simulator",
            "xai": "xai",
            "temporal_xai": "temporal_xai",
            "context": "context",
            "optimizer": "optimizer",
            "chat": "chat",
        }
    )

    workflow.add_edge("planner", "dispatcher")
    workflow.add_edge("executor", "dispatcher")
    workflow.add_edge("feedback", "dispatcher")
    workflow.add_edge("simulator", "dispatcher")
    workflow.add_edge("xai", "dispatcher")
    workflow.add_edge("temporal_xai", "dispatcher")
    workflow.add_edge("context", "dispatcher")
    workflow.add_edge("optimizer", "dispatcher")
    
    workflow.add_edge("chat", END)

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    try:
        graph_image = app.get_graph().draw_mermaid_png()
        with open(f"agent_FULL.png", "wb") as f:
            f.write(graph_image)   
        print(f"\n{Colors.GREEN}✨ Gráfico generado correctamente: 'agent_FULL.png'{Colors.RESET}")
                
    except Exception as e:
        print(f"\n{Colors.YELLOW}⚠️ No se pudo generar la imagen PNG. Copia este código en mermaid.live:{Colors.RESET}")
        print(app.get_graph().draw_mermaid())

    return app

if __name__ == "__main__":
    load_dotenv()
    
    initial_input = {
    "runId": 16,
    "Teams": 1,
    "Simulation_period": 2160,
    "A001": {
        "tasks": {
        "T001": {
            "Duration": 6,
            "Requires_Shutdown": False
        },
        "T002": {
            "Duration": 8,
            "Requires_Shutdown": True
        },
        "T003": {
            "Duration": 11,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T002"]
        },
        "T004": {
            "Duration": 13,
            "Requires_Shutdown": True,
            "taskDependency": True,
            "taskCode": ["T003"]
        },
        "T005": {
            "Duration": 15,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T004", "T002"]
        },
        "T006": {
            "Duration": 17,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T005"]
        },
        "T007": {
            "Duration": 5,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T006"]
        },
        "T008": {
            "Duration": 7,
            "Requires_Shutdown": True,
            "taskDependency": True,
            "taskCode": ["T007"]
        },
        "T009": {
            "Duration": 9,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T008"]
        },
        "T010": {
            "Duration": 11,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T009", "T002"]
        },
        "T011": {
            "Duration": 13,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T010"]
        },
        "T012": {
            "Duration": 15,
            "Requires_Shutdown": True,
            "taskDependency": True,
            "taskCode": ["T011"]
        },
        "T013": {
            "Duration": 17,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T012"]
        },
        "T014": {
            "Duration": 5,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T013"]
        },
        "T015": {
            "Duration": 7,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T014", "T002"]
        }
        },
        "T_period": 720,
        "T_wait": 4,
        "Start_disp": 12,
        "Team": "TeamA",
        "Team members": 3,
        "Shift_duration": 8
    },
    "A002": {
        "tasks": {
        "T001": {
            "Duration": 10,
            "Requires_Shutdown": False
        },
        "T002": {
            "Duration": 14,
            "Requires_Shutdown": True,
            "taskDependency": True,
            "taskCode": ["T001"]
        },
        "T003": {
            "Duration": 18,
            "Requires_Shutdown": False,
            "taskDependency": True,
            "taskCode": ["T001"]
        }
        },
        "T_period": 720,
        "T_wait": 8,
        "Start_disp": 100,
        "Team": "TeamA",
        "Team members": 3,
        "Shift_duration": 8,
        "activityDependency": True,
        "activityCode": ["A001"]
    }
    }


    simulation_paths = {
        "trace_csv": str(SIM_OUTPUT_XLSX),
        "stats_json": str(GENERAL_OUTPUTS_JSON),
        "manual_pdf": str(PETRI_VARIABLES_PDF),
    }

    episodic_paths = {
        "trace_csv": str(SIM_OUTPUT_XLSX),
        "stats_json": str(GENERAL_OUTPUTS_JSON),
        "manual_csv": str(EPISODIC_FAILURES_CSV),
        "manual_pdf": str(PETRI_VARIABLES_PDF),
    }

    app = build_interactive_graph()

    try:
        episodic_memory = EpisodicCSVWiki(episodic_paths["manual_csv"])
        store = episodic_memory
    except:
        store = None

    baseline_report = ""
    baseline_kpis = {}
    baseline_simulation_ready = False
    try:
        print(f"\n{Colors.CYAN}🧪 Ejecutando simulacion base (JSON inicial)...{Colors.RESET}")
        run_petrinets_simulation_fresh(input=initial_input, info=None, silence=True)
        baseline_simulation_ready = True 
        baseline_paths = dict(simulation_paths)
        baseline_paths["delta"] = {}
        baseline_kpis = load_kpis_from_stats(simulation_paths["stats_json"])
        baseline_paths["baseline_kpis"] = baseline_kpis
        baseline_paths["current_kpis"] = baseline_kpis
        baseline_paths["kpi_delta"] = {}
        baseline_report = xAI_simulation(input_data=baseline_paths) or ""
        if baseline_report:
            print(f"{Colors.GREEN}✅ Reporte xAI base guardado en memoria.{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}⚠️ Reporte xAI base vacio o no disponible.{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️ No se pudo generar el reporte xAI base: {e}{Colors.RESET}")

    thread_id = "session_dev_01"
    config = {"configurable": {"thread_id": thread_id, "episodic_store": store}}
    last_known_config = initial_input
    last_simulation_ready = baseline_simulation_ready  
    
    print(f"\n{Colors.HEADER}=== CDTO: SYSTEM ONLINE ==={Colors.RESET}")
    
    while True:
        try:
            user_input = input(f"\n{Colors.BOLD}Usuario > {Colors.RESET}").strip()
            
            if not user_input: continue

            if user_input.lower() in ["salir", "exit", "quit"]:
                print(f"{Colors.YELLOW}💾 Guardando configuración y cerrando...{Colors.RESET}")
                with open("final_config.json", "w") as f:
                    json.dump(last_known_config, f, indent=2)
                break
            
            if store:
                past_trauma = store.consult_failures(user_input, score_threshold=0.35)
                if past_trauma:
                    print(f"\n{Colors.RED}⛔ ALERTA DE MEMORIA EPISÓDICA:{Colors.RESET}")
                    print(f"Detecté un patrón similar a un fallo previo:\n{past_trauma}")
                    confirm = input(f"{Colors.YELLOW}¿Proceder de todas formas? (s/n): {Colors.RESET}")
                    if confirm.lower() != 's':
                        continue

            input_state = {
                "messages": [HumanMessage(content=user_input)],
                "current_config": last_known_config,
                "baseline_report": baseline_report,
                "baseline_kpis": baseline_kpis,
                "current_kpis": baseline_kpis,
                "kpi_delta": {},
                
                "original_config": initial_input,
                "simulation_paths": simulation_paths,
                "episodic_paths": episodic_paths,
                "simulation_ready": last_simulation_ready,  
                
                "retry_count": 0,        
                "validation_errors": [],
                "episodic_loop": False
            }
            
            final_state = app.invoke(input_state, config=config)
            
            last_known_config = final_state["current_config"]
            
            last_simulation_ready = final_state.get("simulation_ready", last_simulation_ready)
            
            if not baseline_report and final_state.get("report"):
                baseline_report = final_state["report"]

            if final_state.get("baseline_kpis"):
                baseline_kpis = final_state["baseline_kpis"]

            if final_state.get("validation_errors") and len(final_state["validation_errors"]) > 0:
                 print(f"{Colors.DIM}(System Note: Ciclo terminó con flags de error activos){Colors.RESET}")

        except Exception as e:
            print(f"\n{Colors.RED}🔥 CRITICAL KERNEL PANIC: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
