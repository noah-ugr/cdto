"""
Author: Noah Masegosa Caceres 
Center: @ugr

TemporalXAIAgent: Responde preguntas específicas sobre estados temporales de la simulación.
    - Analiza consultas temporales del usuario (ej: "¿Qué pasó en t=50?" o "Explica de t=100 a t=200")
    - Extrae datos relevantes del M_k (matriz de marcado)
    - Usa RAG (PDFWiki) para contextualizar transiciones y lugares
    - Procesa eventos en paralelo (batch de 1 evento por transición)
    - Sintetiza explicaciones individuales en narrativa coherente

Métodos principales:
    - parse_temporal_query: Extrae el rango temporal de la consulta del usuario usando LLM
    - extract_temporal_data: Obtiene los eventos relevantes del TraceProcessor
    - process_events_parallel: Procesa cada evento en paralelo (batch=1)
    - synthesize_temporal_narrative: Une las explicaciones individuales
"""

from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from input_agent.src.llm import LLMService
from input_agent.src.wiki import TXTWiki
from input_agent.src.traceProcessor import TraceProcessor
from input_agent.src.prompts import (
    TEMPORAL_QUERY_PARSER_PROMPT,
    TEMPORAL_EVENT_PROMPT,
    TEMPORAL_SYNTHESIS_PROMPT
)


class TemporalQuery(BaseModel):
    """Estructura para parsear consultas temporales."""
    time_start: Optional[float] = Field(None, description="Tiempo inicial del rango (inclusive)")
    time_end: Optional[float] = Field(None, description="Tiempo final del rango (inclusive)")
    is_single_point: bool = Field(False, description="¿Es una consulta de un punto temporal específico?")
    reasoning: str = Field("", description="Razonamiento sobre la interpretación de la consulta")


class TemporalEvent(BaseModel):
    """Representa un evento en un momento específico."""
    time: float
    transition_id: str
    places_affected: Dict[str, int]  # {place_id: tokens}
    transition_description: str = ""
    places_descriptions: Dict[str, str] = {}


