"""
Author: Noah Masegosa Caceres 
Center: @ugr

xAI simulation: Wrapper que activa al agente xAI con visualizaciones integradas.
"""

import os
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from input_agent.src.llm import LLMService
from input_agent.src.wiki import PDFWiki
from input_agent.src.traceProcessor import TraceProcessor
from input_agent.sub_agents.narrative import NarrativeAgent


# Matplotlib keeps process-global state; serialize rendering during concurrent xAI calls.
_VISUALIZATION_LOCK = threading.Lock()


def extract_numeric_kpis(stats: Any, prefix: str = "") -> Dict[str, float]:
    """
    Extrae TODOS los KPIs numéricos detectables de una estructura JSON anidada.
    Retorna un diccionario plano path->valor.
    """
    kpis: Dict[str, float] = {}

    if isinstance(stats, dict):
        for key, value in stats.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            kpis.update(extract_numeric_kpis(value, next_prefix))
        return kpis

    if isinstance(stats, list):
        for idx, value in enumerate(stats):
            next_prefix = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            kpis.update(extract_numeric_kpis(value, next_prefix))
        return kpis

    if isinstance(stats, bool):
        return kpis

    if isinstance(stats, (int, float)):
        key = prefix if prefix else "value"
        kpis[key] = float(stats)

    return kpis


def load_kpis_from_stats(stats_json_path: str) -> Dict[str, float]:
    """Carga KPIs numéricos desde el JSON de estadísticas de simulación."""
    try:
        stats_path = Path(stats_json_path)
        if not stats_path.exists():
            return {}

        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)

        return extract_numeric_kpis(stats)
    except Exception:
        return {}


