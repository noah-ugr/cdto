"""
FastAPI backend for the CDTO (Cognitive Digital Twin Orchestrator) demo.
Exposes endpoints to interact with agent.py via HTTP REST.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import os
import sys
import socket
from dotenv import load_dotenv
import logging
from pathlib import Path

# Allows running this file directly (python core/api.py)
# ensuring the repo root is in sys.path for absolute imports.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

from config.paths import (  # noqa: E402 - repo root is inserted before first-party imports for direct execution.
    DYNAMIC_DOCUMENTATION_MD,
    DYNAMIC_DOCUMENTATION_TXT,
    EPISODIC_FAILURES_CSV,
    GENERAL_OUTPUTS_JSON,
    PETRI_VARIABLES_PDF,
    RESULTS_DIR,
    SIM_OUTPUT_XLSX,
    VISUALIZATION_METADATA_JSON,
)


# ============== PYDANTIC MODELS ==============
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "session_web_demo"
    include_episodic_memory: bool = True


class ChatResponse(BaseModel):
    response: str
    success: bool
    execution_log: List[str] = []
    validation_errors: List[str] = []
    validation_violations: List[Dict[str, str]] = []  # {"rule", "group", "path", "detail"}
    current_config: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    xai_report: Optional[str] = None
    episodic_xai_report: Optional[str] = None
    visualizations: Optional[Dict[str, Any]] = None
    baseline_kpis: Optional[Dict[str, float]] = None
    current_kpis: Optional[Dict[str, float]] = None
    kpi_delta: Optional[Dict[str, Dict[str, Any]]] = None


class ConfigRequest(BaseModel):
    config: Dict[str, Any]
    thread_id: Optional[str] = "session_web_demo"


class SimulationRequest(BaseModel):
    config: Dict[str, Any]
    simulation_period: int = 2000
    thread_id: Optional[str] = "session_web_demo"


class OptimizationRequest(BaseModel):
    query: str
    optimizer: str = "iwo"  # "iwo" or "qga"
    config: Optional[Dict[str, Any]] = None
    thread_id: Optional[str] = "session_web_demo"


class OptimizationResponse(BaseModel):
    success: bool
    optimized_config: Optional[Dict[str, Any]] = None
    extracted_kpis: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    execution_log: List[str] = []


# ============== INITIALIZE FASTAPI ==============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle (startup/shutdown) without deprecated on_event."""
    try:
        app_state.initialize()
        logger.info("🚀 CDTO API started successfully")
        yield
    except Exception as e:
        logger.error(f"❌ Initialization error: {e}")
        raise


