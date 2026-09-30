# Documentación de Red de Petri - Configuración Específica

## Resumen de la Configuración

### Parámetros Globales

- **Simulation Period**: 2000 horas
- **Teams Available**: 1
- **Run ID**: 25

### Actividades y Tareas

| Activity | Tasks | T_period | T_wait | Start_disp | Team |
|----------|-------|----------|--------|-----------|------|
| A001 | 3 | 480 | 2 | 3 | TeamA |
| A002 | 4 | 720 | 4 | 1 | TeamA |

### Detalles de Tareas

| Activity | Task | Duration | Requires_Shutdown | Precedes |
|----------|------|----------|------------------|----------|
| A001 | T001 | 10 | False | None |
| A001 | T002 | 30 | True | None |
| A001 | T003 | 40 | False | T001, T002 |
| A002 | T001 | 80 | False | None |
| A002 | T002 | 100 | False | T001 |
| A002 | T003 | 60 | True | T001 |
| A002 | T004 | 10 | False | T002, T003 |

---

## Configuración de Lugares

### Lugares Genéricos

- $p3$: team-capacity pool.
- $p4$: maintenance lock / allocation place.
- $p5$: work-state indicator.
- $p6$: break-state indicator.
- $p0$: global "system operational" place.

### Per-Activity Places


**Activity 1 (A001)**:
- $p11$: activity ready to start.
- $p021$: activity in the task loop state.
- $p81$: activity completion place.
- $p001$: initial place for activity 1.
- $p10$: initial state within activity 1 subnet.

**Activity 2 (A002)**:
- $p12$: activity ready to start.
- $p022$: activity in the task loop state.
- $p82$: activity completion place.
- $p002$: initial place for activity 2.
- $p20$: initial state within activity 2 subnet.

### Per-Task Places


**Activity 1**:
- $p711$: internal task place for task 1 in activity 1.
- $p721$: internal task place for task 2 in activity 1.
- $p731$: internal task place for task 3 in activity 1.

**Activity 2**:
- $p712$: internal task place for task 1 in activity 2.
- $p722$: internal task place for task 2 in activity 2.
- $p732$: internal task place for task 3 in activity 2.
- $p742$: internal task place for task 4 in activity 2.

### Buffer Places

Para comunicación inter-actividad:

- `pbuff1`: buffer place for activity A001.
- `pbuff2`: buffer place for activity A002.

### Initial Markings

- $p001 = 1$: initial marking for activity 1.
- $p002 = 1$: initial marking for activity 2.

- $p0 = 1$: global operational state.
- $p5 = 1$: initially in work state.

---

## Configuración de Transiciones

### Atomic (Global) Transitions

- $t3$: allocation of workers (team allocation).
- $t4$: transition from break to work state.
- $t5$: transition from work to break state.
- $t9$: global reset transition.

### Activity-Level Transitions


**Activity 1**:
- $t10$: activation of activity 1.
- $t11$: entry into the task loop.
- $t12$: completion and return to $p10$.
- $t00061$: maintenance loop transition.
- $t00081$: completion transition feeding $p81$ and buffer places.

**Activity 2**:
- $t20$: activation of activity 2.
- $t21$: entry into the task loop.
- $t22$: completion and return to $p20$.
- $t00062$: maintenance loop transition.
- $t00082$: completion transition feeding $p82$ and buffer places.

### Task-Level Transitions


**Activity 1**:
- $t000711$: execution of task 1 in activity 1.
- $t000721$: execution of task 2 in activity 1.
- $t000731$: execution of task 3 in activity 1.

**Activity 2**:
- $t000712$: execution of task 1 in activity 2.
- $t000722$: execution of task 2 in activity 2.
- $t000732$: execution of task 3 in activity 2.
- $t000742$: execution of task 4 in activity 2.

### Tabla Consolidada de Transiciones