def compute_kpi_delta(baseline_kpis: Dict[str, float], current_kpis: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
    """
    Calcula delta matemático KPI a KPI.
    - delta_abs = current - baseline
    - delta_pct = ((current - baseline) / abs(baseline)) * 100, salvo baseline=0 -> None (N/A)
    """
    result: Dict[str, Dict[str, Any]] = {}
    all_keys = sorted(set(baseline_kpis.keys()) | set(current_kpis.keys()))

    for key in all_keys:
        base_val = baseline_kpis.get(key, 0.0)
        curr_val = current_kpis.get(key, 0.0)

        if isinstance(base_val, bool) or isinstance(curr_val, bool):
            continue
        if not isinstance(base_val, (int, float)) or not isinstance(curr_val, (int, float)):
            continue

        delta_abs = float(curr_val) - float(base_val)
        if float(base_val) == 0.0:
            delta_pct = None
        else:
            delta_pct = (delta_abs / abs(float(base_val))) * 100.0

        result[key] = {
            "baseline": float(base_val),
            "current": float(curr_val),
            "delta_abs": float(delta_abs),
            "delta_pct": float(delta_pct) if delta_pct is not None else None,
        }

    return result


def _generate_visualizations(input_data: dict) -> Dict[str, Any]:
    """
    Generates bottleneck heatmap and Gantt charts from simulation results.
    
    Args:
        input_data: Dictionary with trace_csv and other paths
    
    Returns:
        Dictionary with paths to generated visualizations and summaries
    """
    visualizations = {
        "bottleneck_heatmap": None,
        "bottleneck_summary": None,
        "gantt_charts": [],
        "gantt_summary": None
    }
    
    metadata_path = None

    try:
        from input_agent.src.bottlenecks import analyze_bottlenecks, get_bottleneck_summary
        from input_agent.src.visualization import generate_gantt_charts, get_gantt_summary
        
        trace_csv = input_data.get('trace_csv')
        if not trace_csv or not Path(trace_csv).exists():
            print(f"⚠️ Trace file not found: {trace_csv}")
            return visualizations
        
        results_dir = Path(trace_csv).parent
        metadata_path = results_dir / "visualization_metadata.json"
        
        print("📊 Generating bottleneck heatmap...")
        rank_df, heatmap_path = analyze_bottlenecks(
            trace_path=trace_csv,
            output_dir=str(results_dir),
            topN=15,
            show_plot=False
        )
        visualizations["bottleneck_heatmap"] = heatmap_path
        visualizations["bottleneck_summary"] = get_bottleneck_summary(rank_df, topN=10)
        
        durations_path = results_dir / "calculated_task_durations.xlsx"
        if durations_path.exists():
            print("📊 Generating Gantt charts...")
            gantt_paths = generate_gantt_charts(
                durations_path=str(durations_path),
                output_dir=str(results_dir),
                show_plots=False,
                condense_idle_gaps=True,
                idle_gap_scale=0.05,
                min_gap_to_condense=0.0
            )
            visualizations["gantt_charts"] = gantt_paths
            visualizations["gantt_summary"] = get_gantt_summary(str(durations_path))
        else:
            print(f"⚠️ Durations file not found: {durations_path}")

        # Persist metadata for the frontend so generated images are discoverable.
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(visualizations, f, ensure_ascii=False, indent=2)
            print(f"✅ Visualization metadata saved to: {metadata_path}")
        except Exception as metadata_error:
            print(f"⚠️ Could not save visualization metadata: {metadata_error}")
        
    except Exception as e:
        print(f"❌ Error generating visualizations: {e}")
        import traceback
        traceback.print_exc()
    
    return visualizations


def xAI_simulation(input_data, info=None):
    """
    Ejecuta el pipeline de análisis forense post-simulación.
    Enriquecido con análisis de delta para explicar cambios de configuración.
    Ahora incluye visualizaciones automáticas (bottlenecks y Gantt charts).
    
    Args:
        input_data (dict): Debe contener las rutas de los archivos generados.
                           Ej: {'trace_csv': '...', 'stats_json': '...', 'manual_pdf': '...',
                                'delta': {...}, 'baseline_report': '...'}
                           'delta' es opcional y contiene cambios estructurales.
                           'baseline_report' es opcional y representa el reporte xAI base.
        info (dict): Metadatos opcionales.
    
    Returns:
        str: Reporte narrativo con análisis causal de cambios y KPIs
    """

    load_dotenv()
    M_k_path = input_data.get('trace_csv', 'trace.csv')
    general_outputs_path = input_data.get('stats_json', 'stats.json')
    pdf_path = input_data.get('manual_pdf', 'manual.pdf')
    delta = input_data.get('delta', {})
    baseline_report = input_data.get('baseline_report', '')
    compact_report = input_data.get('compact_report', True)
    baseline_kpis = input_data.get('baseline_kpis', {})
    current_kpis = input_data.get('current_kpis', {})
    kpi_delta = input_data.get('kpi_delta', {})
    validation_violations = input_data.get('validation_violations')
    kpi_reference = input_data.get('kpi_reference')

    llm_service = LLMService()
    
    try:
        print("🎨 Generating visualizations...")
        with _VISUALIZATION_LOCK:
            visualizations = _generate_visualizations(input_data)
        
        # Solo generar visualizaciones, sin análisis en el reporte
        # Las visualizaciones se guardarán en JSON para el frontend
        
        wiki = PDFWiki(pdf_path)
        processor = TraceProcessor(M_k_path, general_outputs_path)
        agent = NarrativeAgent(wiki, llm_service)

        if not current_kpis:
            current_kpis = extract_numeric_kpis(processor.stats)
        if baseline_kpis and not kpi_delta:
            kpi_delta = compute_kpi_delta(baseline_kpis, current_kpis)

        if compact_report:
            print("⚡ Modo compacto KPI activado: se omite el análisis evento-a-evento para acelerar la generación del reporte.")
            segments = []
        else:
            if delta or baseline_report:
                print(f"📊 Enriqueciendo análisis con delta de cambios: {str(delta)[:200]}...")
                segments = agent.run_batched_cycle(
                    processor,
                    delta_context=delta,
                    baseline_report=baseline_report
                )
            else:
                segments = agent.run_batched_cycle(processor)

        final_report = agent.generate_full_narrative(
            segments,
            processor,
            delta_context=delta if delta else None,
            baseline_report=baseline_report,
            baseline_kpis=baseline_kpis,
            current_kpis=current_kpis,
            kpi_delta=kpi_delta,
            validation_violations=validation_violations,
            kpi_reference=kpi_reference,
        )
        
        output_filename = "forensic_report.txt"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(final_report)
        
        # Guardar metadata de visualizaciones en JSON para el frontend
        viz_metadata_path = Path(M_k_path).parent / "visualization_metadata.json"
        viz_metadata = {
            "bottleneck_heatmap": str(visualizations["bottleneck_heatmap"]) if visualizations["bottleneck_heatmap"] else None,
            "gantt_charts": [str(p) for p in visualizations["gantt_charts"]]
        }
        with open(viz_metadata_path, "w", encoding="utf-8") as f:
            json.dump(viz_metadata, f, indent=2)
            
        return final_report

    except Exception as e:
        print(f"❌ Error crítico en el análisis: {e}")
        import traceback
        traceback.print_exc()
        return None