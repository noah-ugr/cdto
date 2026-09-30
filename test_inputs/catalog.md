# Catálogo de inputs de prueba

Cada archivo JSON de este directorio es un input listo para pasar directamente a la pipeline.
Para ejecutarlo localmente, sustituye el dict `input` al final de `pipeline.py` por el contenido del archivo, o llama a la API:

```bash
curl -X POST http://localhost:7071/api/petrinets \
  -H "Content-Type: application/json" \
  -d @test_inputs/input_XX.json
```

---

## Resumen rápido

Las precedencias se leen como las ejecuta el motor: en `taskCode` y `activityCode` la lista nombra
lo que su dueño precede ([data-model.md](../data-model.md#precedence-lists)). `X → Y` significa que
X va antes que Y. Todos estos inputs listan IDs anteriores al dueño, así que dentro de cada cadena el
orden de ejecución es el inverso de la numeración.

| Archivo | runId | Horizonte | Equipos | Actividades | Max tareas/act | Precedencias entre actividades | Caso principal |
|---|---|---|---|---|---|---|---|
| input_14.json | 14 | 168 h (1 semana) | 1 | 1 | 2 | No | Smoke test mínimo |
| input_15.json | 15 | 720 h (1 mes) | 1 | 1 | 10 | No | Cadena larga + fan-in de tareas en T001 |
| input_16.json | 16 | 2160 h (3 meses) | 1 | 2 | 15 | A002 → A001 | Muchas tareas + precedencia entre actividades |
| input_17.json | 17 | 8760 h (1 año) | 1 | 18 | 2 | No | Stress test: muchas actividades |
| input_18.json | 18 | 8760 h (1 año) | 2 | 4 | 4 | A002→A001, A003→{A001,A002} | Cross-team + fan-in de actividades en A001 |
| input_19.json | 19 | 17520 h (2 años) | 1 | 8 | 8 | A005→{A001,A002}, A006→A003, A008→{A004,A007} | Escala: 8 act × 8 tareas |
| input_20.json | 20 | 8760 h (1 año) | 1 | 2 | 29 | A002 → A001 | JSON grande: 29 tareas con precedencias complejas |
| input_21.json | 21 | 720 h (1 mes) | 1 | 1 | 3 | No | T_period > Simulation_period (one-shot) |
| input_22.json | 22 | 2160 h (3 meses) | 1 | 1 | 4 | No | 1 miembro, tareas independientes |
| **input_23.json** | **23** | **8760 h (1 año)** | **1** | **1** | **7** | **No** | **7 tareas + árbol de precedencias Requires_Shutdown** |
| input_24.json | 24 | 8760 h (1 año) | 1 | 13 | 2 | A013 → {A001,A003,A005,A007,A009,A011,A012} | Fan-out máximo en DAG de actividades |
| input_25.json | 25 | 4320 h (6 meses) | 2 | 5 | 4 | A002→A001, A004→A003, A005→{A002,A004} | 2 equipos + precedencias cruzadas + periodos mixtos |

> **input_23.json** es el caso de referencia con exactamente **7 tareas** en una actividad.

---

## Descripción detallada

### input_14 — Smoke test (1 semana, 2 tareas, sin dependencias)

**Objetivo**: verificar que el parser, la validación del modelo y la ejecución básica funcionan
con el input mínimo posible.

| Parámetro | Valor |
|---|---|
| Simulation_period | 168 h |
| Actividades | 1 (A001) |
| Tareas | T001 (6 h), T002 (1 h) — independientes |
| T_period | 72 h |
| Trabajadores | 1 × turno 8 h |

**Sentido temporal**: en cada periodo de 72 h (3 días), el trabajador tiene 3 × 8 = 24 h disponibles.
Las tareas suman 7 h secuenciales → caben holgadamente en un turno. Se producen ~2 ocurrencias en la semana.

---

### input_15 — Cadena larga de tareas con fan-in en T001 (1 mes, 10 tareas)

**Objetivo**: validar el grafo de precedencias internas, el orden topológico y el cálculo del
camino crítico cuando hay fan-in. Cada tarea precede a la anterior, así que T010 va primero y
T001 al final; T005 precede a T004 y a T001, y T008 a T007 y a T001, de modo que T001 espera a
T002, T005 y T008.

| Parámetro | Valor |
|---|---|
| Simulation_period | 720 h |
| T_period | 720 h (una única ocurrencia) |
| Tareas | T010 → … → T001 en cadena, con fan-in en T001 |
| Camino crítico | ≈ 94 h de trabajo |
| Trabajadores | 2 × turno 8 h |

**Sentido temporal**: el periodo coincide con la simulación → una sola ejecución.
Con 2 trabajadores y turnos de 8 h, la capacidad mensual es 30 × 8 = 240 h. El camino crítico
de 94 h ocupa ~12 días laborables, holgura de ~18 días. ✓

---

### input_16 — Pocas actividades, muchas tareas, precedencia entre actividades (3 meses)

**Objetivo**: comprobar que A001 no arranca hasta que A002 ha completado su primera ejecución
(A002 precede a A001). A001 tiene 15 tareas en cadena de T015 a T002 (camino crítico ≈ 153 h de
trabajo); T002 espera además a T005, T010 y T015, y T001 no tiene precedencias. A002 tiene 3 tareas
con un join en T001: T002 y T003 lo preceden.

| Parámetro | Valor |
|---|---|
| Simulation_period | 2160 h |
| T_period (A001/A002) | 720 h |
| Camino crítico A001 | ≈ 153 h |
| Trabajadores | 3 × turno 8 h |

**Sentido temporal**: el camino crítico de A001 (153 h) requiere ~20 días laborables.
En un periodo mensual (30 días laborables disponibles: 30 × 8 = 240 h) cabe con margen. ✓

---

### input_17 — Stress test de muchas actividades (1 año, 18 act., pocas tareas) ✅ VERIFICADO

**Objetivo**: probar la iteración y planificación cuando hay muchas actividades (A001–A018),
cada una con 1 o 2 tareas. Sin dependencias entre actividades.

| Parámetro | Valor |
|---|---|
| Simulation_period | 8760 h |
| Actividades | 18 (A001–A018) |
| T_period | 720 h – 960 h |
| Trabajadores | 4 × turno 6 h |

**Sentido temporal**: la tarea más larga es de 17 h (≈ 3 turnos de 6 h).
Con periodos de 720–960 h (30–40 días), la capacidad por periodo es 30 × 6 = 180 h mínimo.
Las tareas suman como máximo 12 + 17 = 29 h por actividad. Amplia holgura. ✓

---

### input_18 — 2 equipos con precedencias cruzadas y fan-in en A001 (1 año)

**Objetivo**: validar el scheduling multi-equipo cuando A001 (TeamA) no puede arrancar hasta que
A002 (TeamB) y A003 (TeamA) han terminado su primera ocurrencia, y A002 espera a A003.

| Parámetro | Valor |
|---|---|
| Teams | 2 (TeamA y TeamB) |
| Simulation_period | 8760 h |
| A001 camino crítico | T003(25)→T001(30) = 55 h |
| A002 camino crítico | T002(22)→T001(18) = 40 h |
| A003 camino crítico | T002(40)→T001(10) = 50 h |

**Sentido temporal**: los caminos críticos no dependen de la dirección de las listas. Con 2
trabajadores a 8 h/día, el de A001 (55 h) ocupa ~7 días laborables. Las horas de arranque que daba
este apartado (A001 en h=80, A002 tras A001, A003 en ~378 h) suponían el orden inverso al que
ejecuta el motor, que empieza por A003 y termina por A001, y no se han recalculado.

---

### input_19 — Test de escala: 8 actividades × 8 tareas (2 años)

**Objetivo**: combinar muchas actividades (A001–A008) con grafos de tareas medianos y
precedencias entre actividades no triviales: A005 precede a A001 y A002, A006 a A003, y A008 a
A004 y A007.

| Parámetro | Valor |
|---|---|
| Simulation_period | 17520 h |
| Actividades | 8, cada una con 8 tareas |
| T_period | 840 h – 960 h |
| Trabajadores | 5 × turno 8 h |
| Camino crítico por actividad | ≈ 110–136 h |

**Sentido temporal**: con T_period=840 h (35 días), los 5 trabajadores tienen 35 × 8 = 280 h
disponibles por periodo. Los caminos críticos (<136 h) caben con holgura. ✓

---

### input_20 — Actividad gigante con 29 tareas (1 año)

**Objetivo**: test de rendimiento con un JSON grande: A001 tiene 29 tareas y un grafo de
precedencias muy ramificado (T029 va primero y precede a T028, T010, T014 y T021).
A002 precede a A001 y tiene 2 tareas.

| Parámetro | Valor |
|---|---|
| Simulation_period | 8760 h |
| A001 tareas | 29 |
| T_period A001 | 1440 h (2 meses) |
| Trabajadores | 6 × turno 8 h |

**Sentido temporal**: con un periodo de 1440 h (60 días) y 6 trabajadores a 8 h/día, la
capacidad disponible es 60 × 8 = 480 h. El camino crítico de A001 (ruta más larga ≈ 212 h)
cabe con amplio margen. ✓

---

### input_21 — T_period > Simulation_period: actividad one-shot (1 mes)

**Objetivo**: probar el caso límite en que el periodo es mayor que el horizonte de simulación,
lo que implica que la actividad se ejecuta como máximo una vez.

| Parámetro | Valor |
|---|---|
| Simulation_period | 720 h |
| T_period | 1000 h (> 720 h) |
| Start_disp | 10 h |
| Tareas | {T002(10 h), T003(12 h)}→T001(20 h) |
| Trabajadores | 2 × turno 8 h |

**Sentido temporal**: la actividad dispara una única vez en h=10. Con T_wait=2 h, el trabajo
arranca en h=12. El camino crítico (T003→T001 = 32 h) requiere ~4 días laborables en los
708 h calendario restantes (≈ 236 h de capacidad). ✓

---

### input_22 — 1 miembro, turno 8 h, tareas independientes (3 meses)

**Objetivo**: validar que el planificador soporta personal mínimo (1 trabajador) y tareas
sin dependencias internas (T001–T004 son independientes).

| Parámetro | Valor |
|---|---|
| Simulation_period | 2160 h |
| T_period | 600 h |
| T_wait | 6 h |
| Tareas | T001(4 h), T002(3 h req. shutdown), T003(2 h), T004(2 h) — independientes |
| Trabajadores | 1 × turno 8 h |

**Sentido temporal**: con 1 trabajador las tareas se ejecutan en serie: 4+3+2+2=11 h.
Por periodo (600 h ≈ 25 días), hay 25 × 8 = 200 h disponibles. ✓

---

### input_23 — **7 tareas**, árbol binario de Requires_Shutdown (1 año) ⭐

**Objetivo**: test de cobertura específico para 7 tareas en una actividad.
Estructura de árbol con raíz en T007, que va primero: T007→{T005, T006}, T005→{T001, T002},
T006→{T003, T004}.
Todas las hojas y nodos intermedios tienen Requires_Shutdown=true; solo T007 es false.

| Parámetro | Valor |
|---|---|
| Simulation_period | 8760 h |
| Tareas | 7 (T001–T007), Duration=1 h cada una |
| T_period | 720 h |
| T_wait | 1 h |
| Start_disp | 30 h |
| Trabajadores | 2 × turno 8 h |
| Camino crítico | T007→T005→T001 = 3 h |

**Sentido temporal**: camino crítico de 3 h. Con T_wait=1 h, el trabajo comienza 1 h después
del trigger. Capacidad mensual: (720−1)/24 × 8 ≈ 240 h. Amplia holgura. ✓
Se producen ~12 ocurrencias en el año (8760/720 ≈ 12.2).

---

### input_24 — Fan-out máximo en DAG de actividades (1 año, 13 actividades)

**Objetivo**: validar que el algoritmo resuelve correctamente un fork con muchos sucesores:
A013 precede a A001, A003, A005, A007, A009, A011 y A012 (7 actividades), que esperan todas a
A013. Ninguna actividad tiene más de un predecesor, así que este input no ejercita un join AND.

| Parámetro | Valor |
|---|---|
| Simulation_period | 8760 h |
| Actividades | 13 (A001–A013) |
| T_period | 840 h (uniforme) |
| Tareas por actividad | 2 (T002→T001) |
| Trabajadores | 4 × turno 8 h |

**Sentido temporal**: cada actividad tiene ≤ 16+12=28 h de trabajo secuencial.
Con T_period=840 h (35 días × 8 h = 280 h/periodo), sobra capacidad para todas. ✓

---

### input_25 — 2 equipos, periodos distintos, precedencias encadenadas (6 meses)

**Objetivo**: escenario realista con TeamA y TeamB asignados a distintas actividades,
periodos variados y precedencias encadenadas: A005 precede a A002 y A004, A002 a A001, y A004 a
A003.

| Parámetro | Valor |
|---|---|
| Teams | **2** (corregido; original declaraba `"Teams": 1`) |
| Simulation_period | 4320 h |
| Actividades | 5 (A001–A005) |
| T_period | 360 h – 960 h |
| Shift_duration | 6 h (A003/A004) u 8 h (A001/A002/A005) |

**Corrección aplicada**: el input original declaraba `"Teams": 1` pero usaba dos equipos
distintos (`"Team": "TeamA"` y `"Team": "TeamB"`). Se ha corregido a `"Teams": 2`.

**Sentido temporal**:
- A001 (TeamA, T_period=480 h): 3 tareas, camino crítico 1+max(1,1)=2 h (T003 precede a T001 y T002) → mínimo coste. ✓
- A002 (TeamB, T_period=720 h): 4 tareas, crítico T004(1)→T003(6)→T001(8)=15 h. ✓
- A003 (TeamA, T_period=360 h, turno 6 h): T001=18 h → 3 turnos de 6 h. ✓
- A004 (TeamB, T_period=360 h, turno 6 h): T001(10)+T002(14)=24 h → 4 turnos. ✓
- A005 (TeamA, T_period=960 h): crítico 20+max(6,8)=28 h (T003 precede a T001 y T002). Con T_wait=8 h, arranca tarde
  pero tiene 40 días de capacidad por periodo. ✓

---

## Incidencias conocidas

| Input | Incidencia | Estado |
|---|---|---|
| input_25 | `"Teams": 1` con dos equipos → corregido a `"Teams": 2` | **Corregido** |
| input_14 | `"Start_disp": 0` (primer trigger en t=0) — caso límite | Sin cambios, válido |
| input_23 | `Duration: 1` en todas las tareas — duraciones muy cortas pero válidas | Sin cambios, válido |