| Transition | Activity | Meaning |
|----------|----------|---------|
| $t001$ | 1 | Activate activity 1 |
| $t10$ | 1 | Entry to activity 1 subnet |
| $t11$ | 1 | Enter task loop in activity 1 |
| $t12$ | 1 | Complete activity 1 |
| $t00061$ | 1 | Maintenance loop in activity 1 |
| $t00081$ | 1 | Completion (feeds pbuff1) |
| $t000711$ | 1 | Execute task 1 |
| $t000721$ | 1 | Execute task 2 |
| $t000731$ | 1 | Execute task 3 |
| $t002$ | 2 | Activate activity 2 |
| $t20$ | 2 | Entry to activity 2 subnet |
| $t21$ | 2 | Enter task loop in activity 2 |
| $t22$ | 2 | Complete activity 2 |
| $t00062$ | 2 | Maintenance loop in activity 2 |
| $t00082$ | 2 | Completion (feeds pbuff2) |
| $t000712$ | 2 | Execute task 1 |
| $t000722$ | 2 | Execute task 2 |
| $t000732$ | 2 | Execute task 3 |
| $t000742$ | 2 | Execute task 4 |


---

## Configuración de Arcos

### Activity Flow Arcs (Detailed)


**Activity 1**:
$$
p001 \rightarrow t001 \rightarrow p11 \rightarrow t11 \rightarrow p021 \rightarrow t12 \rightarrow p10
$$

**Activity 2**:
$$
p002 \rightarrow t002 \rightarrow p12 \rightarrow t21 \rightarrow p022 \rightarrow t22 \rightarrow p20
$$

### Task Flow Arcs (Detailed)


**Task 1 in Activity 1**:
$$
p021 \leftrightarrow t000711 \leftrightarrow p711
$$

**Task 2 in Activity 1**:
$$
p021 \leftrightarrow t000721 \leftrightarrow p721
$$

**Task 3 in Activity 1**:
$$
p021 \leftrightarrow t000731 \leftrightarrow p731
$$

**Task 1 in Activity 2**:
$$
p022 \leftrightarrow t000712 \leftrightarrow p712
$$

**Task 2 in Activity 2**:
$$
p022 \leftrightarrow t000722 \leftrightarrow p722
$$

**Task 3 in Activity 2**:
$$
p022 \leftrightarrow t000732 \leftrightarrow p732
$$

**Task 4 in Activity 2**:
$$
p022 \leftrightarrow t000742 \leftrightarrow p742
$$

### Task Flow with Team Weights

Para cada tarea $j$ en actividad $i$, los arcos desde $p3$ son ponderados según los requisitos específicos del input.

### Maintenance and System Behavior

- Ciclo de trabajo/descanso: $p5 \rightarrow t5 \rightarrow p6 \rightarrow t4 \rightarrow p5$
- Reset global $t9$: reinicia $p3$, $p4$, $p6$ e inicializa $p5$ y todos los $p20$

### Precedence Constraints (Task-Level)


**A001.T003** precedes T001 and T002
- Arc: $p731 \rightarrow t000711$ (T001 runs only after T003 has run)
- Arc: $p731 \rightarrow t000721$ (T002 runs only after T003 has run)

**A002.T002** precedes T001
- Arc: $p722 \rightarrow t000712$ (T001 runs only after T002 has run)

**A002.T003** precedes T001
- Arc: $p732 \rightarrow t000712$ (T001 runs only after T003 has run)

**A002.T004** precedes T002 and T003
- Arc: $p742 \rightarrow t000722$ (T002 runs only after T004 has run)
- Arc: $p742 \rightarrow t000732$ (T003 runs only after T004 has run)


### Precedence Constraints (Activity-Level)


**A002** precedes A001
- Inhibitor arc: $p022 \rightarrow t11$ (activity 1 cannot enter its task loop while activity 2 is in its task loop)
- Arc: $pbuff2 \rightarrow t11$ (activity 1 enters its task loop with the token activity 2 leaves when it completes its tasks)


### Buffer Communication Between Activities

- $t00081 \rightarrow pbuff1$: produces token when activity 1 completes.
- $t00082 \rightarrow pbuff2$: produces token when activity 2 completes.


### Arc Enrichment Metadata

All arcs are enriched with:
- **ActivityID**: Activity identifier (A001, A002, etc.)
- **TaskID**: Task identifier (T001, T002, etc.)
- **Team**: Team assigned
- **T_period**: Repetition period
- **T_wait**: Waiting time
- **Start_disp**: Start displacement

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Activities | 2 |
| Total Tasks | 7 |
| Activities that precede others | 1 |
| Buffer Places | 2 |
| Generic Places | 5 |
