"""
Author: Noah Masegosa Caceres
Center: @ugr

NomenclatureParser: Interpreta la nomenclatura parametrizada del Petri Net.
Convierte IDs como 'p731' o 't001' en descripciones precisas del PDF.

Nomenclatura del Petri Net (basada en la documentación):
- p7ji: lugar de ejecución de tarea j en actividad i (task place)
- p02i: lugar en bucle de tarea de actividad i (task loop place)
- p8i: lugar de completación de actividad i (activity completion place)
- t0007ji: transición de ejecución de tarea j en actividad i
- t0006i: transición de bucle de mantenimiento de actividad i
- t0008i: transición de completación de actividad i
- etc.
"""

import re
from typing import Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class Place:
    """Representación de un lugar en el Petri Net."""
    id: str
    type: str  # generic, activity_level, task_level, buffer
    description: str
    activity_idx: Optional[int] = None
    task_idx: Optional[int] = None


@dataclass
class Transition:
    """Representación de una transición en el Petri Net."""
    id: str
    type: str  # atomic, activity_level, task_level
    description: str
    activity_idx: Optional[int] = None
    task_idx: Optional[int] = None


class NomenclatureParser:
    """Parser para nomenclatura parametrizada del Petri Net."""
    
    # DEFINICIONES DE LUGARES GLOBALES (sin parámetros)
    GENERIC_PLACES = {
        "p3": "team-capacity pool (resource allocation place)",
        "p4": "maintenance lock / allocation place",
        "p5": "work-state indicator (operational/working state)",
        "p6": "break-state indicator (break/rest state)",
        "p0": "global 'system operational' place (marks system is operational)"
    }
    
    # DEFINICIONES DE TRANSICIONES GLOBALES (sin parámetros)
    ATOMIC_TRANSITIONS = {
        "t3": "allocation of workers from maintenance lock to team-capacity pool",
        "t4": "transition from break state to work state",
        "t5": "transition from work state to break state",
        "t9": "global reset transition (reinitializes system state)"
    }
    
    # PATRONES DE LUGARES CON PARÁMETROS
    PLACE_PATTERNS = {
        r"^p7(\d+)(\d+)$": ("task_level", "internal task place for task {j} in activity {i}"),
        r"^p02(\d+)$": ("activity_level", "activity {i} task loop place (activity in execution of tasks)"),
        r"^p8(\d+)$": ("activity_level", "activity {i} completion place"),
        r"^p1(\d+)$": ("activity_level", "activity {i} ready-to-start place"),
        r"^p00(\d+)$": ("activity_level", "initial place for activity {i}"),
        r"^p(\d+)0$": ("activity_level", "initial state place within activity {i} subnet"),
        r"^pbuff(\d+)$": ("buffer", "buffer place for activity {i} (inter-activity precedence)")
    }
    
    # PATRONES DE TRANSICIONES CON PARÁMETROS
    TRANSITION_PATTERNS = {
        r"^t0007(\d+)(\d+)$": ("task_level", "execution transition for task {j} in activity {i}"),
        r"^t0006(\d+)$": ("activity_level", "maintenance loop transition for activity {i}"),
        r"^t0008(\d+)$": ("activity_level", "completion transition for activity {i} (feeds completion place and buffer)"),
        r"^t00(\d+)$": ("activity_level", "root family entry transition t00 for activity {i}"),
        r"^t0(\d+)$": ("activity_level", "root family transition t0 for activity {i}"),
        r"^t(\d+)0$": ("activity_level", "activation transition for activity {i}"),
        r"^t(\d+)1$": ("activity_level", "entry-into-task-loop transition for activity {i}"),
        r"^t(\d+)2$": ("activity_level", "completion and return transition for activity {i}")
    }
    
    @staticmethod
    def parse_place(place_id: str) -> Place:
        """
        Parsea un ID de lugar y retorna su descripción.
        
        Args:
            place_id: ID del lugar (ej: 'p731', 'p02', 'pbuff5')
            
        Returns:
            Place con descripción interpretada
        """
        # Primero chequear lugares genéricos
        if place_id in NomenclatureParser.GENERIC_PLACES:
            return Place(
                id=place_id,
                type="generic",
                description=NomenclatureParser.GENERIC_PLACES[place_id]
            )
        
        # Luego intentar patrones parametrizados
        for pattern, (ptype, template) in NomenclatureParser.PLACE_PATTERNS.items():
            match = re.match(pattern, place_id)
            if match:
                groups = match.groups()
                
                # Extraer i y j según el patrón
                # Para p7ij: groups[0] = j (task = primer valor), groups[1] = i (activity = último valor)
                if len(groups) == 2:
                    j, i = int(groups[0]), int(groups[1])
                    description = template.format(i=i, j=j)
                else:
                    i = int(groups[0])
                    description = template.format(i=i)
                
                return Place(
                    id=place_id,
                    type=ptype,
                    description=description,
                    activity_idx=i,
                    task_idx=j if len(groups) == 2 else None
                )
        
        # Si no coincide nada, retornar descripción genérica
        return Place(
            id=place_id,
            type="unknown",
            description=f"Petri Net place {place_id} (definition not found in schema)"
        )
    
    @staticmethod
    def parse_transition(trans_id: str) -> Transition:
        """
        Parsea un ID de transición y retorna su descripción.
        
        Args:
            trans_id: ID de la transición (ej: 't731', 't0006', 't9')
            
        Returns:
            Transition con descripción interpretada
        """
        # Primero chequear transiciones atómicas
        if trans_id in NomenclatureParser.ATOMIC_TRANSITIONS:
            return Transition(
                id=trans_id,
                type="atomic",
                description=NomenclatureParser.ATOMIC_TRANSITIONS[trans_id]
            )
        
        # Luego intentar patrones parametrizados
        for pattern, (ttype, template) in NomenclatureParser.TRANSITION_PATTERNS.items():
            match = re.match(pattern, trans_id)
            if match:
                groups = match.groups()
                
                # Extraer i y j según el patrón
                # Para t0007ij: groups[0] = j (task = primer valor), groups[1] = i (activity = último valor)
                if len(groups) == 2:
                    j, i = int(groups[0]), int(groups[1])
                    description = template.format(i=i, j=j)
                else:
                    i = int(groups[0])
                    description = template.format(i=i)
                
                return Transition(
                    id=trans_id,
                    type=ttype,
                    description=description,
                    activity_idx=i,
                    task_idx=j if len(groups) == 2 else None
                )
        
        # Si no coincide nada, retornar descripción genérica
        return Transition(
            id=trans_id,
            type="unknown",
            description=f"Petri Net transition {trans_id} (definition not found in schema)"
        )
    
    @staticmethod
    def build_rag_query(node_id: str, node_type: str = "auto") -> str:
        """
        Construye una query RAG precisa basada en nomenclatura.
        
        Args:
            node_id: ID del nodo (ej: 'p731', 't0007')
            node_type: "place", "transition", o "auto" (detección automática)
            
        Returns:
            Query optimizada para RAG
        """
        # Auto-detectar tipo si es necesario
        if node_type == "auto":
            node_type = "place" if node_id.startswith("p") else "transition"
        
        if node_type == "place":
            place = NomenclatureParser.parse_place(node_id)
            
            # Query con contexto de nomenclatura
            if place.type == "generic":
                return f"Generic system place {node_id}: {place.description}. Explain its role in the system."
            elif place.type == "task_level":
                return f"Task-level place {node_id} (format p7ji): {place.description}. What is activity {place.activity_idx} task {place.task_idx}?"
            elif place.type == "activity_level":
                return f"Activity-level place {node_id}: {place.description}. What is the role in activity {place.activity_idx}?"
            elif place.type == "buffer":
                return f"Buffer place {node_id}: {place.description}. How do activities communicate through buffers?"
            else:
                return f"Petri Net place: {node_id}"
        
        else:  # transition
            trans = NomenclatureParser.parse_transition(node_id)
            
            if trans.type == "atomic":
                return f"Atomic system transition {node_id}: {trans.description}. Explain its global system function."
            elif trans.type == "task_level":
                return f"Task-level transition {node_id} (format t0007ji): {trans.description}. How does task {trans.task_idx} execute in activity {trans.activity_idx}?"
            elif trans.type == "activity_level":
                return f"Activity-level transition {node_id}: {trans.description}. What is the lifecycle of activity {trans.activity_idx}?"
            else:
                return f"Petri Net transition: {node_id}"
    
    @staticmethod
    def get_enhanced_description(node_id: str, node_type: str = "auto") -> str:
        """
        Retorna una descripción mejorada del nodo (útil para debugging y logging).
        
        Args:
            node_id: ID del nodo
            node_type: "place" o "transition"
            
        Returns:
            Descripción enriquecida (schema-based)
        """
        if node_type == "auto" or node_type == "place":
            place = NomenclatureParser.parse_place(node_id)
            if place.type != "unknown":
                return f"[{place.type.upper()}] {node_id}: {place.description}"
        
        if node_type == "auto" or node_type == "transition":
            trans = NomenclatureParser.parse_transition(node_id)
            if trans.type != "unknown":
                return f"[{trans.type.upper()}] {node_id}: {trans.description}"
        
        return node_id


# Test y debug
if __name__ == "__main__":
    test_cases = [
        "p731",  # task place task 3 in activity 1
        "p02",   # activity task loop
        "p5",    # work state
        "pbuff2",  # buffer place
        "t0007",  # task 7 execution (pero sin segundo índice)
        "t00015",  # t0007 task 1 activity 5 (INCORRECTO)
        "t000715", # t0007 task 5 activity 1
        "t5",    # work to break
        "t0006",  # maintenance
    ]
    
    print("=" * 60)
    print("NOMENCLATURE PARSER TEST")
    print("=" * 60)
    
    for node_id in test_cases:
        print(f"\n▶ {node_id}")
        
        place = NomenclatureParser.parse_place(node_id)
        trans = NomenclatureParser.parse_transition(node_id)
        
        if place.type != "unknown":
            print(f"  📍 PLACE: {place.description}")
            print(f"     Query: {NomenclatureParser.build_rag_query(node_id, 'place')}")
        else:
            if trans.type != "unknown":
                print(f"  ⚡ TRANSITION: {trans.description}")
                print(f"     Query: {NomenclatureParser.build_rag_query(node_id, 'transition')}")
            else:
                print(f"  ❌ NOT FOUND IN SCHEMA")
