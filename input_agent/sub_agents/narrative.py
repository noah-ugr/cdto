"""
Author: Noah Masegosa Caceres 
Center: @ugr

NarrativeAgent: Genera narrativas comprensibles a partir de evolución temporal de Markings en Petri Nets.
    Utiliza procesamiento por lotes para manejar grandes trazas y RAG para contexto.

Metodos principales:
    - run_batched_cycle: Procesa eventos en bloques, consulta RAG para contexto y genera segmentos narrativos.
    - generate_full_narrative: Combina segmentos en una narrativa completa con visión global.
    - _consult_wiki: Consulta RAG con caché para definiciones de transiciones y lugares.
    - _get_batch_context: Recopila definiciones Wiki solo para elementos presentes en el lote, evitando redundancias.

"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from input_agent.src.llm import LLMService
from input_agent.src.models import FullNarrative, StepNarrative
from input_agent.src.prompts import (
    BATCH_NARRATIVE_PROMPT, 
    GLOBAL_NARRATIVE_PROMPT,
    XAI_NARRATIVE_BASELINE_PROMPT,
    XAI_NARRATIVE_DELTA_PROMPT
)
from input_agent.src.wiki import PDFWiki

class NarrativeAgent:
    def __init__(self, wiki: PDFWiki, llm_service: LLMService):
        self.wiki = wiki
        self.llm = llm_service 
        self.cache = {}

    def _consult_wiki(self, query_id, type="trans"):
        """
        Consulta Wiki para definiciones usando nomenclature inteligente.
        Usa consult_petri_node del PDFWiki para interpretaciones precisas.
        
        Args:
            query_id: ID del nodo (ej: 'p731', 't0007')
            type: "trans" o "place"
            
        Returns:
            Descripción enriquecida del nodo
        """
        if query_id in self.cache:
            return self.cache[query_id]
        
        # Convertir nombre de tipo para compatibilidad
        node_type = "transition" if type == "trans" else "place"
        
        # Usar método mejorado del wiki con nomenclature parser
        res = self.wiki.consult_petri_node(query_id, node_type)
        
        clean_res = res.replace('\n', ' ')[:400]  # Limitar a 400 chars
        self.cache[query_id] = clean_res
        return clean_res

    def _get_batch_context(self, batch_events):
        """
        Recopila definiciones Wiki solo para los elementos presentes en este lote.
        Evita consultas repetidas y ahorra tokens.
        """
        unique_t = set(e['t_id'] for e in batch_events)
        unique_p = set()
        for e in batch_events:
            unique_p.update(e['state'].keys())
            
        context_lines = []
        for t_id in unique_t:
            desc = self._consult_wiki(t_id, "trans")
            context_lines.append(f"- Trans {t_id}: {desc}")
            
        for p_id in unique_p:
            desc = self._consult_wiki(p_id, "place")
            context_lines.append(f"- Place {p_id}: {desc}")
            
        return "\n".join(context_lines)

    def _extract_kpi_snapshot(self, stats: dict, max_items: int = 60):
        """
        Construye un snapshot compacto de KPIs para minimizar tokens en el prompt.
        Evita enviar trazas completas al LLM.
        """
        if not isinstance(stats, dict):
            return {}

        kpi_keywords = (
            "kpi", "availability", "unavailability", "throughput", "util", "duration",
            "downtime", "uptime", "intervention", "standby", "idle", "wait", "cost",
            "bottleneck", "rate", "count", "completed", "failed", "total", "mean",
            "avg", "average", "max", "min", "std", "percent"
        )

        collected = []

        def walk(node, path="", depth=0):
            if isinstance(node, dict):
                for key, value in node.items():
                    next_path = f"{path}.{key}" if path else str(key)
                    walk(value, next_path, depth + 1)
                return

            if isinstance(node, list):
                # Mantener arrays cortos y escalares para no inflar tokens.
                if len(node) <= 8 and all(isinstance(x, (int, float, str, bool, type(None))) for x in node):
                    key_l = path.lower()
                    if any(k in key_l for k in kpi_keywords):
                        collected.append((path, node))
                return

            if isinstance(node, (int, float, bool, str)):
                key_l = path.lower()
                is_kpi_like = any(k in key_l for k in kpi_keywords)
                is_shallow_numeric = depth <= 2 and isinstance(node, (int, float))
                if is_kpi_like or is_shallow_numeric:
                    collected.append((path, node))

        walk(stats)

        # Priorizamos paths KPI y luego los más cortos para mayor legibilidad.
        def score(item):
            path, _ = item
            path_l = path.lower()
            kw_hits = sum(1 for k in kpi_keywords if k in path_l)
            return (-kw_hits, len(path))

        collected_sorted = sorted(collected, key=score)
        trimmed = collected_sorted[:max_items]
        return {k: v for k, v in trimmed}

    def _format_kpi_value(self, value):
        if isinstance(value, (int, float)):
            return f"{value:.4f}"
        return str(value)

    def _prettify_kpi_name(self, raw_key):
        """Convierte paths técnicos de KPIs en nombres legibles para demo."""
        if not raw_key:
            return "KPI"

        # Normalizar path típico: general_results[0].Net_plan_availability_percent
        key = str(raw_key)
        leaf = key.split(".")[-1]

        friendly_map = {
            "Simulation_period_hours": "Simulation Period (h)",
            "Intervention_time_hours": "Intervention Time (h)",
            "Net_plan_availability_hours": "Net Plan Availability (h)",
            "Net_plan_availability_percent": "Net Plan Availability (%)",
            "Net_plan_unavailability_hours": "Net Plan Unavailability (h)",
            "Net_plan_unavailability_percent": "Net Plan Unavailability (%)",
            "P4_total_busy_hours": "P4 Busy Time (h)",
            "P4_total_busy_percent": "P4 Busy Time (%)",
            "Activities_overlap_percent": "Activities Overlap (%)",
        }

        if leaf in friendly_map:
            return friendly_map[leaf]

        # Fallback genérico legible.
        normalized = leaf.replace("_", " ").strip()
        return normalized.title() if normalized else key

    def _build_kpi_comparison_table(self, baseline_kpis, current_kpis, kpi_delta):
        """Construye tabla markdown fija: Baseline | Current | Delta abs | Delta %."""
        baseline_kpis = baseline_kpis or {}
        current_kpis = current_kpis or {}
        kpi_delta = kpi_delta or {}

        keys = sorted(set(baseline_kpis.keys()) | set(current_kpis.keys()) | set(kpi_delta.keys()))
        if not keys:
            return "## KPI Comparison\n\n_No KPI data available._"

        lines = [
            "## KPI Comparison",
            "",
            "| KPI | Baseline | Current | Delta abs | Delta % |",
            "|---|---:|---:|---:|---:|",
        ]

        for key in keys:
            item = kpi_delta.get(key, {}) if isinstance(kpi_delta.get(key, {}), dict) else {}
            baseline_value = item.get("baseline", baseline_kpis.get(key, 0.0))
            current_value = item.get("current", current_kpis.get(key, 0.0))
            try:
                delta_abs_fallback = float(current_value) - float(baseline_value)
            except Exception:
                delta_abs_fallback = 0.0
            delta_abs = item.get("delta_abs", delta_abs_fallback)
            delta_pct = item.get("delta_pct", None)

            delta_pct_text = "N/A" if delta_pct is None else f"{delta_pct:.2f}%"
            lines.append(
                "| {k} | {b} | {c} | {d} | {p} |".format(
                    k=self._prettify_kpi_name(key),
                    b=self._format_kpi_value(baseline_value),
                    c=self._format_kpi_value(current_value),
                    d=self._format_kpi_value(delta_abs),
                    p=delta_pct_text,
                )
            )

        return "\n".join(lines)

    def run_batched_cycle(self, trace_processor, batch_size=5, delta_context=None, baseline_report=None):
        """
        PROCESAMIENTO POR LOTES CON PARALELIZACIÓN (La solución al problema de escala).
        Agrupa eventos cronológicos, prepara mensajes y genera narrativas en PARALELO.
        """
        trace_dict = trace_processor.compress_nested_trace()
        
        all_events = []
        
        sorted_times = sorted(trace_dict.keys(), key=lambda x: float(x))
        
        for time_str in sorted_times:
            transitions = trace_dict[time_str]
            for t_id, state_dict in transitions.items():
                all_events.append({
                    "time": time_str,
                    "t_id": t_id,
                    "state": state_dict
                })
        
        total_events = len(all_events)
        num_batches = (total_events + batch_size - 1) // batch_size
        print(f"⚡ Modo Batch Paralelo Activado: Procesando {total_events} eventos en {num_batches} bloques de {batch_size}...")
        
        batch_jobs = []
        delta_block = str(delta_context) if delta_context else "No delta provided."
        baseline_block = baseline_report if baseline_report else "No baseline report provided."
        
        for i in range(0, total_events, batch_size):
            batch = all_events[i : i + batch_size]
            batch_index = i // batch_size
            
            context_block = self._get_batch_context(batch)
            
            events_text_list = []
            for e in batch:
                state_str = ", ".join([f"{k}:{v}" for k,v in e['state'].items()])
                events_text_list.append(
                    f"[t={e['time']}] Trans '{e['t_id']}' fired. Impact: {{{state_str}}}"
                )
            events_block = "\n".join(events_text_list)

            user_msg = f"""
            CONFIGURATION DELTA:
            {delta_block}

            BASELINE xAI REPORT:
            {baseline_block}

            CONTEXT DEFINITIONS:
            {context_block}

            EVENT LOGS TO NARRATE:
            {events_block}
            """
            
            batch_jobs.append((batch_index, batch, user_msg))
        
        narrative_segments = [None] * len(batch_jobs)
        
        def process_batch(job):
            batch_index, batch, user_msg = job
            try:
                response_dict = self.llm.llm(BATCH_NARRATIVE_PROMPT, user_msg)
                response_dict = StepNarrative(**response_dict)
                
                if "narrative" in response_dict:
                    return (batch_index, response_dict["narrative"])
                else:
                    return (batch_index, str(response_dict))
            except Exception as e:
                print(f"❌ Error en lote {batch_index}: {e}")
                return (batch_index, f"[Error processing batch starting at t={batch[0]['time']}]")
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(process_batch, job): job for job in batch_jobs}
            
            completed = 0
            for future in as_completed(futures):
                batch_index, result = future.result()
                narrative_segments[batch_index] = result
                completed += 1
                progress = int((completed / len(batch_jobs)) * 100)
                print(f"  ✓ Lote {batch_index + 1}/{len(batch_jobs)} completado ({progress}%)")
        
        return narrative_segments
    
    def generate_full_narrative(
        self,
        segments,
        trace_processor,
        delta_context=None,
        baseline_report=None,
        baseline_kpis=None,
        current_kpis=None,
        kpi_delta=None,
        validation_violations=None,
        kpi_reference=None,
    ):

        """Combina los segmentos en una narrativa completa. validation_violations: violaciones
        estructuradas (regla, grupo, ruta, detalle) del candidato rechazado, si las hay.
        kpi_reference: qué configuración ocupa la columna Baseline de la tabla de KPI, si no es la
        inicial (en la rutina de diagnóstico, S_k)."""

        delta_block = str(delta_context) if delta_context else "No delta provided."
        baseline_block = baseline_report if baseline_report else "No baseline report provided."
        kpi_snapshot = self._extract_kpi_snapshot(trace_processor.stats)
        kpi_table_markdown = self._build_kpi_comparison_table(baseline_kpis, current_kpis, kpi_delta)

        violations_block = (
            "Validation Violations of the rejected candidate (JSON): "
            f"{json.dumps(validation_violations, ensure_ascii=False)}\n\n"
            if validation_violations
            else ""
        )
        reference_block = (
            f"KPI Reference: the Baseline column of the KPI table and the KPI Delta refer to the {kpi_reference}, "
            "not to the initial configuration described in the Baseline Report.\n\n"
            if kpi_reference
            else ""
        )

        full_prompt = (
            f"Delta: {delta_block}\n\n"
            f"{violations_block}"
            f"{reference_block}"
            f"Baseline Report: {baseline_block}\n\n"
            f"KPI Snapshot (compact JSON): {json.dumps(kpi_snapshot, ensure_ascii=False)}\n\n"
            f"KPI Delta (JSON): {json.dumps(kpi_delta or {}, ensure_ascii=False)}\n\n"
            f"KPI Comparison Table (MANDATORY in final output):\n{kpi_table_markdown}\n\n"
            f"Stats summary source: {json.dumps(trace_processor.stats, ensure_ascii=False)[:3000]}\n\n"
            "Temporal event-by-event explanation is intentionally excluded in this report."
        )

        if segments:
            # Soporte legacy opcional para modo detallado cuando se habilite explícitamente.
            full_prompt += "\n\nOptional timeline segments:\n" + "\n\n".join(segments[:8])

        if baseline_report and baseline_report.strip():
            print("🔄 Usando XAI_NARRATIVE_DELTA_PROMPT para análisis detallado de cambios...")
            selected_prompt = XAI_NARRATIVE_DELTA_PROMPT
        else:
            print("📊 Usando XAI_NARRATIVE_BASELINE_PROMPT para análisis detallado de baseline...")
            selected_prompt = XAI_NARRATIVE_BASELINE_PROMPT

        final_narrative = self.llm.llm(selected_prompt, full_prompt)

        full_narrative = FullNarrative(**final_narrative)

        report_text = full_narrative.report or ""
        has_kpi_table_header = "| KPI | Baseline | Current | Delta abs | Delta % |" in report_text
        has_kpi_section = "## KPI Comparison" in report_text or "2. KPI Changes" in report_text

        # Garantía dura sin duplicación: solo inyecta la tabla si el LLM no la incluyó.
        if has_kpi_table_header and has_kpi_section:
            return report_text

        return kpi_table_markdown + "\n\n" + report_text