app = FastAPI(
    title="CDTO API Demo",
    description="API for Cognitive Digital Twin Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)

PROJECT_ROOT = Path(__file__).resolve().parent
ALLOWED_IMAGE_ROOTS = (
    PROJECT_ROOT,
    RESULTS_DIR,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== GLOBAL STATE ==============
class AppState:
    def __init__(self):
        self.graph = None
        self.episodic_store = None
        self.initial_input = None
        self.last_config = None
        self.baseline_report = ""
        self.baseline_kpis = {}
        self.current_kpis = {}
        self.kpi_delta = {}
        self.baseline_generated = False
        self.simulation_ready = False
        self.thread_id = "session_web_demo"
        self.config = {}
        self.last_visualizations = None

    def _simulation_paths(self):
        return {
            "trace_csv": str(SIM_OUTPUT_XLSX),
            "stats_json": str(GENERAL_OUTPUTS_JSON),
            "manual_pdf": str(PETRI_VARIABLES_PDF),
            "dynamic_documentation": str(DYNAMIC_DOCUMENTATION_MD),
            "dynamic_documentation_txt": str(DYNAMIC_DOCUMENTATION_TXT),
        }

    def _episodic_paths(self):
        return {
            "trace_csv": str(SIM_OUTPUT_XLSX),
            "stats_json": str(GENERAL_OUTPUTS_JSON),
            "manual_csv": str(EPISODIC_FAILURES_CSV),
            "manual_pdf": str(PETRI_VARIABLES_PDF),
            "dynamic_documentation": str(DYNAMIC_DOCUMENTATION_MD),
            "dynamic_documentation_txt": str(DYNAMIC_DOCUMENTATION_TXT),
        }

    def _load_visualizations(self):
        """Load visualization metadata from the JSON file."""
        viz_path = VISUALIZATION_METADATA_JSON
        try:
            if viz_path.exists():
                import json

                with open(viz_path, "r", encoding="utf-8") as f:
                    self.last_visualizations = json.load(f)
                    logger.info(
                        f"✅ Visualizations loaded: {len(self.last_visualizations.get('gantt_charts', []))} Gantt charts"
                    )
                    return self.last_visualizations
        except Exception as e:
            logger.warning(f"⚠️ Could not load visualizations: {e}")
        self.last_visualizations = None
        return None

    def ensure_baseline_report(self):
        if self.baseline_generated and self.baseline_report:
            return self.baseline_report

        from input_agent.src.narrativeProcess import xAI_simulation, load_kpis_from_stats
        from input_agent.src.fresh_simulation import run_petrinets_simulation_fresh

        simulation_paths = self._simulation_paths()
        try:
            logger.info("🧪 Generating baseline (cold start) on demand...")
            run_petrinets_simulation_fresh(input=self.initial_input, info=None, silence=True)
            baseline_paths = dict(simulation_paths)
            baseline_paths["delta"] = {}
            self.baseline_kpis = load_kpis_from_stats(simulation_paths["stats_json"])
            baseline_paths["baseline_kpis"] = self.baseline_kpis
            baseline_paths["current_kpis"] = self.baseline_kpis
            baseline_paths["kpi_delta"] = {}
            self.baseline_report = xAI_simulation(input_data=baseline_paths) or ""
            self.baseline_generated = True
            self.simulation_ready = True  # Baseline simulation completed
            self.current_kpis = self.baseline_kpis
            self.kpi_delta = {}

            # Load generated visualizations
            self._load_visualizations()

            if self.baseline_report:
                logger.info("✅ Baseline (cold start) generated")
            else:
                logger.warning("⚠️ Baseline generated with no content")
                self.baseline_report = ""
        except Exception as e:
            logger.warning(f"⚠️ Could not generate baseline (cold start): {e}")
            self.baseline_report = ""

        return self.baseline_report

    def initialize(self):
        """Initialize the application with default settings."""
        logger.info("Initializing CDTO...")

        from input_agent.agent import build_interactive_graph
        from input_agent.src.wiki import EpisodicCSVWiki
        from utils.automatic_documentation import (
            generate_petri_net_documentation,
            generate_petri_net_documentation_txt,
        )

        # Default configuration
        self.initial_input = {
            "runId": 25,
            "Teams": 1,
            "Simulation_period": 2000,
            "A001": {
                "tasks": {
                    "T001": {"Duration": 10, "Requires_Shutdown": False},
                    "T002": {"Duration": 30, "Requires_Shutdown": True},
                    "T003": {
                        "Duration": 40,
                        "Requires_Shutdown": False,
                        "taskDependency": True,
                        "taskCode": ["T001", "T002"],
                    },
                },
                "T_period": 480,
                "T_wait": 2,
                "Start_disp": 3,
                "Team": "TeamA",
                "Team members": 2,
                "Shift_duration": 8,
            },
            "A002": {
                "tasks": {
                    "T001": {"Duration": 80, "Requires_Shutdown": False},
                    "T002": {
                        "Duration": 100,
                        "Requires_Shutdown": False,
                        "taskDependency": True,
                        "taskCode": ["T001"],
                    },
                    "T003": {
                        "Duration": 60,
                        "Requires_Shutdown": True,
                        "taskDependency": True,
                        "taskCode": ["T001"],
                    },
                    "T004": {
                        "Duration": 10,
                        "Requires_Shutdown": False,
                        "taskDependency": True,
                        "taskCode": ["T002", "T003"],
                    },
                },
                "T_period": 720,
                "T_wait": 4,
                "Start_disp": 1,
                "Team": "TeamA",
                "Team members": 2,
                "Shift_duration": 8,
                "activityDependency": True,
                "activityCode": ["A001"],
            },
        }

        markdown_doc = generate_petri_net_documentation(self.initial_input)
        txt_doc = generate_petri_net_documentation_txt(self.initial_input)

        self.last_config = self.initial_input.copy()

        # Simulation paths
        simulation_paths = self._simulation_paths()
        episodic_paths = self._episodic_paths()

        doc_path = Path(simulation_paths["dynamic_documentation"])
        txt_doc_path = Path(simulation_paths["dynamic_documentation_txt"])
        try:
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            txt_doc_path.parent.mkdir(parents=True, exist_ok=True)

            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(markdown_doc)
            logger.info(f"✅ Dynamic documentation generated at: {doc_path}")

            with open(txt_doc_path, "w", encoding="utf-8") as f:
                f.write(txt_doc)
            logger.info(f"✅ Dynamic TXT documentation generated at: {txt_doc_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save dynamic documentation: {e}")

        # Build graph
        logger.info("📦 Loading CDTO agent...")
        self.graph = build_interactive_graph()
        logger.info("✅ Agent loaded successfully")

        # Load episodic memory (lazy fallback if it fails)
        try:
            logger.info("🧠 Loading episodic memory...")
            self.episodic_store = EpisodicCSVWiki(episodic_paths["manual_csv"])
            logger.info("✅ Episodic memory loaded")
        except Exception as e:
            logger.warning(f"⚠️ Episodic memory not available: {e}")
            self.episodic_store = None

        # Note: The baseline report is generated on demand in /simulation/baseline
        # It is not generated at startup to keep initialization fast
        logger.info("⏭️  Baseline report (cold start) available on demand")

        # Configure execution context
        self.config = {
            "configurable": {"thread_id": self.thread_id, "episodic_store": self.episodic_store}
        }


app_state = AppState()


def find_available_port(host: str, preferred_port: int, max_tries: int = 10) -> int:
    """Finds a free port starting from preferred_port."""
    bind_host = "" if host == "0.0.0.0" else host
    for offset in range(max_tries):
        port = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((bind_host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(
        f"No free port found in range {preferred_port}-{preferred_port + max_tries - 1}"
    )


# ============== ENDPOINTS ==============


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "cdto_ready": app_state.graph is not None,
        "episodic_memory": app_state.episodic_store is not None,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main endpoint: send a query to the agent.
    """
    try:
        from langchain_core.messages import HumanMessage

        if not app_state.graph:
            raise HTTPException(status_code=503, detail="CDTO not initialized")

        thread_id = request.thread_id or "session_web_demo"
        user_message = request.message.strip()

        if not user_message:
            raise HTTPException(status_code=400, detail="Empty message")

        cold_start_note = ""
        if not app_state.baseline_report:
            baseline = app_state.ensure_baseline_report()
            if baseline:
                cold_start_note = f"{baseline}\n\n"

        # Prepare graph input
        input_state = {
            "messages": [HumanMessage(content=user_message)],
            "current_config": app_state.last_config,
            "baseline_report": app_state.baseline_report,
            "baseline_kpis": app_state.baseline_kpis,
            "current_kpis": app_state.current_kpis,
            "kpi_delta": app_state.kpi_delta,
            "simulation_ready": app_state.simulation_ready,
            "original_config": app_state.initial_input,
            "simulation_paths": {
                "trace_csv": str(SIM_OUTPUT_XLSX),
                "stats_json": str(GENERAL_OUTPUTS_JSON),
                "manual_pdf": str(PETRI_VARIABLES_PDF),
                "dynamic_documentation": str(DYNAMIC_DOCUMENTATION_MD),
                "dynamic_documentation_txt": str(DYNAMIC_DOCUMENTATION_TXT),
            },
            "episodic_paths": {
                "trace_csv": str(SIM_OUTPUT_XLSX),
                "stats_json": str(GENERAL_OUTPUTS_JSON),
                "manual_csv": str(EPISODIC_FAILURES_CSV),
                "manual_pdf": str(PETRI_VARIABLES_PDF),
                "dynamic_documentation": str(DYNAMIC_DOCUMENTATION_MD),
                "dynamic_documentation_txt": str(DYNAMIC_DOCUMENTATION_TXT),
            },
            "retry_count": 0,
            "validation_errors": [],
            "episodic_loop": False,
        }

        # Invoke graph
        config = {
            "configurable": {
                "thread_id": thread_id,
                "episodic_store": app_state.episodic_store
                if request.include_episodic_memory
                else None,
            }
        }
        final_state = app_state.graph.invoke(input_state, config=config)

        # Update latest configuration
        if "current_config" in final_state:
            app_state.last_config = final_state["current_config"]

        # Update simulation_ready if a simulation was executed
        if final_state.get("simulation_ready"):
            app_state.simulation_ready = True

        if "baseline_kpis" in final_state and final_state.get("baseline_kpis"):
            app_state.baseline_kpis = final_state["baseline_kpis"]
        if "current_kpis" in final_state and final_state.get("current_kpis") is not None:
            app_state.current_kpis = final_state["current_kpis"]
        if "kpi_delta" in final_state and final_state.get("kpi_delta") is not None:
            app_state.kpi_delta = final_state["kpi_delta"]

        # Get final response
        response_text = final_state.get("final_response", "")
        if not response_text and final_state.get("messages"):
            last_msg = final_state["messages"][-1]
            response_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        if cold_start_note:
            response_text = f"{cold_start_note}{response_text}"

        # Extract xAI reports from state (if present)
        xai_report = final_state.get("report", None)
        episodic_xai_report = final_state.get("episodic_report", None)

        # Load visualizations if an xAI report was generated
        if xai_report or episodic_xai_report:
            app_state._load_visualizations()

        # A failed xAI (no report) is not a successful turn, even if the rest of the flow finished.
        xai_failed = bool(final_state.get("xai_failed"))

        return ChatResponse(
            response=response_text,
            success=not xai_failed,
            message="The xAI analysis failed and produced no report; see execution_log."
            if xai_failed
            else None,
            execution_log=final_state.get("execution_log", []),
            validation_errors=final_state.get("validation_errors", []),
            current_config=final_state.get("current_config"),
            xai_report=xai_report if xai_report else None,
            episodic_xai_report=episodic_xai_report if episodic_xai_report else None,
            visualizations=app_state.last_visualizations,
            baseline_kpis=final_state.get("baseline_kpis", app_state.baseline_kpis),
            current_kpis=final_state.get("current_kpis", app_state.current_kpis),
            kpi_delta=final_state.get("kpi_delta", app_state.kpi_delta),
        )

    except Exception as e:
        logger.error(f"Error in /chat: {e}", exc_info=True)
        return ChatResponse(response="", success=False, message=f"Error: {e!s}")


@app.post("/config/current")
async def get_current_config():
    """Get the current configuration."""
    return {"config": app_state.last_config, "baseline_available": bool(app_state.baseline_report)}


@app.post("/config/update", response_model=ChatResponse)
async def update_config(request: ConfigRequest):
    """Replace the configuration through the same path as any change (input_agent.nodes._apply_batch):
    the candidate is checked and committed, or rejected with its violations and the current
    configuration kept."""
    try:
        from input_agent.nodes import apply_configuration

        update = apply_configuration(app_state.last_config, request.config, app_state.initial_input)
        if "current_config" in update:
            app_state.last_config = update["current_config"]
            logger.info("Configuration updated")
            return ChatResponse(
                response="Configuration updated successfully",
                success=True,
                execution_log=update.get("execution_log", []),
                current_config=app_state.last_config,
            )
        logger.warning(f"Configuration rejected: {update.get('validation_errors')}")
        return ChatResponse(
            response="",
            success=False,
            message="Configuration rejected by the check; the current configuration is kept.",
            execution_log=update.get("execution_log", []),
            validation_errors=update.get("validation_errors", []),
            validation_violations=update.get("validation_violations", []),
            current_config=app_state.last_config,
        )
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return ChatResponse(response="", success=False, message=f"Error: {e!s}")


@app.post("/config/reset")
async def reset_config():
    """Reset to the initial configuration."""
    try:
        app_state.last_config = app_state.initial_input.copy()
        logger.info("Configuration reset")
        return {
            "success": True,
            "message": "Configuration reset to initial values",
            "config": app_state.last_config,
        }
    except Exception as e:
        logger.error(f"Error resetting: {e}")
        return {"success": False, "message": f"Error: {e!s}"}


@app.get("/simulation/baseline")
async def get_baseline_report():
    """Get the baseline xAI report."""
    if not app_state.baseline_report:
        app_state.ensure_baseline_report()

    return {
        "baseline_report": app_state.baseline_report,
        "baseline_kpis": app_state.baseline_kpis,
        "available": bool(app_state.baseline_report),
    }


@app.get("/simulation/visualizations")
async def get_visualizations():
    """Get visualizations generated by the latest simulation."""
    if not app_state.last_visualizations:
        app_state._load_visualizations()

    return {
        "visualizations": app_state.last_visualizations,
        "available": bool(app_state.last_visualizations),
    }


@app.post("/session/new")
async def new_session(thread_id: str = "session_web_demo"):
    """Create a new session."""
    app_state.thread_id = thread_id
    app_state.last_config = app_state.initial_input.copy()
    app_state.config = {
        "configurable": {"thread_id": thread_id, "episodic_store": app_state.episodic_store}
    }
    logger.info(f"New session created: {thread_id}")
    return {"success": True, "thread_id": thread_id, "message": f"New session created: {thread_id}"}


@app.get("/info")
async def get_info():
    """Get information about CDTO."""
    return {
        "name": "CDTO - Cognitive Digital Twin Orchestrator",
        "version": "1.0.0",
        "description": "Multi-agent architecture for managing Petri nets through natural language",
        "capabilities": [
            "Configuration updates via NLP",
            "Change validation",
            "Petri net simulation",
            "Causal analysis (xAI)",
            "Episodic memory (error prevention)",
            "KPI optimization through natural language",
        ],
        "status": "online" if app_state.graph else "offline",
    }


@app.get("/assets/image")
async def get_image(path: str):
    """Serve local images generated by simulations for frontend display."""
    try:
        requested_path = Path(path).expanduser().resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image path") from None

    if requested_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    is_allowed = any(
        requested_path == root.resolve() or root.resolve() in requested_path.parents
        for root in ALLOWED_IMAGE_ROOTS
    )
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access to path is not allowed")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    media_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return FileResponse(
        str(requested_path),
        media_type=media_map.get(requested_path.suffix.lower(), "application/octet-stream"),
    )


@app.post("/optimize", response_model=OptimizationResponse)
async def optimize_kpis(request: OptimizationRequest):
    """
    Optimization endpoint: extracts KPIs from natural language
    and runs the selected optimizer (IWO or QGA).
    """
    try:
        from input_agent.src.llm import LLMService
        from input_agent.sub_agents.optimizer import OptimizerAgent

        optimizer = request.optimizer.strip().lower()
        if optimizer not in ["iwo", "qga"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid optimizer '{request.optimizer}'. Use 'iwo' or 'qga'",
            )

        logger.info(f"🎯 Starting optimization with sub-agent: {optimizer}")

        llm = LLMService()
        optimizer_agent = OptimizerAgent(llm)
        success, extracted_kpis, optimized_config, message = optimizer_agent.optimize(
            user_query=request.query,
            optimizer_type=optimizer,
            json_input=request.config,
        )

        execution_log = []
        if extracted_kpis:
            execution_log.append(f"✅ Extracted KPIs: {list(extracted_kpis.keys())}")
        execution_log.append(("✅ " if success else "❌ ") + message)

        return OptimizationResponse(
            success=success,
            optimized_config=optimized_config,
            extracted_kpis=extracted_kpis if extracted_kpis else None,
            message=message,
            execution_log=execution_log,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /optimize: {e}", exc_info=True)
        return OptimizationResponse(
            success=False,
            message=f"Error: {e!s}",
            execution_log=[f"❌ Error in /optimize: {e!s}"],
        )


# ============== MAIN ==============
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    preferred_port = int(os.getenv("API_PORT", os.getenv("PORT", "8000")))
    port = find_available_port(host, preferred_port)
    if port != preferred_port:
        logger.warning(f"⚠️ Port {preferred_port} is busy. Starting on port {port}.")
    uvicorn.run(app, host=host, port=port, reload=False)