class TemporalXAIAgent:
    """Agente especializado en responder consultas temporales sobre simulaciones."""
    
    def __init__(self, llm_service: LLMService, wiki: TXTWiki):
        self.llm = llm_service
        self.wiki = wiki
        self.cache = {}
    
    def _consult_wiki(self, query_id: str, type_: str = "trans") -> str:
        """
        Consulta Wiki para definiciones usando nomenclature inteligente.
        Usa consult_petri_node del TXTWiki para interpretaciones precisas.
        
        Args:
            query_id: ID del nodo (ej: 'p731', 't0007')
            type_: "trans" o "place"
            
        Returns:
            Descripción enriquecida del nodo
        """
        cache_key = f"{type_}:{query_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Convertir nombre de tipo para compatibilidad
        node_type = "transition" if type_ == "trans" else "place"
        
        # Usar método mejorado del wiki con nomenclature parser
        result = self.wiki.consult_petri_node(query_id, node_type)
        
        clean_result = result.replace('\n', ' ')[:400]  # Limitar a 400 chars
        self.cache[cache_key] = clean_result
        return clean_result
    
    def parse_temporal_query(self, user_query: str) -> TemporalQuery:
        """
        Usa el LLM para extraer el rango temporal de la consulta del usuario.
        
        Args:
            user_query: Consulta del usuario en lenguaje natural
            
        Returns:
            TemporalQuery con el rango temporal identificado
        """
        response = self.llm.llm(TEMPORAL_QUERY_PARSER_PROMPT, user_query)
        temporal_query = TemporalQuery(**response)
        
        # FIX: Si es un punto temporal único, time_end debe ser igual a time_start
        if temporal_query.is_single_point and temporal_query.time_start is not None:
            temporal_query.time_end = temporal_query.time_start
        
        print(f"🔍 Temporal Query Parsed: {temporal_query.reasoning}")
        print(f"   Time Range: [{temporal_query.time_start}, {temporal_query.time_end}]")
        
        return temporal_query
    
    def extract_temporal_data(
        self,
        trace_processor: TraceProcessor,
        time_start: Optional[float],
        time_end: Optional[float]
    ) -> List[TemporalEvent]:
        """
        Extrae eventos del TraceProcessor en el rango temporal especificado.
        
        Args:
            trace_processor: Procesador de trazas con acceso a M_k
            time_start: Tiempo inicial (None = desde el inicio)
            time_end: Tiempo final (None = hasta el final)
            
        Returns:
            Lista de eventos temporales con contexto
        """
        trace_dict = trace_processor.compress_nested_trace()
        events = []
        
        # Ordenar tiempos cronológicamente
        sorted_times = sorted(trace_dict.keys(), key=lambda x: float(x))
        
        for time_str in sorted_times:
            time_float = float(time_str)
            
            # Filtrar por rango temporal
            if time_start is not None and time_float < time_start:
                continue
            if time_end is not None and time_float > time_end:
                continue
            
            transitions = trace_dict[time_str]
            
            for t_id, state_dict in transitions.items():
                # Obtener definiciones wiki
                trans_desc = self._consult_wiki(t_id, "trans")
                
                places_descs = {}
                for place_id in state_dict.keys():
                    places_descs[place_id] = self._consult_wiki(place_id, "place")
                
                event = TemporalEvent(
                    time=time_float,
                    transition_id=t_id,
                    places_affected=state_dict,
                    transition_description=trans_desc,
                    places_descriptions=places_descs
                )
                events.append(event)
        
        return events
    
    def process_events_parallel(
        self,
        events: List[TemporalEvent],
        user_query: str,
        delta_context: Optional[Dict] = None,
        baseline_report: Optional[str] = None
    ) -> List[str]:
        """
        Procesa cada evento en paralelo (batch de 1 transición).
        Similar a run_batched_cycle del NarrativeAgent pero con batch_size=1.
        
        Args:
            events: Lista de eventos temporales a procesar
            user_query: Consulta original del usuario
            delta_context: Cambios de configuración (opcional)
            baseline_report: Reporte baseline (opcional)
            
        Returns:
            Lista de narrativas individuales (una por evento)
        """
        if not events:
            return ["No se encontraron eventos en el rango temporal especificado."]
        
        total_events = len(events)
        print(f"⚡ Modo Paralelo Activado: Procesando {total_events} eventos individualmente...")
        
        delta_block = str(delta_context) if delta_context else "No delta provided."
        baseline_block = baseline_report if baseline_report else "No baseline report provided."
        
        # Preparar jobs (cada evento es un job independiente)
        event_jobs = []
        for idx, event in enumerate(events):
            # Construir contexto para este evento específico
            places_info = ", ".join([
                f"{p_id}={tokens} tokens" for p_id, tokens in event.places_affected.items()
            ])
            
            event_text = f"[t={event.time}] Transition '{event.transition_id}' fired. Impact: {{{places_info}}}"
            
            # Contexto de definiciones para este evento
            context_lines = []
            context_lines.append(f"- Transition {event.transition_id}: {event.transition_description}")
            for p_id, desc in event.places_descriptions.items():
                context_lines.append(f"- Place {p_id}: {desc}")
            context_block = "\n".join(context_lines)
            
            user_msg = f"""
USER QUERY:
{user_query}

CONFIGURATION DELTA:
{delta_block}

BASELINE xAI REPORT:
{baseline_block}

CONTEXT DEFINITIONS:
{context_block}

EVENT TO EXPLAIN:
{event_text}
"""
            
            event_jobs.append((idx, event, user_msg))
        
        # Inicializar array de resultados
        event_narratives = [None] * len(event_jobs)
        
        def process_event(job):
            idx, event, user_msg = job
            try:
                response = self.llm.llm(TEMPORAL_EVENT_PROMPT, user_msg)
                
                # Extraer narrativa del response
                if isinstance(response, dict) and "narrative" in response:
                    narrative = response["narrative"]
                elif isinstance(response, dict) and "report" in response:
                    narrative = response["report"]
                else:
                    narrative = str(response)
                
                return (idx, narrative)
            except Exception as e:
                print(f"❌ Error procesando evento en t={event.time}: {e}")
                return (idx, f"[Error processing event at t={event.time}]")
        
        # Ejecutar en paralelo con ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(process_event, job): job for job in event_jobs}
            
            completed = 0
            for future in as_completed(futures):
                idx, narrative = future.result()
                event_narratives[idx] = narrative
                completed += 1
                progress = int((completed / len(event_jobs)) * 100)
                print(f"  ✓ Evento {idx + 1}/{len(event_jobs)} completado ({progress}%)")
        
        return event_narratives
    
    def synthesize_temporal_narrative(
        self,
        event_narratives: List[str],
        user_query: str,
        stats: Dict[str, Any],
        time_range: tuple,
        delta_context: Optional[Dict] = None,
        baseline_report: Optional[str] = None
    ) -> str:
        """
        Sintetiza las narrativas individuales en un reporte coherente.
        Similar a generate_full_narrative del NarrativeAgent.
        
        Args:
            event_narratives: Lista de explicaciones individuales
            user_query: Consulta original del usuario
            stats: Estadísticas globales
            time_range: (time_start, time_end)
            delta_context: Cambios de configuración (opcional)
            baseline_report: Reporte baseline (opcional)
            
        Returns:
            Narrativa temporal completa y coherente
        """
        if not event_narratives:
            return "No se generaron narrativas para sintetizar."
        
        delta_block = str(delta_context) if delta_context else "No delta provided."
        baseline_block = baseline_report if baseline_report else "No baseline report provided."
        stats_block = str(stats)
        
        time_start, time_end = time_range
        time_window = f"[t={time_start}, t={time_end}]" if time_end else f"t={time_start}"
        
        # Unir narrativas individuales
        combined_narratives = "\n\n".join([
            f"### Event {i+1}\n{narrative}" 
            for i, narrative in enumerate(event_narratives)
        ])
        
        synthesis_prompt = f"""
USER QUERY:
{user_query}

TEMPORAL WINDOW:
{time_window}

CONFIGURATION DELTA:
{delta_block}

BASELINE xAI REPORT:
{baseline_block}

GLOBAL STATISTICS:
{stats_block}

INDIVIDUAL EVENT EXPLANATIONS:
{combined_narratives}
"""
        
        print("🔄 Sintetizando narrativas individuales en reporte coherente...")
        response = self.llm.llm(TEMPORAL_SYNTHESIS_PROMPT, synthesis_prompt)
        
        # Extraer el reporte
        if isinstance(response, dict) and "report" in response:
            return response["report"]
        
        return str(response)
    
    def run(
        self,
        user_query: str,
        trace_processor: TraceProcessor,
        delta_context: Optional[Dict] = None,
        baseline_report: Optional[str] = None
    ) -> str:
        """
        Pipeline completo: parse query -> extract data -> parallel processing -> synthesis.
        
        Args:
            user_query: Consulta temporal del usuario
            trace_processor: Procesador de trazas
            delta_context: Cambios de configuración (opcional)
            baseline_report: Reporte baseline (opcional)
            
        Returns:
            Narrativa explicativa en lenguaje natural
        """
        # 1. Parsear consulta temporal
        temporal_query = self.parse_temporal_query(user_query)
        
        # 2. Extraer datos del rango temporal
        events = self.extract_temporal_data(
            trace_processor,
            temporal_query.time_start,
            temporal_query.time_end
        )
        
        print(f"📊 Extracted {len(events)} events in temporal range")
        
        if not events:
            return "No se encontraron eventos en el rango temporal especificado. Verifica que la simulación contiene datos para ese período."
        
        # 3. Procesar cada evento en paralelo (batch=1)
        event_narratives = self.process_events_parallel(
            events,
            user_query,
            delta_context,
            baseline_report
        )
        
        # 4. Sintetizar narrativas individuales en reporte coherente
        final_report = self.synthesize_temporal_narrative(
            event_narratives,
            user_query,
            trace_processor.stats,
            (temporal_query.time_start, temporal_query.time_end),
            delta_context,
            baseline_report
        )
        
        return final_report
