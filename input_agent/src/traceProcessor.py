"""
Author: Noah Masegosa Caceres 
Center: @ugr

TraceProcessor: Usa teoría de sparse matrices para comprimir la traza de disparos de un PetriNet,
    generando una representación jerárquica y legible del sistema a lo largo del tiempo.

Metodos principales:
    - compress_nested_trace: Agrupa eventos por tiempo, preservando solo transiciones disparadas y lugares activos (tokens > 0).
        Elimina lugares con 0 tokens para reducir la dispersión y mejorar la legibilidad de la evolución temporal del sistema.
"""


import json
import pandas as pd

class TraceProcessor:
    def __init__(self, M_k_path, general_outputs_path):
        self.df_trace = pd.read_excel(M_k_path)
        with open(general_outputs_path, 'r') as f:
            self.stats = json.load(f)

    def compress_nested_trace(self):
        """
        Genera una estructura jerárquica (Time -> Events -> State) preservando el orden 
        secuencial de los disparos y eliminando lugares con 0 tokens (dispersión).

        La idea es crear una representación más compacta y legible de la evolución del sistema a lo largo del tiempo,
        enfocándose solo en los eventos relevantes (disparos de transiciones y lugares activos). Es algo que solía hacer
        para matrices sparse.

        Returns:
            dict: { "TIME": {"t00i": {"p00i": X, "p00j": Y}, "t00j": {...}}, "TIME2": {...}} }
        """
        timeline = {}
        
        for t, group in self.df_trace.groupby('time'):
            t_str = str(t)
            transition = {}
            for idx, row in group.iterrows():
                trans_name = str(row['transitions'])
                
                active_tokens = {
                    k: int(v) 
                    for k, v in row.items() 
                    if str(k).startswith('p') and v > 0
                }
                
                transition[trans_name] = active_tokens
            
            timeline[t_str] = transition
            
        return timeline