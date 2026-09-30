# Discordant pairs: B and C differ in exact match (planner_executor)

Fill the `cause` column with one of:
- `humanisation`: the difference comes from the new request text (it drops, adds or changes something the instruction asks, e.g. an inverted precedence);
- `model`: the new request is faithful and the difference comes from how gpt-oss:20b reads it;
- `unclear`.

compare keeps the causes filled here when it rewrites this file. Once every row has a cause it also reports C - B without the samples classified as `humanisation`.

| axis | level | sample_idx | EM B | EM C | cause |
|---|---|---|---|---|---|
| complexity | 1 | 17 | 0 | 1 | model |
| complexity | 16 | 791 | 0 | 1 | humanisation |
| completeness | 1 | 2 | 1 | 0 | humanisation |
| completeness | 1 | 23 | 1 | 0 | humanisation |
| completeness | 1 | 33 | 1 | 0 | model |
| completeness | 1 | 41 | 1 | 0 | humanisation |
| completeness | 1 | 48 | 1 | 0 | humanisation |
| completeness | 5 | 201 | 0 | 1 | unclear |
| completeness | 5 | 205 | 1 | 0 | humanisation |
| completeness | 5 | 206 | 0 | 1 | humanisation |
| completeness | 5 | 211 | 1 | 0 | humanisation |
| completeness | 5 | 226 | 1 | 0 | humanisation |
| completeness | 5 | 233 | 1 | 0 | model |
| completeness | 5 | 236 | 1 | 0 | humanisation |
| completeness | 5 | 237 | 1 | 0 | humanisation |
| completeness | 5 | 243 | 1 | 0 | humanisation |
| completeness | 5 | 248 | 1 | 0 | model |
| completeness | 10 | 450 | 1 | 0 | humanisation |
| completeness | 10 | 459 | 1 | 0 | humanisation |
| completeness | 10 | 465 | 1 | 0 | humanisation |
| completeness | 10 | 466 | 1 | 0 | humanisation |
| completeness | 10 | 467 | 0 | 1 | model |
| completeness | 10 | 469 | 1 | 0 | humanisation |
| completeness | 10 | 474 | 1 | 0 | humanisation |
| completeness | 10 | 475 | 1 | 0 | humanisation |
| completeness | 10 | 478 | 1 | 0 | humanisation |
| completeness | 10 | 479 | 1 | 0 | humanisation |
| completeness | 10 | 480 | 1 | 0 | humanisation |
| completeness | 10 | 482 | 1 | 0 | humanisation |
| completeness | 10 | 486 | 1 | 0 | unclear |
| completeness | 10 | 488 | 1 | 0 | humanisation |
| completeness | 10 | 491 | 1 | 0 | humanisation |
| completeness | 10 | 497 | 1 | 0 | humanisation |
| completeness | 15 | 701 | 1 | 0 | humanisation |
| completeness | 15 | 708 | 1 | 0 | humanisation |
| completeness | 15 | 711 | 1 | 0 | humanisation |
| completeness | 15 | 714 | 1 | 0 | humanisation |
| completeness | 15 | 719 | 1 | 0 | humanisation |
| completeness | 15 | 724 | 1 | 0 | humanisation |
| completeness | 15 | 725 | 1 | 0 | humanisation |
| completeness | 15 | 727 | 1 | 0 | humanisation |
| completeness | 15 | 735 | 1 | 0 | humanisation |
| completeness | 15 | 743 | 1 | 0 | humanisation |

## complexity level 1, sample 17 (EM B 0, EM C 1)

**Technical instruction**

1. `SET A001.Team members = 3`

**Original request (B)**: Cambia la dotación de la actividad A-001 a 3.

**New request (C)**: Cambia la dotación de la actividad A001 para que tenga 3 operarios asignados.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET A001.Team = "3"`

**Edits that differ from the GT in B**

- `A001.Team`: GT "TeamA" / prediction "3"
- `A001.Team members`: GT 3 / prediction 2

**Batch emitted by gpt-oss:20b in C**

- `SET A001.Team members = 3`

**Edits that differ from the GT in C**

- none (exact match)


## complexity level 16, sample 791 (EM B 0, EM C 1)

**Technical instruction**

1. `APPEND A001.tasks.T008.Order_Before = "T006"`

**Original request (B)**: Añade la regla de que la tarea 6 de la actividad 1 debe terminar antes de que comience la tarea 8.

**New request (C)**: Añade una restricción para que la tarea T008 de la actividad A001 tenga que terminar antes de empezar la tarea T006.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `APPEND A001.tasks.T006.Order_Before = "T008"`

**Edits that differ from the GT in B**

- `A001.tasks.T006.Order_Before`: GT ["T007"] / prediction ["T007", "T008"]
- `A001.tasks.T008.Order_Before`: GT ["T009", "T006"] / prediction ["T009"]

**Batch emitted by gpt-oss:20b in C**

- `APPEND A001.tasks.T008.Order_Before = "T006"`

**Edits that differ from the GT in C**

- none (exact match)


## completeness level 1, sample 2 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A001.Shift_duration = 13`

**Original request (B)**: Cambia la duración del turno de la primera actividad a 13.

**New request (C)**: Cambia la duración del turno para la actividad A-001 a 13 horas y asegúrate de que tenemos los equipos totales disponibles, que son 3.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET A001.Shift_duration = 13`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A001.Shift_duration = 13`
- `SET A001.Team = 3`

**Edits that differ from the GT in C**

- `A001.Team`: GT "TeamA" / prediction 3


## completeness level 1, sample 23 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A004.T_wait = 18`

**Original request (B)**: Cambia el margen de espera de la actividad 4 a 18.

**New request (C)**: Mira, ajusta el tiempo de espera para la actividad 4 a 18 minutos y asegúrate de que todo lo demás siga igual, especialmente el número de equipos totales que sigue siendo 2.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: #1 T_wait = 18: '18 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET A004.T_wait = 18`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A004.T_wait = 0.3`

**Edits that differ from the GT in C**

- `A004.T_wait`: GT 18 / prediction 0.3


## completeness level 1, sample 33 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A004.tasks.T001.Order_Before`

**Original request (B)**: Borra el parámetro de precedencia de la tarea 1 de la actividad 4, es decir, elimina la regla que obligaba a que esa tarea terminara antes de otra.

**New request (C)**: Mira, quita la regla que obligaba a que la tarea 1 de la actividad A004 terminara antes de empezar cualquier otra cosa.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A004.tasks.T001.Order_Before`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- (no instructions)
- error: Planner Error: Empty LLM response

**Edits that differ from the GT in C**

- `A004.tasks.T001.Order_Before`: not in the GT (prediction [])


## completeness level 1, sample 41 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A001.T_wait = 47`

**Original request (B)**: Ajusta la demora antes de repetir de la actividad 1 a 47

**New request (C)**: Mira, ajusta el tiempo de espera de la actividad A-001 a 47 minutos y anota que tenemos un total de 12 equipos disponibles en fábrica.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: #1 T_wait = 47: '47 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET A001.T_wait = 47`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A001.T_wait = 0.7833`
- `SET Teams = 12`

**Edits that differ from the GT in C**

- `A001.T_wait`: GT 47 / prediction 0.7833


## completeness level 1, sample 48 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A001.T_wait = 41`

**Original request (B)**: Cambia el margen de espera de la actividad 1 a 41.

**New request (C)**: Por favor, ajusta el tiempo de espera para la actividad A-001 a 41 minutos y asegúrate de que tenemos los 10 equipos totales listos.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: #1 T_wait = 41: '41 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET A001.T_wait = 41`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A001.T_wait = 0.6833333333333333`
- `SET Teams = 10`

**Edits that differ from the GT in C**

- `A001.T_wait`: GT 41 / prediction 0.6833333333333333


## completeness level 5, sample 201 (EM B 0, EM C 1)

**Technical instruction**

1. `SET A002.Activity_Order_Enforced = true`
2. `DELETE A003.tasks.T002.Order_Enforced`
3. `DELETE A005.Start_disp`
4. `APPEND A004.Activity_Order_Before = "A008"`
5. `REMOVE_ITEM A004.Activity_Order_Before = "A005"`

**Original request (B)**: Mira, activa la secuencia estricta de la actividad 2, elimina la obligación de forzar orden de la tarea 2 dentro de la actividad 3, borra el desplazamiento inicial de la actividad 5, añade que la actividad 4 debe terminar antes de que empiece la actividad 8 y quita la regla que obligaba a que la actividad 4 terminara antes de la actividad 5.

**New request (C)**: Por favor, activa la secuencia estricta para la actividad 2, borra la obligatoriedad de orden para la tarea 2 dentro de la actividad 3 y también quita el desplazamiento inicial de la actividad 5. Además, haz que ahora la actividad 4 dependa de terminar antes de empezar la actividad 8 y asegúrate de eliminar la regla que forzaba a que la actividad 4 termine antes de la actividad 5.

**Fidelity of the new request**: ok; direction warnings: #4 A004.Activity_Order_Before = A008 (activity 4 before activity 8), text reads 'activity 4 ... depend ... activity 8': "haz que ahora la actividad 4 dependa de terminar antes de empezar la actividad 8"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET A002.Activity_Order_Enforced = true`
- `SET A003.tasks.T002.Order_Enforced = false`
- `DELETE A005.Start_disp`
- `APPEND A004.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A004.Activity_Order_Before = "A005"`

**Edits that differ from the GT in B**

- `A003.tasks.T002.Order_Enforced`: not in the GT (prediction false)

**Batch emitted by gpt-oss:20b in C**

- `SET A002.Activity_Order_Enforced = true`
- `DELETE A003.tasks.T002.Order_Enforced`
- `DELETE A005.Start_disp`
- `APPEND A004.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A004.Activity_Order_Before = "A005"`

**Edits that differ from the GT in C**

- none (exact match)


## completeness level 5, sample 205 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Teams = 13`
2. `SET A003.T_wait = 13`
3. `DELETE A005.tasks.T001.Requires_Shutdown`
4. `APPEND A006.Activity_Order_Before = "A008"`
5. `REMOVE_ITEM A004.Activity_Order_Before = "A005"`

**Original request (B)**: Pon el número de equipos totales a 13 y, para la actividad 3, ajusta el tiempo de espera a 13; elimina la restricción que la tarea 1 de la actividad 5 necesita apagar la máquina; añade a la actividad 6 que debe terminar antes de que empiece la actividad 8 y quita la regla que obligaba a que la actividad 4 terminara antes de empezar la actividad 5.

**New request (C)**: Mira, necesito que cambies el número de equipos disponibles en fábrica a 13 y también ajustes el tiempo de espera de la actividad A-003 a 13 minutos. Además, borra la restricción de que la tarea T001 requiera parar la máquina en la actividad A005, haz que ahora la actividad A006 dependa de terminar primero la actividad A008 y quita la regla que obligaba a que A004 terminara antes de empezar A005.

**Fidelity of the new request**: ok; direction warnings: #4 A006.Activity_Order_Before = A008 (activity 6 before activity 8), text reads 'activity 6 ... depend ... activity 8': "haz que ahora la actividad a006 dependa de terminar primero la actividad a008"; unit warnings: #1 Teams = 13: '13 minutos' | #2 T_wait = 13: '13 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 13`
- `SET A003.T_wait = 13`
- `DELETE A005.tasks.T001.Requires_Shutdown`
- `APPEND A006.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A004.Activity_Order_Before = "A005"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET Teams = 13`
- `SET A003.T_wait = 0.2166666667`
- `DELETE A005.tasks.T001.Requires_Shutdown`
- `APPEND A006.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A004.Activity_Order_Before = "A005"`

**Edits that differ from the GT in C**

- `A003.T_wait`: GT 13 / prediction 0.2166666667


## completeness level 5, sample 206 (EM B 0, EM C 1)

**Technical instruction**

1. `DELETE A005.tasks.T002.Requires_Shutdown`
2. `DELETE A007.Team`
3. `SET A003.tasks.T002.Order_Enforced = true`
4. `APPEND A008.Activity_Order_Before = "A005"`
5. `REMOVE_ITEM A005.tasks.T001.Order_Before = "T002"`

**Original request (B)**: Borra la necesidad de que la tarea 2 de la actividad 5 requiera parada. Elimina la cuadrilla asignada a la actividad 7. Activa la obligación de que la tarea 2 de la actividad 3 siga la secuencia estricta y haz que la actividad 8 termine antes de que empiece la actividad 5. Quita la regla que obligaba a que la tarea 1 de la actividad 5 terminara antes de la tarea 2.

**New request (C)**: Mira, necesito que elimines el requisito de parada para la tarea 2 de la actividad 5 y también quita la asignación del equipo para la actividad 7. Además, pon a true la obligatoriedad de la secuencia para la tarea 2 en la actividad 3. Ahora, añade una dependencia haciendo que la actividad 8 no pueda empezar hasta que termine la actividad 5 y finalmente quita la regla que obligaba a que la tarea 1 de la actividad 5 terminara antes de comenzar la tarea 2.

**Fidelity of the new request**: ok; direction warnings: #4 A008.Activity_Order_Before = A005 (activity 8 before activity 5), text reads 'activity 8 ... hasta que ... activity 5': "anade una dependencia haciendo que la actividad 8 no pueda empezar hasta que termine la actividad 5"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A005.tasks.T002.Requires_Shutdown`
- `DELETE A007.Team members`
- `SET A003.tasks.T002.Order_Enforced = true`
- `APPEND A008.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A005.tasks.T001.Order_Before = "T002"`

**Edits that differ from the GT in B**

- `A007.Team`: not in the GT (prediction "TeamG")
- `A007.Team members`: missing from the prediction (GT 1)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A005.tasks.T002.Requires_Shutdown`
- `DELETE A007.Team`
- `SET A003.tasks.T002.Order_Enforced = true`
- `APPEND A008.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A005.tasks.T001.Order_Before = "T002"`

**Edits that differ from the GT in C**

- none (exact match)


## completeness level 5, sample 211 (EM B 1, EM C 0)

**Technical instruction**

1. `SET runId = 3952`
2. `SET A001.Start_disp = 105`
3. `DELETE A002.tasks.T001.Cost_per_hour`
4. `APPEND A001.tasks.T006.Order_Before = "T005"`
5. `REMOVE_ITEM A002.tasks.T005.Order_Before = "T006"`

**Original request (B)**: Pon el identificador de ejecución a 3952 y ajusta el desplazamiento inicial de la actividad 1 a 105, borra el dato de costo por hora de la tarea 1 de la actividad 2, añade que la tarea 6 de la actividad 1 debe terminar antes de que empiece la tarea 5 de la misma, y quita la regla que obligaba a que la tarea 5 de la actividad 2 terminara antes de empezar la tarea 6 de la actividad 2.

**New request (C)**: Mira, pon el runId a 3952 y ajusta el desplazamiento inicial de la actividad A-001 a 105 minutos. Después, borra el dato del costo por hora de la tarea T001 en la actividad A002 porque ya no lo necesitamos. Además, haz que ahora también dependa la tarea T006 de que termine la tarea T005 en la actividad A-001 y quita la regla que obligaba a que la tarea T005 terminara antes de empezar T006 en la actividad A002.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: #2 Start_disp = 105: '105 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET runId = 3952`
- `SET A001.Start_disp = 105`
- `DELETE A002.tasks.T001.Cost_per_hour`
- `APPEND A001.tasks.T006.Order_Before = "T005"`
- `REMOVE_ITEM A002.tasks.T005.Order_Before = "T006"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET runId = 3952`
- `SET A001.Start_disp = 1.75`
- `DELETE A002.tasks.T001.Cost_per_hour`
- `APPEND A001.tasks.T006.Order_Before = "T005"`
- `REMOVE_ITEM A002.tasks.T006.Order_Before = "T005"`

**Edits that differ from the GT in C**

- `A001.Start_disp`: GT 105 / prediction 1.75
- `A002.tasks.T005.Order_Before`: GT [] / prediction ["T006"]


## completeness level 5, sample 226 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A003.tasks.T001.Cost_per_hour = 490`
2. `DELETE A004.tasks.T004.Duration`
3. `DELETE A003.tasks.T004.Order_Before`
4. `APPEND A004.Activity_Order_Before = "A003"`
5. `REMOVE_ITEM A001.tasks.T003.Order_Before = "T004"`

**Original request (B)**: Por favor, cambia el costo por hora de la tarea 1 de la actividad 3 a 490, borra el tiempo de proceso de la tarea 4 de la actividad 4 y elimina la regla de orden antes de la tarea 4 en la actividad 3; además, añade que la actividad 4 termine antes de que empiece la actividad 3 y quita la dependencia que hacía que la tarea 3 de la actividad 1 terminara antes de la tarea 4.

**New request (C)**: Ajusta el costo por hora de la tarea 1 de la actividad A-003 a 490 euros, borra la duración de la tarea 4 de la actividad A-004 y también quita la regla que obligaba al paso 4 de la tarea A-003 de terminar antes de empezar la siguiente, además, añade a la actividad A-004 para que ahora también dependa de que la actividad A-003 termine primero y finalmente elimina la dependencia de que el paso 3 de la tarea A-001 vaya antes del paso 4.

**Fidelity of the new request**: ok; direction warnings: #4 A004.Activity_Order_Before = A003 (activity 4 before activity 3), text reads 'activity 4 ... depend ... activity 3': "anade a la actividad a-004 para que ahora tambien dependa de que la actividad a-003 termine primero"; unit warnings: #1 Cost_per_hour = 490: '490 euros'

**Batch emitted by gpt-oss:20b in B**

- `SET A003.tasks.T001.Cost_per_hour = 490`
- `DELETE A004.tasks.T004.Duration`
- `DELETE A003.tasks.T004.Order_Before`
- `APPEND A004.Activity_Order_Before = "A003"`
- `REMOVE_ITEM A001.tasks.T003.Order_Before = "T004"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- (no instructions)
- error: Planner Error: Empty LLM response

**Edits that differ from the GT in C**

- `A001.tasks.T003.Order_Before`: GT [] / prediction ["T004"]
- `A003.tasks.T001.Cost_per_hour`: GT 490 / prediction 434
- `A003.tasks.T004.Order_Before`: not in the GT (prediction [])
- `A004.Activity_Order_Before`: GT ["A003"] / prediction []
- `A004.tasks.T004.Duration`: not in the GT (prediction 45)


## completeness level 5, sample 233 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A001.Team members = 10`
2. `SET runId = 8530`
3. `DELETE A001.Team members`
4. `APPEND A001.tasks.T010.Order_Before = "T015"`
5. `REMOVE_ITEM A001.tasks.T011.Order_Before = "T013"`

**Original request (B)**: Pon la dotación de la actividad 1 a 10 operarios y luego elimina ese dato, actualiza el identificador de ejecución a 8530, añade que la tarea 10 debe terminar antes de que empiece la tarea 15 y elimina la regla que hacía obligatoria que la tarea 11 terminara antes de la tarea 13.

**New request (C)**: Por favor, ajusta el personal asignado a 10 para la actividad A-001 y también actualiza el ID de ejecución a 8530, luego borra por completo el dato del tamaño de la cuadrilla en esa misma actividad, además añade que ahora la tarea T010 debe terminar antes de que empiece T015, y finalmente quita la regla que obligaba a que T011 termine antes de empezar T013.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET A001.Team members = 10`
- `DELETE A001.Team members`
- `SET runId = 8530`
- `APPEND A001.tasks.T010.Order_Before = "T015"`
- `REMOVE_ITEM A001.tasks.T011.Order_Before = "T013"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- (no instructions)
- error: Planner Error: Empty LLM response

**Edits that differ from the GT in C**

- `A001.Team members`: not in the GT (prediction 8)
- `A001.tasks.T010.Order_Before`: GT ["T011", "T015"] / prediction ["T011"]
- `A001.tasks.T011.Order_Before`: GT ["T012"] / prediction ["T012", "T013"]
- `runId`: GT 8530 / prediction 380


## completeness level 5, sample 236 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Simulation_period = 13896`
2. `SET A001.tasks.T010.Duration = 45`
3. `DELETE A001.Team members`
4. `APPEND A001.tasks.T007.Order_Before = "T012"`
5. `REMOVE_ITEM A001.tasks.T008.Order_Before = "T009"`

**Original request (B)**: Por favor, cambia el horizonte de simulación a 13896, ajusta la duración de la tarea 10 a 45 y borra el dato de dotación de la actividad 1. Añade a la tarea 7 que debe terminar antes de la tarea 12 y quita la regla que obligaba a que la tarea 8 terminara antes de la tarea 9.

**New request (C)**: Mira, necesito que ajustes el horizonte de simulación a 13896 y también que cambies la duración de la tarea T010 de la actividad A001 a 45 minutos. Además, borra el dato de la dotación del equipo asignado en esa misma actividad A001. Haz que ahora también dependa la tarea T007 de la tarea T012 antes de empezar y quita la regla que obligaba a que la tarea T008 terminara antes de que empezara la tarea T009.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: #2 Duration = 45: '45 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET Simulation_period = 13896`
- `SET A001.tasks.T010.Duration = 45`
- `DELETE A001.Team members`
- `APPEND A001.tasks.T007.Order_Before = "T012"`
- `REMOVE_ITEM A001.tasks.T008.Order_Before = "T009"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET Simulation_period = 13896`
- `SET A001.tasks.T010.Duration = 0.75`
- `DELETE A001.Team members`
- `APPEND A001.tasks.T012.Order_Before = "T007"`
- `REMOVE_ITEM A001.tasks.T008.Order_Before = "T009"`

**Edits that differ from the GT in C**

- `A001.tasks.T007.Order_Before`: GT ["T008", "T012"] / prediction ["T008"]
- `A001.tasks.T010.Duration`: GT 45 / prediction 0.75
- `A001.tasks.T012.Order_Before`: GT ["T013"] / prediction ["T013", "T007"]


## completeness level 5, sample 237 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A001.Start_disp = 54`
2. `SET A001.Shift_duration = 16`
3. `DELETE A001.T_wait`
4. `APPEND A001.tasks.T014.Order_Before = "T003"`
5. `REMOVE_ITEM A001.tasks.T003.Order_Before = "T005"`

**Original request (B)**: Cambia el desplazamiento inicial de la actividad 1 a 54 y ajusta la duración del turno a 16; elimina la regla de tiempo de espera que tenía la actividad 1; añade a la tarea 14 la regla de que debe terminar antes de que empiece la tarea 3; y quita la regla que obligaba a que la tarea 3 terminara antes de la tarea 5.

**New request (C)**: Mira, necesito que ajustes el desplazamiento inicial de la actividad A-001 a 54 minutos y también la duración del turno a 16 horas, además borra el tiempo de espera de esa misma actividad. Ahora, añade una regla para que la tarea T014 termine antes de empezar la tarea T003, pero quita la regla que obligaba a que la tarea T003 terminara antes de empezar la tarea T005.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: #1 Start_disp = 54: '54 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET A001.Start_disp = 54`
- `SET A001.Shift_duration = 16`
- `DELETE A001.T_wait`
- `APPEND A001.tasks.T014.Order_Before = "T003"`
- `REMOVE_ITEM A001.tasks.T003.Order_Before = "T005"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A001.Start_disp = 0.9`
- `SET A001.Shift_duration = 16`
- `DELETE A001.T_wait`
- `APPEND A001.tasks.T014.Order_Before = "T003"`
- `REMOVE_ITEM A001.tasks.T003.Order_Before = "T005"`

**Edits that differ from the GT in C**

- `A001.Start_disp`: GT 54 / prediction 0.9


## completeness level 5, sample 243 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Teams = 3`
2. `DELETE A009.tasks.T001.Order_Enforced`
3. `SET A014.Start_disp = 43`
4. `APPEND A002.Activity_Order_Before = "A008"`
5. `REMOVE_ITEM A007.Activity_Order_Before = "A008"`

**Original request (B)**: Cambia el número de equipos totales a 3, elimina la regla que forzaba el orden de la tarea 1 de la actividad 9, pon el desplazamiento inicial de la actividad 14 a 43, añade que la actividad 2 debe terminar antes de que empiece la actividad 8 y quita la dependencia de que la actividad 7 termine antes de la actividad 8.

**New request (C)**: Mira, necesito que actualices el número de equipos disponibles en fábrica a 3, borra la obligatoriedad de secuencia estricta para la tarea T001 de la actividad A009, ajusta el retraso del primer inicio para la actividad A014 a 43 minutos, haz que ahora también dependa de A008 para que A002 termine antes de empezar y quita la regla que obligaba a que A007 terminara antes de comenzar A008.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: #3 Start_disp = 43: '43 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 3`
- `DELETE A009.tasks.T001.Order_Enforced`
- `SET A014.Start_disp = 43`
- `APPEND A002.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A007.Activity_Order_Before = "A008"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET Teams = 3`
- `DELETE A009.tasks.T001.Order_Enforced`
- `SET A014.Start_disp = 0.7166666667`
- `APPEND A002.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A008.Activity_Order_Before = "A007"`

**Edits that differ from the GT in C**

- `A007.Activity_Order_Before`: GT [] / prediction ["A008"]
- `A014.Start_disp`: GT 43 / prediction 0.7166666667


## completeness level 5, sample 248 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A013.T_period`
2. `DELETE A014.tasks.T001.Order_Before`
3. `DELETE A015.Team`
4. `APPEND A009.Activity_Order_Before = "A014"`
5. `REMOVE_ITEM A015.Activity_Order_Before = "A016"`

**Original request (B)**: Elimina el período de mantenimiento de la actividad 13, borra la regla de precedencia de la tarea 1 en la actividad 14, quita el equipo asignado a la actividad 15, añade a la actividad 9 la regla que la hace terminar antes de comenzar la actividad 14 y elimina la dependencia que hacía que la actividad 15 terminara antes de la actividad 16.

**New request (C)**: Borra el periodo entre intervenciones de la actividad A013 y también quita la dependencia que obligaba a terminar la tarea 1 antes de empezar cualquier otra cosa en la actividad A014, además de eliminar el equipo asignado a la actividad A015. Ahora, asegúrate de que la actividad 9 debe terminar antes de que empiece la actividad 14 y quita la regla que obligaba a que la actividad 15 terminara antes de empezar la actividad 16.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A013.T_period`
- `DELETE A014.tasks.T001.Order_Before`
- `DELETE A015.Team`
- `APPEND A009.Activity_Order_Before = "A014"`
- `REMOVE_ITEM A015.Activity_Order_Before = "A016"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A013.T_wait`
- `DELETE A014.tasks.T001.Order_Before`
- `DELETE A015.Team`
- `APPEND A009.Activity_Order_Before = "A014"`
- `REMOVE_ITEM A015.Activity_Order_Before = "A016"`

**Edits that differ from the GT in C**

- `A013.T_period`: not in the GT (prediction 2988)
- `A013.T_wait`: missing from the prediction (GT 30)


## completeness level 10, sample 450 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A003.T_period = 372`
2. `DELETE A004.Activity_Order_Enforced`
3. `SET Simulation_period = 6235`
4. `SET Teams = 5`
5. `SET A004.tasks.T002.Order_Enforced = true`
6. `APPEND A001.tasks.T004.Order_Before = "T001"`
7. `REMOVE_ITEM A002.tasks.T002.Order_Before = "T004"`
8. `APPEND A001.Activity_Order_Before = "A003"`
9. `REMOVE_ITEM A004.tasks.T002.Order_Before = "T003"`
10. `APPEND A001.tasks.T001.Order_Before = "T004"`

**Original request (B)**: Primero, cambia la frecuencia de mantenimiento de la actividad 3 a 372 y el horizonte de simulación a 6235, mientras reduces los equipos totales a 5; luego, borra la obligatoriedad de la secuencia de la actividad 4 y activa la obligatoriedad de secuencia en la tarea 2 de esa misma actividad. Además, añade que el paso 4 de la actividad 1 termine antes de que empiece el paso 1 y que el paso 1 de la actividad 1 termine antes de que empiece el paso 4, y que la actividad 1 termine antes de que empiece la actividad 3. Por último, quita las dependencias que hacían que el paso 2 de la actividad 2 terminara antes del paso 4 y que el paso 2 de la actividad 4 terminara antes del paso 3.

**New request (C)**: Mira, necesito que cambies el periodo entre intervenciones de la actividad 3 a 372 horas y también quites la obligatoriedad de la ruta para la actividad 4. Además, ajusta el horizonte de simulación a 6235 unidades de tiempo y reduce el número de equipos totales en fábrica a solo 5. Ahora, activa la secuencia estricta para la tarea 2 dentro de la actividad 4. Luego, añade que la tarea 4 de la actividad 1 debe terminar antes de que empiece la tarea 1 y haz lo mismo con las tareas 1 y 4 pero en sentido inverso. Por último, quita la regla que obligaba a que la tarea 2 de la actividad 2 terminara antes de empezar la tarea 4 y también elimina la dependencia similar entre la tarea 2 y la tarea 3 dentro de la actividad 4. Y no olvides que ahora la actividad 1 debe iniciar después de que termine la actividad 3.

**Fidelity of the new request**: ok; direction warnings: #8 A001.Activity_Order_Before = A003 (activity 1 before activity 3), text reads 'activity 1 ... despues ... activity 3': "no olvides que ahora la actividad 1 debe iniciar despues de que termine la actividad 3" | #10 A001.tasks.T001.Order_Before = T004 (task 1 before task 4), text reads 'task 4 ... antes ... task 1': "anade que la tarea 4 de la actividad 1 debe terminar antes de que empiece la tarea 1"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Simulation_period = 6235`
- `SET Teams = 5`
- `SET A003.T_period = 372`
- `DELETE A004.Activity_Order_Enforced`
- `SET A004.tasks.T002.Order_Enforced = true`
- `APPEND A001.tasks.T004.Order_Before = "T001"`
- `APPEND A001.tasks.T001.Order_Before = "T004"`
- `APPEND A001.Activity_Order_Before = "A003"`
- `REMOVE_ITEM A002.tasks.T002.Order_Before = "T004"`
- `REMOVE_ITEM A004.tasks.T002.Order_Before = "T003"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A003.T_period = 372`
- `SET A004.Activity_Order_Enforced = false`
- `SET Simulation_period = 6235`
- `SET Teams = 5`
- `SET A004.tasks.T002.Order_Enforced = true`
- `APPEND A001.tasks.T004.Order_Before = "T001"`
- `APPEND A001.tasks.T001.Order_Before = "T004"`
- `REMOVE_ITEM A002.tasks.T002.Order_Before = "T004"`
- `REMOVE_ITEM A004.tasks.T002.Order_Before = "T003"`
- `APPEND A003.Activity_Order_Before = "A001"`

**Edits that differ from the GT in C**

- `A001.Activity_Order_Before`: GT ["A002", "A003"] / prediction ["A002"]
- `A003.Activity_Order_Before`: GT ["A004"] / prediction ["A004", "A001"]
- `A004.Activity_Order_Enforced`: not in the GT (prediction false)


## completeness level 10, sample 459 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Teams = 25`
2. `DELETE A004.tasks.T002.Order_Before`
3. `SET A001.tasks.T002.Order_Enforced = false`
4. `DELETE A002.tasks.T004.Duration`
5. `SET Simulation_period = 8621`
6. `APPEND A004.Activity_Order_Before = "A002"`
7. `REMOVE_ITEM A004.tasks.T002.Order_Before = "T003"`
8. `APPEND A002.Activity_Order_Before = "A004"`
9. `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
10. `APPEND A001.Activity_Order_Before = "A003"`

**Original request (B)**: El equipo debe cambiar los equipos totales a 25 y ajustar el horizonte de simulación a 8621, mientras desactiva la obligación de forzar orden de la tarea 2 de la actividad 1, borra la duración de la tarea 4 de la actividad 2 y elimina la restricción que la tarea 2 de la actividad 4 tenía de terminar antes de otra tarea; además quita la regla que obligaba a que la tarea 2 de la actividad 4 terminara antes de la tarea 3, añade a la actividad 4 la regla de que debe terminar antes de que empiece la actividad 2, añade a la actividad 2 la regla de que debe terminar antes de que empiece la actividad 4, quita la regla que obligaba a que la tarea 2 de la actividad 2 terminara antes de la tarea 3 y añade a la actividad 1 la regla de que debe terminar antes de que empiece la actividad 3.

**New request (C)**: Mira, necesito que cambies el número de equipos disponibles en fábrica a 25 y borres la restricción que obligaba a que la tarea T002 de la actividad A004 terminara antes de empezar otra cosa. Además, desactiva la obligatoriedad de la ruta para la tarea T002 de la actividad A001 y quita el dato de duración de la tarea T004 en la actividad A002. También ajusta el horizonte de simulación a 8621, añade que ahora la actividad A004 también dependa de que la actividad A002 termine primero, y quita la regla que obligaba a que T002 de A004 terminara antes de empezar T003. Haz lo mismo para la tarea T002 en la actividad A002 pero cambiando la dependencia para que ahora también dependa de A004, y finalmente añade que la tarea A001 ahora también precede a la actividad A003.

**Fidelity of the new request**: ok; direction warnings: #6 A004.Activity_Order_Before = A002 (activity 4 before activity 2), text reads 'activity 4 ... depend ... activity 2': "anade que ahora la actividad a004 tambien dependa de que la actividad a002 termine primero" | #8 A002.Activity_Order_Before = A004 (activity 2 before activity 4), text reads 'activity 2 ... depend ... activity 4': "haz lo mismo para la tarea t002 en la actividad a002 pero cambiando la dependencia para que ahora tambien dependa de a004"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 25`
- `SET Simulation_period = 8621`
- `SET A001.tasks.T002.Order_Enforced = false`
- `DELETE A002.tasks.T004.Duration`
- `DELETE A004.tasks.T002.Order_Before`
- `REMOVE_ITEM A004.tasks.T002.Order_Before = "T003"`
- `APPEND A004.Activity_Order_Before = "A002"`
- `APPEND A002.Activity_Order_Before = "A004"`
- `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
- `APPEND A001.Activity_Order_Before = "A003"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- (no instructions)
- error: Planner Error: Empty LLM response

**Edits that differ from the GT in C**

- `A001.Activity_Order_Before`: GT ["A002", "A003"] / prediction ["A002"]
- `A002.Activity_Order_Before`: GT ["A003", "A004"] / prediction ["A003"]
- `A002.tasks.T002.Order_Before`: GT ["T004"] / prediction ["T003", "T004"]
- `A002.tasks.T004.Duration`: not in the GT (prediction 23)
- `A004.Activity_Order_Before`: GT ["A002"] / prediction []
- `A004.tasks.T002.Order_Before`: not in the GT (prediction ["T003", "T004"])
- `Simulation_period`: GT 8621 / prediction 5887
- `Teams`: GT 25 / prediction 16


## completeness level 10, sample 465 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Teams = 4`
2. `DELETE A001.tasks.T008.Requires_Shutdown`
3. `DELETE A001.tasks.T003.Duration`
4. `DELETE A001.tasks.T014.Requires_Shutdown`
5. `DELETE A001.tasks.T005.Order_Before`
6. `APPEND A001.tasks.T014.Order_Before = "T001"`
7. `REMOVE_ITEM A001.tasks.T013.Order_Before = "T015"`
8. `APPEND A001.tasks.T012.Order_Before = "T005"`
9. `REMOVE_ITEM A001.tasks.T011.Order_Before = "T012"`
10. `APPEND A001.tasks.T009.Order_Before = "T005"`

**Original request (B)**: Pon los equipos totales en 4, borra el requisito de parada de la tarea 8 de la actividad 1, borra la duración de la tarea 3 de la actividad 1 y borra el requisito de parada de la tarea 14 de la actividad 1. Además, borra la lista de tareas que deben terminar antes de que empiece la tarea 5, añade que la tarea 14 debe terminar antes de que empiece la tarea 1, quita la regla que obligaba a que la tarea 13 terminara antes de que empiece la tarea 15, añade que la tarea 12 debe terminar antes de que empiece la tarea 5, quita la regla que obligaba a que la tarea 11 terminara antes de que empiece la tarea 12 y añade que la tarea 9 debe terminar antes de que empiece la tarea 5.

**New request (C)**: Necesito que cambies el número de equipos disponibles en fábrica a cuatro y además elimines la necesidad de parada para las tareas T008, T014 y T005 de la actividad A-001. También borra la duración de la tarea T003. Además, quita la regla que obligaba a que la tarea T005 terminara antes de empezar otra y añade una nueva regla para que ahora la tarea T014 termine antes de que empiece la T001. Haz que la tarea T012 también dependa de la T005, pero quita la dependencia que existía entre las tareas T013 y T015. Por último, añade a la lista de precedencias de la tarea T009 que debe terminar antes de que empiece la tarea T005.

**Fidelity of the new request**: #9 REMOVE_ITEM A001.tasks.T011.Order_Before = T012: missing task; direction warnings: #8 A001.tasks.T012.Order_Before = T005 (task 12 before task 5), text reads 'task 12 ... depend ... task 5': "haz que la tarea t012 tambien dependa de la t005"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 4`
- `DELETE A001.tasks.T008.Requires_Shutdown`
- `DELETE A001.tasks.T003.Duration`
- `DELETE A001.tasks.T014.Requires_Shutdown`
- `DELETE A001.tasks.T005.Order_Before`
- `APPEND A001.tasks.T014.Order_Before = "T001"`
- `REMOVE_ITEM A001.tasks.T013.Order_Before = "T015"`
- `APPEND A001.tasks.T012.Order_Before = "T005"`
- `REMOVE_ITEM A001.tasks.T011.Order_Before = "T012"`
- `APPEND A001.tasks.T009.Order_Before = "T005"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET Teams = 4`
- `SET A001.tasks.T008.Requires_Shutdown = false`
- `SET A001.tasks.T014.Requires_Shutdown = false`
- `SET A001.tasks.T005.Requires_Shutdown = false`
- `DELETE A001.tasks.T003.Duration`
- `DELETE A001.tasks.T005.Order_Before`
- `APPEND A001.tasks.T014.Order_Before = "T001"`
- `APPEND A001.tasks.T012.Order_Before = "T005"`
- `REMOVE_ITEM A001.tasks.T013.Order_Before = "T015"`
- `APPEND A001.tasks.T009.Order_Before = "T005"`

**Edits that differ from the GT in C**

- `A001.tasks.T008.Requires_Shutdown`: not in the GT (prediction false)
- `A001.tasks.T011.Order_Before`: GT [] / prediction ["T012"]
- `A001.tasks.T014.Requires_Shutdown`: not in the GT (prediction false)


## completeness level 10, sample 466 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A001.Team`
2. `DELETE A001.tasks.T003.Order_Enforced`
3. `SET A001.tasks.T002.Duration = 50`
4. `DELETE A001.Activity_Order_Enforced`
5. `SET A001.tasks.T005.Cost_per_hour = 618`
6. `APPEND A001.tasks.T015.Order_Before = "T004"`
7. `REMOVE_ITEM A001.tasks.T012.Order_Before = "T013"`
8. `APPEND A001.tasks.T005.Order_Before = "T002"`
9. `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
10. `APPEND A001.tasks.T009.Order_Before = "T006"`

**Original request (B)**: Por favor, quita el equipo asignado de la actividad 1 y borra la obligatoriedad de la ruta de actividades de la misma; elimina la regla de forzar orden de la tarea 3 y la regla que obliga a que la tarea 12 termine antes de la 13; cambia la duración de la tarea 2 a 50 y actualiza el costo por hora de la tarea 5 a 618; además, añade a la tarea 15 que debe terminar antes de que empiece la tarea 4, añade a la tarea 5 que debe terminar antes de que empiece la tarea 2, quita la regla que obliga a que la tarea 4 termine antes de la 5 y añade a la tarea 9 que debe terminar antes de que empiece la tarea 6.

**New request (C)**: Mira, necesito que borres el equipo asignado a la actividad 1 y también elimines la obligatoriedad de la secuencia para las tareas dentro de esa actividad. Ajusta la duración de la tarea 2 a 50 unidades y quita la restricción general sobre la orden de actividades en la actividad 1. Ahora, pon el costo por hora de la tarea 5 a 618. Además, añade que la tarea 15 debe terminar antes de que empiece la tarea 4, y quita la regla que obligaba a que la tarea 12 terminara antes de empezar la tarea 13. Haz que ahora también dependa la tarea 5 de que termine primero la tarea 2, y elimina la dependencia de que la tarea 4 vaya antes que la tarea 5. Finalmente, añade una nueva regla para que la tarea 9 preceda a la tarea 6.

**Fidelity of the new request**: #2 DELETE A001.tasks.T003.Order_Enforced: missing task; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A001.Team`
- `DELETE A001.Activity_Order_Enforced`
- `DELETE A001.tasks.T003.Order_Enforced`
- `REMOVE_ITEM A001.tasks.T012.Order_Before = "T013"`
- `SET A001.tasks.T002.Duration = 50`
- `SET A001.tasks.T005.Cost_per_hour = 618`
- `APPEND A001.tasks.T015.Order_Before = "T004"`
- `APPEND A001.tasks.T005.Order_Before = "T002"`
- `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
- `APPEND A001.tasks.T009.Order_Before = "T006"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- (no instructions)
- error: Planner Error: Empty LLM response

**Edits that differ from the GT in C**

- `A001.Activity_Order_Enforced`: not in the GT (prediction true)
- `A001.Team`: not in the GT (prediction "TeamA")
- `A001.tasks.T002.Duration`: GT 50 / prediction 14
- `A001.tasks.T003.Order_Enforced`: not in the GT (prediction false)
- `A001.tasks.T004.Order_Before`: GT [] / prediction ["T005"]
- `A001.tasks.T005.Cost_per_hour`: GT 618 / prediction 290
- `A001.tasks.T005.Order_Before`: GT ["T006", "T002"] / prediction ["T006"]
- `A001.tasks.T009.Order_Before`: GT ["T010", "T006"] / prediction ["T010"]
- `A001.tasks.T012.Order_Before`: GT [] / prediction ["T013"]
- `A001.tasks.T015.Order_Before`: GT ["T016", "T004"] / prediction ["T016"]


## completeness level 10, sample 467 (EM B 0, EM C 1)

**Technical instruction**

1. `SET Simulation_period = 11907`
2. `DELETE A001.T_wait`
3. `SET A001.Shift_duration = 10`
4. `SET Simulation_period = 719`
5. `DELETE A001.tasks.T010.Requires_Shutdown`
6. `APPEND A001.tasks.T004.Order_Before = "T016"`
7. `REMOVE_ITEM A001.tasks.T011.Order_Before = "T013"`
8. `APPEND A001.tasks.T014.Order_Before = "T012"`
9. `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
10. `APPEND A001.tasks.T004.Order_Before = "T014"`

**Original request (B)**: Primero establezco el horizonte de simulación a 11907 y luego lo ajusto a 719; borro el tiempo de espera de la actividad 1 y asigno la duración del turno a 10 horas; elimino la necesidad de apagar la máquina en la tarea 10 de la actividad 1, añado que la tarea 4 debe terminar antes de la tarea 16, quito la regla que obligaba a que la tarea 11 terminara antes de la tarea 13 y hago que la tarea 14 termine antes de la tarea 12; por último, elimino la regla que hacía que la tarea 4 terminara antes de la tarea 5 y añado la nueva dependencia de que la tarea 4 debe terminar antes de la tarea 14.

**New request (C)**: Necesito que actualices el periodo global de simulación a 719 y borres el tiempo de espera para la actividad A001, además ajusta su duración del turno a 10 horas. También quita la restricción de parada en la tarea T010 de esa misma actividad. En cuanto a las dependencias, añade que ahora la tarea T004 va antes que T016 y que la tarea T014 precede a T012, pero quita la regla que obligaba a que la tarea T011 terminara antes de empezar T013. Finalmente, asegúrate de añadir también que la tarea T004 va antes que T014 y elimina esa dependencia anterior que tenía con la tarea T005.

**Fidelity of the new request**: #1 SET Simulation_period = 11907: missing value; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Simulation_period = 11907`
- `SET Simulation_period = 719`
- `DELETE A001.T_wait`
- `SET A001.Shift_duration = 10`
- `SET A001.tasks.T010.Requires_Shutdown = false`
- `APPEND A001.tasks.T004.Order_Before = "T016"`
- `REMOVE_ITEM A001.tasks.T011.Order_Before = "T013"`
- `APPEND A001.tasks.T014.Order_Before = "T012"`
- `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
- `APPEND A001.tasks.T004.Order_Before = "T014"`

**Edits that differ from the GT in B**

- `A001.tasks.T010.Requires_Shutdown`: not in the GT (prediction false)

**Batch emitted by gpt-oss:20b in C**

- `SET Simulation_period = 719`
- `DELETE A001.T_wait`
- `SET A001.Shift_duration = 10`
- `DELETE A001.tasks.T010.Requires_Shutdown`
- `APPEND A001.tasks.T004.Order_Before = "T016"`
- `APPEND A001.tasks.T014.Order_Before = "T012"`
- `REMOVE_ITEM A001.tasks.T011.Order_Before = "T013"`
- `APPEND A001.tasks.T004.Order_Before = "T014"`
- `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`

**Edits that differ from the GT in C**

- none (exact match)


## completeness level 10, sample 469 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A001.T_wait = 21`
2. `DELETE A001.Activity_Order_Enforced`
3. `DELETE A001.T_period`
4. `SET A001.Activity_Order_Enforced = true`
5. `SET A001.Activity_Order_Enforced = false`
6. `APPEND A001.tasks.T001.Order_Before = "T010"`
7. `REMOVE_ITEM A001.tasks.T006.Order_Before = "T007"`
8. `APPEND A001.tasks.T013.Order_Before = "T012"`
9. `REMOVE_ITEM A001.tasks.T002.Order_Before = "T003"`
10. `APPEND A001.tasks.T012.Order_Before = "T011"`

**Original request (B)**: Modifica el tiempo de espera de la actividad A-001 a 21; borra el periodo entre intervenciones y la regla de forzar orden de actividades, luego activa la secuencia y la desactiva de nuevo; agrega que la tarea 1 debe terminar antes de la tarea 10, que la tarea 13 debe terminar antes de la tarea 12 y que la tarea 12 debe terminar antes de la tarea 11; quita la dependencia de que la tarea 6 vaya antes que la 7, que la tarea 2 vaya antes que la 3.

**New request (C)**: Ajusta el tiempo de espera de la actividad A-001 a 21 minutos y borra las restricciones del orden de actividades y el periodo entre intervenciones, luego desactiva primero y luego vuelve a activar la obligatoriedad de la ruta para asegurar que todo quede claro. Además, añade una regla en la tarea T001 para que termine antes de empezar T010, y quita la dependencia que obligaba a que T006 terminara antes de T007. Haz lo mismo con las tareas T013 y T012, así como T012 y T011, para asegurar la secuencia correcta.

**Fidelity of the new request**: #9 REMOVE_ITEM A001.tasks.T002.Order_Before = T003: missing task, value; direction warnings: none; unit warnings: #1 T_wait = 21: '21 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET A001.T_wait = 21`
- `DELETE A001.T_period`
- `DELETE A001.Activity_Order_Enforced`
- `SET A001.Activity_Order_Enforced = true`
- `SET A001.Activity_Order_Enforced = false`
- `APPEND A001.tasks.T001.Order_Before = "T010"`
- `APPEND A001.tasks.T013.Order_Before = "T012"`
- `APPEND A001.tasks.T012.Order_Before = "T011"`
- `REMOVE_ITEM A001.tasks.T006.Order_Before = "T007"`
- `REMOVE_ITEM A001.tasks.T002.Order_Before = "T003"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A001.T_wait = 0.35`
- `DELETE A001.Activity_Order_Enforced`
- `DELETE A001.T_period`
- `SET A001.Activity_Order_Enforced = false`
- `SET A001.Activity_Order_Enforced = true`
- `APPEND A001.tasks.T001.Order_Before = "T010"`
- `REMOVE_ITEM A001.tasks.T006.Order_Before = "T007"`
- `APPEND A001.tasks.T013.Order_Before = "T012"`
- `APPEND A001.tasks.T012.Order_Before = "T011"`

**Edits that differ from the GT in C**

- `A001.Activity_Order_Enforced`: GT false / prediction true
- `A001.T_wait`: GT 21 / prediction 0.35
- `A001.tasks.T002.Order_Before`: GT [] / prediction ["T003"]


## completeness level 10, sample 474 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A001.tasks.T001.Duration`
2. `SET A001.Team members = 10`
3. `DELETE A008.tasks.T001.Order_Before`
4. `SET A004.tasks.T001.Duration = 50`
5. `SET A005.tasks.T001.Cost_per_hour = 563`
6. `APPEND A003.Activity_Order_Before = "A010"`
7. `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
8. `APPEND A007.Activity_Order_Before = "A010"`
9. `REMOVE_ITEM A008.Activity_Order_Before = "A009"`
10. `APPEND A006.Activity_Order_Before = "A016"`

**Original request (B)**: Necesito que borres el parámetro de duración de la tarea 1 de la actividad 1, cambies la dotación de esa misma actividad a 10 operarios y elimines la regla de precedencia de la tarea 1 de la actividad 8. Además, cambia la duración de la tarea 1 de la actividad 4 a 50 y el costo por hora de la tarea 1 de la actividad 5 a 563. Añade también a las actividades 3 y 7 la regla de que deben terminar antes de la actividad 10, y a la actividad 6 la regla de que debe terminar antes de la actividad 16, mientras quitas la regla que obligaba a que la actividad 13 terminara antes de la actividad 14 y la regla que obligaba a que la actividad 8 terminara antes de la actividad 9.

**New request (C)**: Mira, necesito que borres el tiempo de proceso de la tarea 1 en la actividad A-001, y ajustes la cantidad de operarios a 10 para esa actividad. Además, quita cualquier regla que indicara que la tarea 1 de la actividad A008 debía terminar antes de otra, y ahora pon la duración de la tarea 1 en la actividad A-004 en 50 minutos. Ajusta el costo operativo de la tarea 1 de la actividad A-005 a 563 por hora. Haz que la actividad A-003 también dependa de terminar antes de empezar la actividad A-010, y quita la regla que obligaba a que la actividad A-013 terminara antes de comenzar la actividad A-014. Ahora, asegúrate de añadir una nueva dependencia para que la actividad A-007 también tenga que cumplirse antes de iniciar la A-010 y por último, agrega una regla en A-006 indicando que debe terminar antes de que comience la actividad A-016.

**Fidelity of the new request**: #9 REMOVE_ITEM A008.Activity_Order_Before = A009: missing value; direction warnings: #6 A003.Activity_Order_Before = A010 (activity 3 before activity 10), text reads 'activity 3 ... depend ... activity 10': "haz que la actividad a-003 tambien dependa de terminar antes de empezar la actividad a-010"; unit warnings: #4 Duration = 50: '50 minutos'

**Batch emitted by gpt-oss:20b in B**

- `DELETE A001.tasks.T001.Duration`
- `SET A001.Team members = 10`
- `DELETE A008.tasks.T001.Order_Before`
- `SET A004.tasks.T001.Duration = 50`
- `SET A005.tasks.T001.Cost_per_hour = 563`
- `APPEND A003.Activity_Order_Before = "A010"`
- `APPEND A007.Activity_Order_Before = "A010"`
- `APPEND A006.Activity_Order_Before = "A016"`
- `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
- `REMOVE_ITEM A008.Activity_Order_Before = "A009"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A001.tasks.T001.Duration`
- `SET A001.Team members = 10`
- `DELETE A008.tasks.T001.Order_Before`
- `SET A004.tasks.T001.Duration = 0.8333`
- `SET A005.tasks.T001.Cost_per_hour = 563`
- `APPEND A003.Activity_Order_Before = "A010"`
- `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
- `APPEND A007.Activity_Order_Before = "A010"`
- `APPEND A006.Activity_Order_Before = "A016"`

**Edits that differ from the GT in C**

- `A004.tasks.T001.Duration`: GT 50 / prediction 0.8333
- `A008.Activity_Order_Before`: GT [] / prediction ["A009"]


## completeness level 10, sample 475 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A002.tasks.T001.Order_Before`
2. `DELETE A010.tasks.T001.Order_Enforced`
3. `SET A002.tasks.T001.Order_Enforced = true`
4. `SET A004.tasks.T001.Cost_per_hour = 511`
5. `DELETE A010.T_wait`
6. `APPEND A001.Activity_Order_Before = "A016"`
7. `REMOVE_ITEM A010.Activity_Order_Before = "A011"`
8. `APPEND A005.Activity_Order_Before = "A015"`
9. `REMOVE_ITEM A011.Activity_Order_Before = "A012"`
10. `APPEND A003.Activity_Order_Before = "A007"`

**Original request (B)**: Borra la regla que obligaba a la tarea 1 de la actividad 2 a terminar antes de otra actividad y elimina la obligatoriedad de que la tarea 1 de la actividad 10 siga la secuencia estricta. Activa la obligatoriedad de que la tarea 1 de la actividad 2 siga la secuencia estricta, cambia el costo por hora de la tarea 1 de la actividad 4 a 511 y borra el tiempo de espera de la actividad 10. Añade que la actividad 1 deba terminar antes de la actividad 16, quita la regla que obligaba a que la actividad 10 terminara antes de la actividad 11, añade que la actividad 5 deba terminar antes de la actividad 15, quita la regla que obligaba a que la actividad 11 terminara antes de la actividad 12 y añade que la actividad 3 deba terminar antes de la actividad 7.

**New request (C)**: Mira, necesito que borres la regla que obligaba a que la tarea 1 de la actividad 2 terminara antes de empezar cualquier otra cosa y también quites la restricción de secuencia estricta para la tarea 1 de la actividad 10. Además, pon la opción de forzar orden de tareas en verdadero para la tarea 1 de la actividad 2 y ajusta el costo por hora de la tarea 1 de la actividad 4 a 511. También quita el margen de espera de la actividad 10 y añade que ahora también depende de la actividad 16, quita la regla que obligaba a que la actividad 10 fuera antes que la 11, haz que la actividad 5 ahora también vaya antes que la 15 y finalmente añade que la actividad 3 debe terminar antes de que empiece la actividad 7.

**Fidelity of the new request**: #9 REMOVE_ITEM A011.Activity_Order_Before = A012: missing value; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A002.tasks.T001.Order_Before`
- `DELETE A010.tasks.T001.Order_Enforced`
- `SET A002.tasks.T001.Order_Enforced = true`
- `SET A004.tasks.T001.Cost_per_hour = 511`
- `DELETE A010.T_wait`
- `APPEND A001.Activity_Order_Before = "A016"`
- `REMOVE_ITEM A010.Activity_Order_Before = "A011"`
- `APPEND A005.Activity_Order_Before = "A015"`
- `REMOVE_ITEM A011.Activity_Order_Before = "A012"`
- `APPEND A003.Activity_Order_Before = "A007"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A002.tasks.T001.Order_Before`
- `DELETE A010.tasks.T001.Order_Enforced`
- `SET A002.tasks.T001.Order_Enforced = true`
- `SET A004.tasks.T001.Cost_per_hour = 511`
- `DELETE A010.T_wait`
- `APPEND A010.Activity_Order_Before = "A016"`
- `REMOVE_ITEM A010.Activity_Order_Before = "A011"`
- `APPEND A005.Activity_Order_Before = "A015"`
- `APPEND A003.Activity_Order_Before = "A007"`

**Edits that differ from the GT in C**

- `A001.Activity_Order_Before`: GT ["A002", "A016"] / prediction ["A002"]
- `A010.Activity_Order_Before`: GT [] / prediction ["A016"]
- `A011.Activity_Order_Before`: GT [] / prediction ["A012"]


## completeness level 10, sample 478 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A007.tasks.T001.Cost_per_hour = 313`
2. `DELETE A002.T_wait`
3. `DELETE A010.tasks.T001.Cost_per_hour`
4. `DELETE A007.tasks.T001.Cost_per_hour`
5. `DELETE A004.tasks.T001.Requires_Shutdown`
6. `APPEND A006.Activity_Order_Before = "A002"`
7. `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
8. `APPEND A002.Activity_Order_Before = "A004"`
9. `REMOVE_ITEM A012.Activity_Order_Before = "A013"`
10. `APPEND A002.Activity_Order_Before = "A001"`

**Original request (B)**: Pon el costo por hora de la tarea 1 de la actividad 7 a 313 y después elimina ese dato, borra el costo por hora de la tarea 1 de la actividad 10, borra que la tarea 1 de la actividad 4 requiera parada, elimina el tiempo de espera de la actividad 2, quita la regla que obligaba a que la actividad 3 terminara antes de empezar la actividad 4, quita la regla que obligaba a que la actividad 12 terminara antes de empezar la actividad 13, añade que la actividad 6 debe terminar antes de que empiece la actividad 2, y añade que la actividad 2 debe terminar antes de que empiece la actividad 4 y antes de que empiece la actividad 1.

**New request (C)**: Cambia el costo por hora de la tarea 1 de la actividad A-007 a 313 euros y borra la demora antes de repetir de la actividad 2, además quita el dato del costo horario de la primera tarea de la actividad A-010 y también elimina la restricción de requerir parada para la primera tarea de la actividad A-004. Haz que ahora la actividad 6 dependa antes de comenzar la actividad 2, elimina la regla que obligaba a que la actividad 3 terminara antes de empezar la actividad 4, y añade la regla que hace que la actividad 2 no pueda iniciar hasta que termine la actividad 4. Finalmente, quita también el vínculo que decía que la actividad A-012 va antes que A-013 y añade a la lista de dependencias de la actividad 2 para que inicie después de terminar la actividad 1.

**Fidelity of the new request**: ok; direction warnings: #6 A006.Activity_Order_Before = A002 (activity 6 before activity 2), text reads 'activity 6 ... depend ... activity 2': "haz que ahora la actividad 6 dependa antes de comenzar la actividad 2" | #8 A002.Activity_Order_Before = A004 (activity 2 before activity 4), text reads 'activity 2 ... hasta que ... activity 4': "anade la regla que hace que la actividad 2 no pueda iniciar hasta que termine la actividad 4" | #10 A002.Activity_Order_Before = A001 (activity 2 before activity 1), text reads 'activity 2 ... despues ... activity 1': "anade a la lista de dependencias de la actividad 2 para que inicie despues de terminar la actividad 1"; unit warnings: #1 Cost_per_hour = 313: '313 euros'

**Batch emitted by gpt-oss:20b in B**

- `SET A007.tasks.T001.Cost_per_hour = 313`
- `DELETE A007.tasks.T001.Cost_per_hour`
- `DELETE A010.tasks.T001.Cost_per_hour`
- `DELETE A004.tasks.T001.Requires_Shutdown`
- `DELETE A002.T_wait`
- `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
- `REMOVE_ITEM A012.Activity_Order_Before = "A013"`
- `APPEND A006.Activity_Order_Before = "A002"`
- `APPEND A002.Activity_Order_Before = "A004"`
- `APPEND A002.Activity_Order_Before = "A001"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A007.tasks.T001.Cost_per_hour = 313`
- `DELETE A002.T_wait`
- `DELETE A010.tasks.T001.Cost_per_hour`
- `DELETE A004.tasks.T001.Requires_Shutdown`
- `APPEND A006.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
- `APPEND A002.Activity_Order_Before = "A004"`
- `REMOVE_ITEM A012.Activity_Order_Before = "A013"`
- `APPEND A002.Activity_Order_Before = "A001"`

**Edits that differ from the GT in C**

- `A007.tasks.T001.Cost_per_hour`: not in the GT (prediction 313)


## completeness level 10, sample 479 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A008.T_wait`
2. `DELETE A004.Activity_Order_Before`
3. `DELETE A003.T_wait`
4. `SET A006.Shift_duration = 9`
5. `SET A013.T_wait = 67`
6. `APPEND A003.Activity_Order_Before = "A015"`
7. `REMOVE_ITEM A001.Activity_Order_Before = "A002"`
8. `APPEND A007.Activity_Order_Before = "A015"`
9. `REMOVE_ITEM A008.Activity_Order_Before = "A009"`
10. `APPEND A010.Activity_Order_Before = "A009"`

**Original request (B)**: Elimina el tiempo de espera de la actividad 8 y de la actividad 3, y quita la restricción de que la actividad 4 dependa de otra; cambia la duración del turno de la actividad 6 a 9 horas y actualiza el tiempo de espera de la actividad 13 a 67; añade que la actividad 3 debe terminar antes de que empiece la actividad 15, que la actividad 7 también debe terminar antes de la actividad 15 y que la actividad 10 debe terminar antes de la actividad 9; además quita la dependencia que obligaba a que la actividad 1 terminara antes de que empiece la actividad 2 y elimina la regla que obligaba a que la actividad 8 terminara antes de la actividad 9.

**New request (C)**: Mira, necesito que borres el tiempo de espera para la actividad 8 y también elimines la restricción de orden de actividades para la actividad 4. Además, quita el margen de espera para la actividad 3, ajusta la duración del turno de la actividad 6 a 9 horas y configura un tiempo de espera de 67 minutos para la actividad 13. Ahora también, añade que la actividad 3 debe terminar antes de empezar la actividad 15 y haz lo mismo con la actividad 7. Por otro lado, quita la regla que obligaba a que la actividad 1 terminara antes de empezar la actividad 2, y finalmente agrega que la actividad 10 va ahora después de la actividad 9.

**Fidelity of the new request**: ok; direction warnings: #10 A010.Activity_Order_Before = A009 (activity 10 before activity 9), text reads 'activity 10 ... despues ... activity 9': "finalmente agrega que la actividad 10 va ahora despues de la actividad 9"; unit warnings: #5 T_wait = 67: '67 minutos'

**Batch emitted by gpt-oss:20b in B**

- `DELETE A003.T_wait`
- `DELETE A008.T_wait`
- `DELETE A004.Activity_Order_Before`
- `SET A006.Shift_duration = 9`
- `SET A013.T_wait = 67`
- `APPEND A003.Activity_Order_Before = "A015"`
- `APPEND A007.Activity_Order_Before = "A015"`
- `APPEND A010.Activity_Order_Before = "A009"`
- `REMOVE_ITEM A001.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A008.Activity_Order_Before = "A009"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- (no instructions)
- error: Planner Error: plan inválido (faltan instrucciones).

**Edits that differ from the GT in C**

- `A001.Activity_Order_Before`: GT [] / prediction ["A002"]
- `A003.Activity_Order_Before`: GT ["A015"] / prediction []
- `A003.T_wait`: not in the GT (prediction 1)
- `A004.Activity_Order_Before`: not in the GT (prediction [])
- `A006.Shift_duration`: GT 9 / prediction 8
- `A007.Activity_Order_Before`: GT ["A008", "A015"] / prediction ["A008"]
- `A008.Activity_Order_Before`: GT [] / prediction ["A009"]
- `A008.T_wait`: not in the GT (prediction 13)
- `A010.Activity_Order_Before`: GT ["A009"] / prediction []
- `A013.T_wait`: GT 67 / prediction 29


## completeness level 10, sample 480 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A001.tasks.T001.Order_Enforced`
2. `SET Teams = 16`
3. `DELETE A003.Team members`
4. `DELETE A001.tasks.T002.Duration`
5. `DELETE A005.Team`
6. `APPEND A004.Activity_Order_Before = "A008"`
7. `REMOVE_ITEM A007.tasks.T001.Order_Before = "T002"`
8. `APPEND A008.Activity_Order_Before = "A003"`
9. `REMOVE_ITEM A004.tasks.T001.Order_Before = "T002"`
10. `APPEND A008.Activity_Order_Before = "A002"`

**Original request (B)**: Pon el número de equipos a 16 y elimina la obligatoriedad de la tarea 1 de la actividad 1, borra la duración de la tarea 2 de la actividad 1, quita la dotación de la actividad 3 y el equipo asignado a la actividad 5. Quita la dependencia que hacía que la tarea 1 de la actividad 7 terminara antes de la tarea 2 y la que hacía que la tarea 1 de la actividad 4 terminara antes de la tarea 2. Añade a la actividad 4 que debe terminar antes de la actividad 8, y haz que la actividad 8 termine antes de la actividad 3 y de la actividad 2.

**New request (C)**: Mira, necesito que borres la obligatoriedad de orden de tareas para la tarea 1 en la actividad 1 y ajustes el número de equipos totales a 16. Además, quita la dotación del equipo asignado en la actividad 3 y elimina la duración de la tarea 2 en la actividad 1, también borra el equipo asignado en la actividad 5. Ahora, haz que la actividad 4 preceda a la actividad 8, y quita la regla que obligaba a que la tarea 1 de la actividad 7 termine antes de empezar T002. Finalmente, añade que ahora también depende la actividad 8 de las actividades 3 y 2.

**Fidelity of the new request**: ok; direction warnings: none; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 16`
- `DELETE A001.tasks.T001.Order_Enforced`
- `DELETE A001.tasks.T002.Duration`
- `DELETE A003.Team members`
- `DELETE A005.Team`
- `REMOVE_ITEM A007.tasks.T001.Order_Before = "T002"`
- `REMOVE_ITEM A004.tasks.T001.Order_Before = "T002"`
- `APPEND A004.Activity_Order_Before = "A008"`
- `APPEND A008.Activity_Order_Before = "A003"`
- `APPEND A008.Activity_Order_Before = "A002"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A001.tasks.T001.Order_Enforced`
- `SET Teams = 16`
- `DELETE A003.Team members`
- `DELETE A001.tasks.T002.Duration`
- `DELETE A005.Team`
- `APPEND A004.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A007.tasks.T001.Order_Before = "T002"`
- `APPEND A008.Activity_Order_Before = "A003"`
- `APPEND A008.Activity_Order_Before = "A002"`

**Edits that differ from the GT in C**

- `A004.tasks.T001.Order_Before`: GT [] / prediction ["T002"]


## completeness level 10, sample 482 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A002.Activity_Order_Enforced`
2. `DELETE A001.tasks.T001.Order_Enforced`
3. `SET A007.Start_disp = 37`
4. `DELETE A004.tasks.T002.Cost_per_hour`
5. `SET A002.tasks.T002.Duration = 5`
6. `APPEND A006.Activity_Order_Before = "A008"`
7. `REMOVE_ITEM A007.tasks.T001.Order_Before = "T002"`
8. `APPEND A003.Activity_Order_Before = "A004"`
9. `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
10. `APPEND A005.Activity_Order_Before = "A008"`

**Original request (B)**: Elimina la obligatoriedad de la secuencia de actividades de la actividad 2 y también quita la regla que obliga al paso 1 de la actividad 1 a seguir un orden. Pon el retraso del primer inicio de la actividad 7 a 37, elimina la tarifa horaria del paso 2 de la actividad 4 y fija la duración del paso 2 de la actividad 2 a 5 horas. Añade que la actividad 6 termine antes de la actividad 8, quita la regla que obligaba al paso 1 de la actividad 7 a terminar antes del paso 2 y quita la regla que obligaba al paso 1 de la actividad 8 a terminar antes del paso 2. Añade que la actividad 3 termine antes de la actividad 4 y que la actividad 5 termine antes de la actividad 8.

**New request (C)**: Mira, necesito que quites la obligatoriedad de la secuencia para la actividad 2 y también elimines el requisito de orden estricto para la tarea 1 en la actividad 1. Además, ajusta el retraso del primer inicio de la actividad 7 a 37 minutos y borra el dato del costo horario para la tarea 2 dentro de la actividad 4. Ahora, pon que la duración de la tarea 2 en la actividad 2 sea de 5 horas. Haz que ahora también dependa la actividad 8 antes de empezar la actividad 6, quita la regla que obligaba a que T001 de la actividad 7 terminara antes de comenzar T002, y asegúrate de que A004 preceda a A003. Finalmente, elimina también la dependencia de que el paso 1 en la tarea del activity 8 termine antes de empezar T002 y añade una nueva regla para que A005 tenga como requisito previo terminar A008.

**Fidelity of the new request**: ok; direction warnings: #6 A006.Activity_Order_Before = A008 (activity 6 before activity 8), text reads 'activity 8 ... antes ... activity 6': "haz que ahora tambien dependa la actividad 8 antes de empezar la actividad 6" | #8 A003.Activity_Order_Before = A004 (activity 3 before activity 4), text reads 'activity 4 ... preced ... activity 3': "asegurate de que a004 preceda a a003"; unit warnings: #3 Start_disp = 37: '37 minutos'

**Batch emitted by gpt-oss:20b in B**

- `DELETE A002.Activity_Order_Enforced`
- `DELETE A001.tasks.T001.Order_Enforced`
- `SET A007.Start_disp = 37`
- `DELETE A004.tasks.T002.Cost_per_hour`
- `SET A002.tasks.T002.Duration = 5`
- `APPEND A006.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A007.tasks.T001.Order_Before = "T002"`
- `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
- `APPEND A003.Activity_Order_Before = "A004"`
- `APPEND A005.Activity_Order_Before = "A008"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A002.Activity_Order_Enforced`
- `DELETE A001.tasks.T001.Order_Enforced`
- `SET A007.Start_disp = 0.6166667`
- `DELETE A004.tasks.T002.Cost_per_hour`
- `SET A002.tasks.T002.Duration = 5`
- `APPEND A008.Activity_Order_Before = "A006"`
- `REMOVE_ITEM A007.tasks.T001.Order_Before = "T002"`
- `APPEND A004.Activity_Order_Before = "A003"`
- `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
- `APPEND A005.Activity_Order_Before = "A008"`

**Edits that differ from the GT in C**

- `A003.Activity_Order_Before`: GT ["A004"] / prediction []
- `A004.Activity_Order_Before`: GT ["A005"] / prediction ["A005", "A003"]
- `A006.Activity_Order_Before`: GT ["A007", "A008"] / prediction ["A007"]
- `A007.Start_disp`: GT 37 / prediction 0.6166667
- `A008.Activity_Order_Before`: GT [] / prediction ["A006"]


## completeness level 10, sample 486 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A004.tasks.T001.Requires_Shutdown`
2. `SET A008.tasks.T001.Cost_per_hour = 694`
3. `SET A002.Activity_Order_Enforced = false`
4. `SET Teams = 13`
5. `SET runId = 2528`
6. `APPEND A003.Activity_Order_Before = "A006"`
7. `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
8. `APPEND A003.tasks.T002.Order_Before = "T001"`
9. `REMOVE_ITEM A007.Activity_Order_Before = "A008"`
10. `APPEND A007.Activity_Order_Before = "A002"`

**Original request (B)**: Cambia el número de equipos totales a 13, actualiza el identificador de ejecución a 2528 y desactiva la obligatoriedad de secuencia para la actividad 2. Borra la restricción de que la tarea 1 de la actividad 4 requiera parada y cambia el costo por hora de la tarea 1 de la actividad 8 a 694. Añade que la actividad 3 debe terminar antes de que empiece la actividad 6, que la tarea 2 de la actividad 3 debe terminar antes de que empiece la tarea 1 y que la actividad 7 debe terminar antes de que empiece la actividad 2. Quita la regla que obligaba a que la tarea 1 de la actividad 8 terminara antes de empezar la tarea 2 y la regla que obligaba a que la actividad 7 terminara antes de que empiece la actividad 8.

**New request (C)**: Mira, necesito que quites el requisito de parada para la tarea 1 de la actividad A-004, ajusta el costo por hora de la tarea 1 de la actividad A-008 a 694, y desactivas la obligatoriedad de la ruta en la actividad 2. Además, aumenta el número de cuadrillas disponibles en fábrica a 13 y actualiza el ID de ejecución a 2528. Ahora, haz que la actividad 3 dependa también de la actividad 6 y quita la regla de que la tarea 1 de la actividad A-008 vaya antes que la tarea 2. También, añade que la tarea 2 de la actividad 3 depende ahora de la tarea 1, quita la regla que obligaba a que la actividad 7 termine antes de empezar la actividad 8 y finalmente, haz que la actividad 7 preceda a la actividad 2.

**Fidelity of the new request**: ok; direction warnings: #6 A003.Activity_Order_Before = A006 (activity 3 before activity 6), text reads 'activity 3 ... depend ... activity 6': "haz que la actividad 3 dependa tambien de la actividad 6" | #8 A003.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 2 ... depend ... task 1': "anade que la tarea 2 de la actividad 3 depende ahora de la tarea 1"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET runId = 2528`
- `SET Teams = 13`
- `SET A002.Activity_Order_Enforced = false`
- `DELETE A004.tasks.T001.Requires_Shutdown`
- `SET A008.tasks.T001.Cost_per_hour = 694`
- `APPEND A003.Activity_Order_Before = "A006"`
- `APPEND A003.tasks.T002.Order_Before = "T001"`
- `APPEND A007.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
- `REMOVE_ITEM A007.Activity_Order_Before = "A008"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A004.tasks.T001.Requires_Shutdown`
- `SET A008.tasks.T001.Cost_per_hour = 694`
- `DELETE A002.Activity_Order_Enforced`
- `SET Teams = 13`
- `SET runId = 2528`
- `APPEND A003.Activity_Order_Before = "A006"`
- `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
- `APPEND A003.tasks.T002.Order_Before = "T001"`
- `REMOVE_ITEM A007.Activity_Order_Before = "A008"`
- `APPEND A007.Activity_Order_Before = "A002"`

**Edits that differ from the GT in C**

- `A002.Activity_Order_Enforced`: missing from the prediction (GT false)


## completeness level 10, sample 488 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A001.Team members`
2. `DELETE A008.T_wait`
3. `SET Teams = 5`
4. `DELETE A004.tasks.T002.Cost_per_hour`
5. `SET runId = 9177`
6. `APPEND A002.Activity_Order_Before = "A004"`
7. `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
8. `APPEND A007.Activity_Order_Before = "A006"`
9. `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
10. `APPEND A002.Activity_Order_Before = "A005"`

**Original request (B)**: Borra la dotación de la actividad 1, quita el tiempo de espera de la actividad 8 y cambia el número de equipos totales a cinco, además de eliminar el costo por hora de la tarea 2 de la actividad 4 y poner el runId a 9177. Haz que la actividad 2 termine antes de que empiece la actividad 4 y la actividad 5, y que la actividad 7 termine antes de la actividad 6. Quita la regla que obligaba a que la tarea 1 de la actividad 1 terminara antes de la tarea 2, y elimina la dependencia de que la actividad 3 viera antes que la actividad 4.

**New request (C)**: Mira, necesito que borres el dato del personal asignado a la actividad A-001 y también elimines la demora antes de repetir en la actividad 8. Además, ajusta el número de equipos totales a 5 y quita el costo horario de la tarea T002 en la actividad 4. También debes cambiar el ID del runId a 9177. Ahora, haz que la segunda actividad ahora también dependa de la cuarta, y además elimina la regla que obligaba a la tarea T001 terminar antes de empezar T002 en la primera actividad. Luego, añade que la séptima actividad va antes que la sexta y finalmente, agrega que la segunda actividad precede a la quinta.

**Fidelity of the new request**: #9 REMOVE_ITEM A003.Activity_Order_Before = A004: missing activity; direction warnings: #6 A002.Activity_Order_Before = A004 (activity 2 before activity 4), text reads 'activity 2 ... depend ... activity 4': "haz que la segunda actividad ahora tambien dependa de la cuarta"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A001.Team members`
- `DELETE A008.T_wait`
- `SET Teams = 5`
- `DELETE A004.tasks.T002.Cost_per_hour`
- `SET runId = 9177`
- `APPEND A002.Activity_Order_Before = "A004"`
- `APPEND A002.Activity_Order_Before = "A005"`
- `APPEND A007.Activity_Order_Before = "A006"`
- `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
- `REMOVE_ITEM A003.Activity_Order_Before = "A004"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A001.Team members`
- `DELETE A008.T_wait`
- `SET Teams = 5`
- `DELETE A004.tasks.T002.Cost_per_hour`
- `SET runId = 9177`
- `APPEND A002.Activity_Order_Before = "A004"`
- `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
- `APPEND A007.Activity_Order_Before = "A006"`
- `APPEND A002.Activity_Order_Before = "A005"`

**Edits that differ from the GT in C**

- `A003.Activity_Order_Before`: GT [] / prediction ["A004"]


## completeness level 10, sample 491 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A001.Shift_duration`
2. `DELETE A001.Activity_Order_Before`
3. `SET Teams = 3`
4. `SET A002.T_period = 862`
5. `DELETE A002.tasks.T005.Duration`
6. `APPEND A002.tasks.T007.Order_Before = "T003"`
7. `REMOVE_ITEM A001.tasks.T003.Order_Before = "T004"`
8. `APPEND A001.tasks.T003.Order_Before = "T002"`
9. `REMOVE_ITEM A002.tasks.T003.Order_Before = "T004"`
10. `APPEND A002.tasks.T003.Order_Before = "T006"`

**Original request (B)**: Quiero que borres la duración del turno y cualquier orden previa que tenga la actividad 1, y que establezcas que haya solo tres equipos totales en la planta. Cambia el periodo de mantenimiento de la actividad 2 a 862, elimina la duración de la tarea 5 de esa actividad y añade que la tarea 7 de la actividad 2 debe terminar antes de que empiece la tarea 3. También quita la regla que decía que la tarea 3 de la actividad 1 terminara antes de la tarea 4, y haz que ahora la tarea 3 de la actividad 1 termine antes de la tarea 2; para la actividad 2, elimina la dependencia que tenía la tarea 3 antes de la tarea 4 y agrega que la tarea 3 de la actividad 2 termine antes de la tarea 6.

**New request (C)**: Mira, primero borra el dato del largo del turno para la actividad A-001 y quita cualquier restricción de orden de actividades allí. Además, ajusta el número de equipos disponibles en fábrica a solo 3 y cambia la frecuencia de mantenimiento para la tarea A002 a 862. Tampoco olvides borrar la duración de la tarea T005 dentro de A002. Luego, añade una regla que haga que la tarea T007 en A002 ahora también dependa de T003 terminar antes. Para la actividad A-001, quita la regla que obligaba que T004 empezara después de T003 y en su lugar haz que T002 termine antes de T003. Finalmente, para la tarea A002, elimina la dependencia de que T004 vaya antes que T003 pero sí añade una regla nueva para que T006 sea requisito para empezar T003.

**Fidelity of the new request**: ok; direction warnings: #6 A002.tasks.T007.Order_Before = T003 (task 7 before task 3), text reads 'task 7 ... depend ... task 3': "anade una regla que haga que la tarea t007 en a002 ahora tambien dependa de t003 terminar antes" | #7 A001.tasks.T003.Order_Before = T004 (task 3 before task 4), text reads 'task 4 ... antes ... task 3': "elimina la dependencia de que t004 vaya antes que t003 pero si anade una regla nueva para que t006 sea requisito para empezar t003" | #8 A001.tasks.T003.Order_Before = T002 (task 3 before task 2), text reads 'task 2 ... antes ... task 3': "en su lugar haz que t002 termine antes de t003" | #9 A002.tasks.T003.Order_Before = T004 (task 3 before task 4), text reads 'task 4 ... antes ... task 3': "elimina la dependencia de que t004 vaya antes que t003 pero si anade una regla nueva para que t006 sea requisito para empezar t003" | #10 A002.tasks.T003.Order_Before = T006 (task 3 before task 6), text reads 'task 6 ... requisito para ... task 3': "elimina la dependencia de que t004 vaya antes que t003 pero si anade una regla nueva para que t006 sea requisito para empezar t003"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A001.Shift_duration`
- `DELETE A001.Activity_Order_Before`
- `SET Teams = 3`
- `SET A002.T_period = 862`
- `DELETE A002.tasks.T005.Duration`
- `APPEND A002.tasks.T007.Order_Before = "T003"`
- `REMOVE_ITEM A001.tasks.T003.Order_Before = "T004"`
- `APPEND A001.tasks.T003.Order_Before = "T002"`
- `REMOVE_ITEM A002.tasks.T003.Order_Before = "T004"`
- `APPEND A002.tasks.T003.Order_Before = "T006"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A001.Shift_duration`
- `DELETE A001.Activity_Order_Enforced`
- `DELETE A001.Activity_Order_Before`
- `SET Teams = 3`
- `SET A002.T_period = 862`
- `DELETE A002.tasks.T005.Duration`
- `APPEND A002.tasks.T007.Order_Before = "T003"`
- `REMOVE_ITEM A001.tasks.T004.Order_Before = "T003"`
- `APPEND A001.tasks.T002.Order_Before = "T003"`
- `REMOVE_ITEM A002.tasks.T004.Order_Before = "T003"`
- `APPEND A002.tasks.T003.Order_Before = "T006"`

**Edits that differ from the GT in C**

- `A001.Activity_Order_Enforced`: missing from the prediction (GT false)
- `A001.tasks.T002.Order_Before`: GT ["T003"] / prediction ["T003", "T003"]
- `A001.tasks.T003.Order_Before`: GT ["T002"] / prediction ["T004"]
- `A002.tasks.T003.Order_Before`: GT ["T006"] / prediction ["T004", "T006"]


## completeness level 10, sample 497 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Teams = 11`
2. `SET A002.T_wait = 40`
3. `DELETE A001.tasks.T004.Order_Before`
4. `SET A001.tasks.T003.Cost_per_hour = 87`
5. `SET Simulation_period = 6777`
6. `APPEND A002.Activity_Order_Before = "A001"`
7. `REMOVE_ITEM A001.tasks.T006.Order_Before = "T008"`
8. `APPEND A002.tasks.T006.Order_Before = "T001"`
9. `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
10. `APPEND A001.Activity_Order_Before = "A002"`

**Original request (B)**: Cambia el número de equipos totales a 11, ajusta el tiempo de espera de la actividad 2 a 40 y modifica el horizonte de simulación a 6777. Borra la regla de precedencia de la tarea 4 de la actividad 1, cambia el costo por hora de la tarea 3 de la actividad 1 a 87 y quita la regla que obligaba a que la tarea 4 de la actividad 1 terminara antes de la tarea 5. Añade que la actividad 2 debe terminar antes de que empiece la actividad 1 y también que la actividad 1 debe terminar antes de que empiece la actividad 2. Quita la regla que obligaba a que la tarea 6 de la actividad 1 terminara antes de la tarea 8, añade que la tarea 6 de la actividad 2 debe terminar antes de que empiece la tarea 1.

**New request (C)**: Mira, necesito que ajustes el número de equipos disponibles en fábrica a 11 y cambies el tiempo de espera de la tarea 40 en la actividad 2. Además, quita la regla que obligaba a la tarea T004 de la actividad A001 terminar antes de empezar algo más, y pon el costo por hora de la tarea T003 de la actividad A001 a 87. También, actualiza el horizonte de simulación a 6777. Ahora, añade que la actividad A002 dependa de terminar primero la actividad A001 y asegúrate de quitar la regla que obligaba a la tarea T006 de la actividad A001 terminar antes de T008. Luego, agrega que la tarea T006 de la actividad A002 depende de completarse primero la tarea T001 y también quita la regla que obligaba a la tarea T004 de la actividad A001 terminar antes de T005. Finalmente, haz que la actividad A001 ahora también dependa de que termine antes la actividad A002.

**Fidelity of the new request**: ok; direction warnings: #6 A002.Activity_Order_Before = A001 (activity 2 before activity 1), text reads 'activity 2 ... depend ... activity 1': "anade que la actividad a002 dependa de terminar primero la actividad a001" | #8 A002.tasks.T006.Order_Before = T001 (task 6 before task 1), text reads 'task 6 ... depend ... task 1': "agrega que la tarea t006 de la actividad a002 depende de completarse primero la tarea t001" | #10 A001.Activity_Order_Before = A002 (activity 1 before activity 2), text reads 'activity 1 ... depend ... activity 2': "haz que la actividad a001 ahora tambien dependa de que termine antes la actividad a002"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 11`
- `SET A002.T_wait = 40`
- `SET Simulation_period = 6777`
- `DELETE A001.tasks.T004.Order_Before`
- `SET A001.tasks.T003.Cost_per_hour = 87`
- `APPEND A002.Activity_Order_Before = "A001"`
- `APPEND A001.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A001.tasks.T006.Order_Before = "T008"`
- `APPEND A002.tasks.T006.Order_Before = "T001"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET Teams = 11`
- `SET Simulation_period = 6777`
- `SET A001.tasks.T003.Cost_per_hour = 87`
- `APPEND A002.Activity_Order_Before = "A001"`
- `APPEND A001.Activity_Order_Before = "A002"`
- `DELETE A001.tasks.T004.Order_Before`
- `REMOVE_ITEM A001.tasks.T006.Order_Before = "T008"`
- `APPEND A002.tasks.T006.Order_Before = "T001"`

**Edits that differ from the GT in C**

- `A002.T_wait`: GT 40 / prediction 5


## completeness level 15, sample 701 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Teams = 25`
2. `SET runId = 5918`
3. `SET A002.tasks.T004.Order_Enforced = true`
4. `DELETE A002.Activity_Order_Before`
5. `DELETE A002.Start_disp`
6. `SET A002.T_wait = 15`
7. `APPEND A002.Activity_Order_Before = "A001"`
8. `REMOVE_ITEM A001.tasks.T006.Order_Before = "T007"`
9. `APPEND A001.Activity_Order_Before = "A002"`
10. `REMOVE_ITEM A002.tasks.T003.Order_Before = "T004"`
11. `APPEND A002.tasks.T001.Order_Before = "T003"`
12. `REMOVE_ITEM A002.tasks.T006.Order_Before = "T007"`
13. `APPEND A001.tasks.T003.Order_Before = "T001"`
14. `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
15. `APPEND A002.tasks.T004.Order_Before = "T002"`

**Original request (B)**: Cambia los equipos totales a 25 y cambia el identificador de ejecución a 5918, borra la restricción de precedencia y elimina el desplazamiento inicial de la actividad 2, ajusta su tiempo de espera a 15 y haz obligatoria la secuencia de la tarea 4 de la actividad 2. Añade que la actividad 2 debe terminar antes de que empiece la actividad 1 y que la actividad 1 debe terminar antes de que empiece la actividad 2, añade que la tarea 1 de la actividad 2 debe terminar antes de la tarea 3, y añade que la tarea 4 de la actividad 2 debe terminar antes de la tarea 2. Añade que la tarea 3 de la actividad 1 debe terminar antes de la tarea 1, quita la regla que hacía que la tarea 6 de la actividad 1 terminara antes de la tarea 7, quita la regla que hacía que la tarea 3 de la actividad 2 terminara antes de la tarea 4, y quita la regla que hacía que la tarea 6 de la actividad 2 terminara antes de la tarea 7. También quita la regla que hacía que la tarea 4 de la actividad 1 terminara antes de la tarea 5.

**New request (C)**: Por favor, actualiza el número de equipos disponibles en fábrica a 25 y configura la simulación con el ID 5918. Además, asegúrate de que las tareas dentro de la actividad dos sigan una secuencia estricta, elimina cualquier restricción previa sobre qué actividades deben terminar antes que la segunda y quita ese retraso inicial del primer inicio en esa misma actividad. Ajusta el margen de espera para la actividad 2 a 15 unidades y añade que ahora también depende de que la primera actividad termine antes de empezar. Quita la regla que obligaba al paso 6 de la tarea T006 de la actividad 1 terminar antes de que empiece el paso 7, pero haz que ahora la segunda actividad tenga que terminar antes de que comience cualquier cosa en la primera actividad. Adicionalmente, elimina las restricciones que decían que los pasos 3 y 6 de la tarea T004 de la segunda actividad debían terminar antes del paso 7 y añade que el paso 1 de la tarea T001 de la misma actividad ahora depende del paso 3. También, asegúrate de que en la primera actividad se siga la regla de que el paso 3 termine antes que el paso 1 y agrega que para la cuarta tarea en la segunda actividad ahora debe terminar después del segundo paso.

**Fidelity of the new request**: #14 REMOVE_ITEM A001.tasks.T004.Order_Before = T005: missing value; direction warnings: #9 A001.Activity_Order_Before = A002 (activity 1 before activity 2), text reads 'activity 2 ... antes ... activity 1': "pero haz que ahora la segunda actividad tenga que terminar antes de que comience cualquier cosa en la primera actividad" | #11 A002.tasks.T001.Order_Before = T003 (task 1 before task 3), text reads 'task 1 ... depend ... task 3': "anade que el paso 1 de la tarea t001 de la misma actividad ahora depende del paso 3"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET runId = 5918`
- `SET Teams = 25`
- `DELETE A002.Start_disp`
- `SET A002.T_wait = 15`
- `SET A002.tasks.T004.Order_Enforced = true`
- `APPEND A002.Activity_Order_Before = "A001"`
- `APPEND A001.Activity_Order_Before = "A002"`
- `APPEND A002.tasks.T001.Order_Before = "T003"`
- `APPEND A002.tasks.T004.Order_Before = "T002"`
- `APPEND A001.tasks.T003.Order_Before = "T001"`
- `REMOVE_ITEM A001.tasks.T006.Order_Before = "T007"`
- `REMOVE_ITEM A002.tasks.T003.Order_Before = "T004"`
- `REMOVE_ITEM A002.tasks.T006.Order_Before = "T007"`
- `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET runId = 5918`
- `SET Teams = 25`
- `SET A002.Activity_Order_Enforced = true`
- `DELETE A002.Activity_Order_Before`
- `DELETE A002.Start_disp`
- `SET A002.T_wait = 15`
- `APPEND A001.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A001.tasks.T006.Order_Before = "T007"`
- `APPEND A002.Activity_Order_Before = "A001"`
- `REMOVE_ITEM A002.tasks.T004.Order_Before = "T007"`
- `APPEND A002.tasks.T001.Order_Before = "T003"`
- `APPEND A001.tasks.T003.Order_Before = "T001"`
- `APPEND A002.tasks.T002.Order_Before = "T004"`

**Edits that differ from the GT in C**

- `A001.tasks.T004.Order_Before`: GT [] / prediction ["T005"]
- `A002.Activity_Order_Enforced`: GT false / prediction true
- `A002.tasks.T002.Order_Before`: GT ["T003"] / prediction ["T003", "T004"]
- `A002.tasks.T003.Order_Before`: GT [] / prediction ["T004"]
- `A002.tasks.T004.Order_Before`: GT ["T005", "T002"] / prediction ["T005"]
- `A002.tasks.T004.Order_Enforced`: GT true / prediction false
- `A002.tasks.T006.Order_Before`: GT [] / prediction ["T007"]


## completeness level 15, sample 708 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Simulation_period = 5845`
2. `SET A001.tasks.T006.Cost_per_hour = 751`
3. `DELETE A002.tasks.T006.Order_Enforced`
4. `SET A002.tasks.T005.Order_Enforced = false`
5. `DELETE A001.tasks.T007.Cost_per_hour`
6. `DELETE A002.Team members`
7. `APPEND A001.tasks.T007.Order_Before = "T004"`
8. `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
9. `APPEND A002.tasks.T003.Order_Before = "T001"`
10. `REMOVE_ITEM A002.tasks.T004.Order_Before = "T006"`
11. `APPEND A002.tasks.T005.Order_Before = "T003"`
12. `REMOVE_ITEM A002.tasks.T001.Order_Before = "T003"`
13. `APPEND A002.Activity_Order_Before = "A001"`
14. `REMOVE_ITEM A002.tasks.T003.Order_Before = "T004"`
15. `APPEND A001.Activity_Order_Before = "A002"`

**Original request (B)**: Cambia el horizonte de simulación a 5845, actualiza la tarifa horaria de la tarea 6 de la actividad 1 a 751, elimina el costo por hora de la tarea 7 de la actividad 1 y desactiva la regla de forzar orden de la tarea 5 de la actividad 2. Borra la regla de forzar orden de la tarea 6 de la actividad 2, elimina la dotación de la actividad 2, y agrega que la tarea 7 de la actividad 1 debe terminar antes de la tarea 4, que la tarea 3 de la actividad 2 debe terminar antes de la tarea 1, y que la tarea 5 de la actividad 2 debe terminar antes de la tarea 3. Quita las reglas que hacían que la tarea 2 de la actividad 2 terminara antes de la tarea 3, que la tarea 4 terminara antes de la tarea 6, que la tarea 1 terminara antes de la tarea 3, y que la tarea 3 terminara antes de la tarea 4. Añade que la actividad 2 debe terminar antes de que empiece la actividad 1, y que la actividad 1 debe terminar antes de que empiece la actividad 2.

**New request (C)**: Necesito que ajustes el horizonte de simulación a 5845 unidades y cambies el costo por hora de la tarea 6 en la actividad 1 a 751. Además, borra la obligatoriedad de orden para la tarea 6 en la actividad 2 y desactiva la forzar orden de tareas para la tarea 5 en la misma actividad. Quita el dato del costo por hora de la tarea 7 en la actividad 1 y elimina la dotación asignada a la actividad 2. Añade que ahora la tarea 7 de la actividad 1 depende de terminar primero la tarea 4, y quita la regla que obligaba a que la tarea 2 de la actividad 2 terminara antes de empezar la tarea 3. Haz que la tarea 3 en la actividad 2 también dependa ahora de completarse primero la tarea 1 y elimina la regla que obligaba a que la tarea 4 termine antes de que empiece la tarea 6, luego añade que la tarea 5 va antes que la tarea 3. Además, quita la regla que obligaba a que la tarea 1 terminara antes de empezar la tarea 3 y finalmente, asegúrate de que la actividad 2 precede a la actividad 1 y viceversa.

**Fidelity of the new request**: ok; direction warnings: #7 A001.tasks.T007.Order_Before = T004 (task 7 before task 4), text reads 'task 7 ... depend ... task 4': "anade que ahora la tarea 7 de la actividad 1 depende de terminar primero la tarea 4" | #9 A002.tasks.T003.Order_Before = T001 (task 3 before task 1), text reads 'task 3 ... depend ... task 1': "haz que la tarea 3 en la actividad 2 tambien dependa ahora de completarse primero la tarea 1" | #15 A001.Activity_Order_Before = A002 (activity 1 before activity 2), text reads 'activity 2 ... preced ... activity 1': "asegurate de que la actividad 2 precede a la actividad 1"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Simulation_period = 5845`
- `SET A001.tasks.T006.Cost_per_hour = 751`
- `DELETE A001.tasks.T007.Cost_per_hour`
- `SET A002.tasks.T005.Order_Enforced = false`
- `DELETE A002.tasks.T006.Order_Enforced`
- `DELETE A002.Team members`
- `APPEND A001.tasks.T007.Order_Before = "T004"`
- `APPEND A002.tasks.T003.Order_Before = "T001"`
- `APPEND A002.tasks.T005.Order_Before = "T003"`
- `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
- `REMOVE_ITEM A002.tasks.T004.Order_Before = "T006"`
- `REMOVE_ITEM A002.tasks.T001.Order_Before = "T003"`
- `REMOVE_ITEM A002.tasks.T003.Order_Before = "T004"`
- `APPEND A002.Activity_Order_Before = "A001"`
- `APPEND A001.Activity_Order_Before = "A002"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET Simulation_period = 5845`
- `SET A001.tasks.T006.Cost_per_hour = 751`
- `DELETE A002.tasks.T006.Order_Enforced`
- `DELETE A002.tasks.T005.Order_Enforced`
- `DELETE A001.tasks.T007.Cost_per_hour`
- `DELETE A002.Team members`
- `APPEND A001.tasks.T007.Order_Before = "T004"`
- `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
- `APPEND A002.tasks.T003.Order_Before = "T001"`
- `REMOVE_ITEM A002.tasks.T004.Order_Before = "T006"`
- `APPEND A002.tasks.T005.Order_Before = "T003"`
- `REMOVE_ITEM A002.tasks.T001.Order_Before = "T003"`
- `APPEND A002.Activity_Order_Before = "A001"`
- `APPEND A001.Activity_Order_Before = "A002"`

**Edits that differ from the GT in C**

- `A002.tasks.T003.Order_Before`: GT ["T001"] / prediction ["T004", "T001"]
- `A002.tasks.T005.Order_Enforced`: missing from the prediction (GT false)


## completeness level 15, sample 711 (EM B 1, EM C 0)

**Technical instruction**

1. `SET Simulation_period = 7270`
2. `SET A009.Start_disp = 114`
3. `SET A001.T_period = 9092`
4. `DELETE A011.Activity_Order_Before`
5. `DELETE A013.Team members`
6. `SET Teams = 17`
7. `APPEND A002.Activity_Order_Before = "A009"`
8. `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
9. `APPEND A009.Activity_Order_Before = "A008"`
10. `REMOVE_ITEM A002.Activity_Order_Before = "A003"`
11. `APPEND A016.Activity_Order_Before = "A015"`
12. `REMOVE_ITEM A005.Activity_Order_Before = "A006"`
13. `APPEND A015.Activity_Order_Before = "A004"`
14. `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
15. `APPEND A011.Activity_Order_Before = "A015"`

**Original request (B)**: Cambia el horizonte de simulación a 7270, el desplazamiento inicial de la actividad 9 a 114 y la frecuencia de mantenimiento de la actividad 1 a 9092. Borra la restricción de que la actividad 11 tenga predecesores, elimina la dotación de la actividad 13 y cambia el número total de equipos a 17. Añade a la actividad 2 la regla de que debe terminar antes de la actividad 9, quita la regla que obligaba a que la actividad 2 terminara antes de la actividad 3, añade a la actividad 9 la regla de que debe terminar antes de la actividad 8, quita la regla que obligaba a que la actividad 13 terminara antes de la actividad 14, añade a la actividad 16 la regla de que debe terminar antes de la actividad 15, quita la regla que obligaba a que la actividad 5 terminara antes de la actividad 6, añade a la actividad 15 la regla de que debe terminar antes de la actividad 4, quita la regla que obligaba a que la actividad 3 terminara antes de la actividad 4 y añade a la actividad 11 la regla de que debe terminar antes de la actividad 15.

**New request (C)**: Por favor, ajusta el horizonte de simulación a 7270 y anota que la actividad 9 ahora tiene un inicio diferido de 114. Además, cambia el periodo entre intervenciones de la actividad 1 a 9092 y quita la restricción de orden estricto para la actividad 11. Borra también los datos de la dotación del equipo de la actividad 13 y actualiza el número de equipos totales a 17. Ahora, haz que la actividad 2 ahora también dependa de la finalización de la actividad 9 y quita la regla que obligaba a la actividad 13 terminar antes de empezar la actividad 14. Añade a la lista de precedencias de la actividad 9 para que termine antes de iniciar la actividad 8, luego quita la dependencia que hacía que la actividad 2 tuviera que terminar antes de comenzar la actividad 3. Además, agrega una nueva regla en la actividad 16 para que termine después de la finalización de la actividad 15 y quita la restricción que obligaba a la actividad 5 a terminar antes de iniciar la actividad 6. Finalmente, añade a la lista de precedencias de la actividad 15 para que termine antes de empezar la actividad 4 y actualiza las dependencias en la actividad 11 para que ahora también dependa de la finalización de la actividad 15.

**Fidelity of the new request**: ok; direction warnings: #7 A002.Activity_Order_Before = A009 (activity 2 before activity 9), text reads 'activity 2 ... depend ... activity 9': "haz que la actividad 2 ahora tambien dependa de la finalizacion de la actividad 9" | #11 A016.Activity_Order_Before = A015 (activity 16 before activity 15), text reads 'activity 16 ... despues ... activity 15': "agrega una nueva regla en la actividad 16 para que termine despues de la finalizacion de la actividad 15" | #15 A011.Activity_Order_Before = A015 (activity 11 before activity 15), text reads 'activity 11 ... depend ... activity 15': "actualiza las dependencias en la actividad 11 para que ahora tambien dependa de la finalizacion de la actividad 15"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Simulation_period = 7270`
- `SET A009.Start_disp = 114`
- `SET A001.T_period = 9092`
- `DELETE A011.Activity_Order_Before`
- `DELETE A013.Team members`
- `SET Teams = 17`
- `APPEND A002.Activity_Order_Before = "A009"`
- `REMOVE_ITEM A002.Activity_Order_Before = "A003"`
- `APPEND A009.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
- `APPEND A016.Activity_Order_Before = "A015"`
- `REMOVE_ITEM A005.Activity_Order_Before = "A006"`
- `APPEND A015.Activity_Order_Before = "A004"`
- `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
- `APPEND A011.Activity_Order_Before = "A015"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET Simulation_period = 7270`
- `SET A009.Start_disp = 114`
- `SET A001.T_period = 9092`
- `SET A011.Activity_Order_Enforced = false`
- `DELETE A013.Team members`
- `SET Teams = 17`
- `APPEND A002.Activity_Order_Before = "A009"`
- `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
- `APPEND A009.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A002.Activity_Order_Before = "A003"`
- `APPEND A016.Activity_Order_Before = "A015"`
- `REMOVE_ITEM A005.Activity_Order_Before = "A006"`
- `APPEND A015.Activity_Order_Before = "A004"`
- `APPEND A011.Activity_Order_Before = "A015"`

**Edits that differ from the GT in C**

- `A003.Activity_Order_Before`: GT [] / prediction ["A004"]
- `A011.Activity_Order_Enforced`: GT true / prediction false


## completeness level 15, sample 714 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A011.tasks.T001.Duration`
2. `SET A003.tasks.T001.Cost_per_hour = 558`
3. `DELETE A013.Activity_Order_Before`
4. `SET A015.tasks.T001.Duration = 45`
5. `SET Teams = 19`
6. `DELETE A013.Team`
7. `APPEND A001.Activity_Order_Before = "A013"`
8. `REMOVE_ITEM A015.Activity_Order_Before = "A016"`
9. `APPEND A007.Activity_Order_Before = "A003"`
10. `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
11. `APPEND A002.Activity_Order_Before = "A008"`
12. `REMOVE_ITEM A006.Activity_Order_Before = "A007"`
13. `APPEND A004.Activity_Order_Before = "A015"`
14. `REMOVE_ITEM A001.Activity_Order_Before = "A002"`
15. `APPEND A006.Activity_Order_Before = "A005"`

**Original request (B)**: Borra la duración de la tarea 1 de la actividad 11 y elimina la regla de precedencia de la actividad 13, además quita la asignación de equipo de esa actividad. Pon la tarifa horaria de la tarea 1 de la actividad 3 a 558 y fija su duración a 45 horas en la tarea 1 de la actividad 15. Ajusta el número de equipos totales a 19, añade que la actividad 1 debe terminar antes de la actividad 13, quita que la actividad 1 termine antes de la actividad 2, elimina la dependencia de que la actividad 15 termine antes de la actividad 16, y quita que la actividad 13 termine antes de la actividad 14. Agrega que la actividad 7 termine antes de la actividad 3, que la actividad 2 antes de la actividad 8, que la actividad 4 antes de la actividad 15, que la actividad 6 antes de la actividad 5, y quita que la actividad 6 termine antes de la actividad 7.

**New request (C)**: Ajusta el costo por hora de la tarea 1 en la actividad 3 a 558, cambia la duración de la tarea 1 en la actividad 15 a 45 minutos y ajusta el número de equipos disponibles en fábrica a 19. Borra la regla que obligaba a la actividad 13 a tener una secuencia estricta, quita el equipo asignado para la actividad 13 y elimina su duración de la tarea 1. Ahora, haz que la actividad 1 preceda a la actividad 13, pero quita la regla que obligaba a la actividad 15 terminar antes de empezar la actividad 16. Además, añade la actividad 3 como requisito para la actividad 7 y la actividad 8 como requisito para la actividad 2. También, quita la dependencia de que la actividad 13 termine antes de la actividad 14 y haz que la actividad 15 preceda a la actividad 4 después de eliminar la regla que obligaba a la actividad 6 terminar antes de empezar la actividad 7. Finalmente, añade la actividad 5 como requisito para la actividad 6.

**Fidelity of the new request**: #1 DELETE A011.tasks.T001.Duration: missing activity; direction warnings: #9 A007.Activity_Order_Before = A003 (activity 7 before activity 3), text reads 'activity 3 ... requisito para ... activity 7': "anade la actividad 3 como requisito para la actividad 7" | #11 A002.Activity_Order_Before = A008 (activity 2 before activity 8), text reads 'activity 8 ... requisito para ... activity 2': "la actividad 8 como requisito para la actividad 2" | #13 A004.Activity_Order_Before = A015 (activity 4 before activity 15), text reads 'activity 15 ... preced ... activity 4': "haz que la actividad 15 preceda a la actividad 4 despues de eliminar la regla que obligaba a la actividad 6 terminar antes de empezar la actividad 7" | #15 A006.Activity_Order_Before = A005 (activity 6 before activity 5), text reads 'activity 5 ... requisito para ... activity 6': "anade la actividad 5 como requisito para la actividad 6"; unit warnings: #4 Duration = 45: '45 minutos'

**Batch emitted by gpt-oss:20b in B**

- `DELETE A011.tasks.T001.Duration`
- `DELETE A013.Activity_Order_Before`
- `DELETE A013.Team`
- `SET A003.tasks.T001.Cost_per_hour = 558`
- `SET A015.tasks.T001.Duration = 45`
- `SET Teams = 19`
- `APPEND A001.Activity_Order_Before = "A013"`
- `REMOVE_ITEM A001.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A015.Activity_Order_Before = "A016"`
- `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
- `APPEND A007.Activity_Order_Before = "A003"`
- `APPEND A002.Activity_Order_Before = "A008"`
- `APPEND A004.Activity_Order_Before = "A015"`
- `APPEND A006.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A006.Activity_Order_Before = "A007"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A003.tasks.T001.Cost_per_hour = 558`
- `SET A015.tasks.T001.Duration = 0.75`
- `SET Teams = 19`
- `DELETE A013.Activity_Order_Enforced`
- `DELETE A013.Team`
- `DELETE A013.tasks.T001.Duration`
- `APPEND A001.Activity_Order_Before = "A013"`
- `REMOVE_ITEM A015.Activity_Order_Before = "A016"`
- `APPEND A003.Activity_Order_Before = "A007"`
- `APPEND A008.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A013.Activity_Order_Before = "A014"`
- `REMOVE_ITEM A006.Activity_Order_Before = "A007"`
- `APPEND A015.Activity_Order_Before = "A004"`
- `APPEND A005.Activity_Order_Before = "A006"`

**Edits that differ from the GT in C**

- `A001.Activity_Order_Before`: GT ["A013"] / prediction ["A002", "A013"]
- `A002.Activity_Order_Before`: GT ["A003", "A008"] / prediction ["A003"]
- `A003.Activity_Order_Before`: GT [] / prediction ["A007"]
- `A004.Activity_Order_Before`: GT ["A015"] / prediction []
- `A005.Activity_Order_Before`: GT [] / prediction ["A006"]
- `A006.Activity_Order_Before`: GT ["A005"] / prediction []
- `A007.Activity_Order_Before`: GT ["A008", "A003"] / prediction ["A008"]
- `A008.Activity_Order_Before`: GT [] / prediction ["A002"]
- `A011.tasks.T001.Duration`: not in the GT (prediction 33)
- `A013.Activity_Order_Before`: not in the GT (prediction [])
- `A013.Activity_Order_Enforced`: missing from the prediction (GT false)
- `A013.tasks.T001.Duration`: missing from the prediction (GT 41)
- `A015.Activity_Order_Before`: GT [] / prediction ["A004"]
- `A015.tasks.T001.Duration`: GT 45 / prediction 0.75


## completeness level 15, sample 719 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A008.T_period`
2. `DELETE A006.T_wait`
3. `SET Teams = 15`
4. `DELETE A001.tasks.T001.Requires_Shutdown`
5. `SET A005.tasks.T001.Order_Enforced = false`
6. `SET A001.T_period = 7594`
7. `APPEND A001.Activity_Order_Before = "A013"`
8. `REMOVE_ITEM A009.Activity_Order_Before = "A010"`
9. `APPEND A015.Activity_Order_Before = "A014"`
10. `REMOVE_ITEM A002.Activity_Order_Before = "A003"`
11. `APPEND A006.Activity_Order_Before = "A009"`
12. `REMOVE_ITEM A008.Activity_Order_Before = "A009"`
13. `APPEND A012.Activity_Order_Before = "A009"`
14. `REMOVE_ITEM A010.Activity_Order_Before = "A011"`
15. `APPEND A012.Activity_Order_Before = "A002"`

**Original request (B)**: Cambia el número de equipos totales a 15, borra el parámetro de período de la actividad 8, quita el tiempo de espera de la actividad 6, elimina la necesidad de apagar la máquina en el primer paso de la actividad 1 y desactiva la obligatoriedad de la secuencia de tareas en el primer paso de la actividad 5. Pon el período de la actividad 1 a 7 594 horas, añade la regla de que la actividad 1 debe terminar antes de que empiece la actividad 13 y elimina la regla que obligaba a que la actividad 9 terminara antes de la actividad 10. Haz que la actividad 15 termine antes de la actividad 14, elimina la dependencia de que la actividad 2 terminara antes de la actividad 3, añade la regla de que la actividad 6 debe terminar antes de la actividad 9 y elimina la regla que obligaba a que la actividad 8 terminara antes de la actividad 9. Agrega la regla de que la actividad 12 debe terminar antes de la actividad 9, elimina la regla que obligaba a que la actividad 10 terminara antes de la actividad 11 y añade la regla de que la actividad 12 debe terminar antes de la actividad 2.

**New request (C)**: Mira, necesito que borres el periodo entre intervenciones de la actividad A008 y también quites la demora antes de repetir de la tarea A006. Además, actualiza el número de equipos disponibles en fábrica a 15 y desactiva la opción de parada de línea para la tarea T001 de la actividad A001. Ahora, ajusta que la frecuencia de mantenimiento de la misma actividad A001 sea de 7594 y asegúrate de que la actividad A013 termine antes de empezar esta. Luego, quita la regla que obligaba a terminar A010 antes del inicio de A009, y haz que ahora también dependa de A014 para iniciar A015. Además, elimina la condición que requería A003 antes de comenzar A002, y añade a A009 como requisito previo para iniciar A006. También quita la regla que obligaba a terminar A009 antes del inicio de A008 y haz que ahora también dependa de A009 para iniciar A012. Y finalmente, elimina la condición que requería A011 antes de comenzar A010 y añade que A002 va antes que A012.

**Fidelity of the new request**: #5 SET A005.tasks.T001.Order_Enforced = False: missing activity, parameter; direction warnings: #8 A009.Activity_Order_Before = A010 (activity 9 before activity 10), text reads 'activity 10 ... antes ... activity 9': "quita la regla que obligaba a terminar a010 antes del inicio de a009" | #10 A002.Activity_Order_Before = A003 (activity 2 before activity 3), text reads 'activity 3 ... antes ... activity 2': "elimina la condicion que requeria a003 antes de comenzar a002" | #11 A006.Activity_Order_Before = A009 (activity 6 before activity 9), text reads 'activity 9 ... previ ... activity 6': "anade a a009 como requisito previo para iniciar a006" | #12 A008.Activity_Order_Before = A009 (activity 8 before activity 9), text reads 'activity 9 ... antes ... activity 8': "tambien quita la regla que obligaba a terminar a009 antes del inicio de a008" | #14 A010.Activity_Order_Before = A011 (activity 10 before activity 11), text reads 'activity 11 ... antes ... activity 10': "elimina la condicion que requeria a011 antes de comenzar a010" | #15 A012.Activity_Order_Before = A002 (activity 12 before activity 2), text reads 'activity 2 ... antes ... activity 12': "anade que a002 va antes que a012"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 15`
- `DELETE A008.T_period`
- `DELETE A006.T_wait`
- `DELETE A001.tasks.T001.Requires_Shutdown`
- `SET A005.tasks.T001.Order_Enforced = false`
- `SET A001.T_period = 7594`
- `APPEND A001.Activity_Order_Before = "A013"`
- `REMOVE_ITEM A009.Activity_Order_Before = "A010"`
- `APPEND A015.Activity_Order_Before = "A014"`
- `REMOVE_ITEM A002.Activity_Order_Before = "A003"`
- `APPEND A006.Activity_Order_Before = "A009"`
- `REMOVE_ITEM A008.Activity_Order_Before = "A009"`
- `APPEND A012.Activity_Order_Before = "A009"`
- `REMOVE_ITEM A010.Activity_Order_Before = "A011"`
- `APPEND A012.Activity_Order_Before = "A002"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A008.T_wait`
- `DELETE A006.T_wait`
- `SET Teams = 15`
- `SET A001.tasks.T001.Requires_Shutdown = false`
- `SET A001.T_period = 7594`
- `APPEND A013.Activity_Order_Before = "A001"`
- `REMOVE_ITEM A010.Activity_Order_Before = "A009"`
- `APPEND A015.Activity_Order_Before = "A014"`
- `REMOVE_ITEM A002.Activity_Order_Before = "A003"`
- `APPEND A006.Activity_Order_Before = "A009"`
- `REMOVE_ITEM A008.Activity_Order_Before = "A009"`
- `APPEND A012.Activity_Order_Before = "A009"`
- `REMOVE_ITEM A010.Activity_Order_Before = "A011"`
- `APPEND A002.Activity_Order_Before = "A012"`

**Edits that differ from the GT in C**

- `A001.Activity_Order_Before`: GT ["A002", "A013"] / prediction ["A002"]
- `A001.tasks.T001.Requires_Shutdown`: not in the GT (prediction false)
- `A002.Activity_Order_Before`: GT [] / prediction ["A012"]
- `A008.T_period`: not in the GT (prediction 3582)
- `A008.T_wait`: missing from the prediction (GT 20)
- `A009.Activity_Order_Before`: GT [] / prediction ["A010"]
- `A012.Activity_Order_Before`: GT ["A009", "A002"] / prediction ["A009"]
- `A013.Activity_Order_Before`: GT [] / prediction ["A001"]


## completeness level 15, sample 724 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A007.tasks.T001.Requires_Shutdown = false`
2. `SET Teams = 10`
3. `SET A006.Team members = 8`
4. `DELETE A006.Team members`
5. `SET A001.tasks.T001.Cost_per_hour = 487`
6. `SET A002.tasks.T002.Cost_per_hour = 97`
7. `APPEND A003.Activity_Order_Before = "A007"`
8. `REMOVE_ITEM A004.Activity_Order_Before = "A005"`
9. `APPEND A005.Activity_Order_Before = "A007"`
10. `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
11. `APPEND A002.Activity_Order_Before = "A008"`
12. `REMOVE_ITEM A005.Activity_Order_Before = "A006"`
13. `APPEND A007.tasks.T002.Order_Before = "T001"`
14. `REMOVE_ITEM A003.tasks.T001.Order_Before = "T002"`
15. `APPEND A006.tasks.T002.Order_Before = "T001"`

**Original request (B)**: Cambia los equipos totales a 10, para la actividad 7, tarea 1 no necesita parar la máquina, asigna 8 operarios a la actividad 6 y luego elimina esa dotación, establece el costo por hora de la tarea 1 de la actividad 1 en 487 y el de la tarea 2 de la actividad 2 en 97. En cuanto a dependencias, la actividad 3 debe terminar antes de la actividad 7, la actividad 5 también debe terminar antes de la actividad 7, la actividad 2 debe terminar antes de la actividad 8, se quitan las reglas que obligaban a la actividad 4 a terminar antes de la actividad 5 y a la actividad 5 antes de la actividad 6. Además, se eliminan las dependencias de que la tarea 1 de la actividad 1 termine antes de la tarea 2 y de que la tarea 1 de la actividad 3 termine antes de la tarea 2; se añade que la tarea 2 de la actividad 7 termine antes de la tarea 1 y que la tarea 2 de la actividad 6 termine antes de la tarea 1.

**New request (C)**: Mira, necesito que cambies varias cosas: desactiva el requisito de parada para la tarea T001 de la actividad A007, ajusta los equipos totales a 10 y deja la dotación del equipo en la actividad A006 en 8; pero luego borra esa restricción de dotación. Además, actualiza el costo por hora de la tarea T001 en la actividad A001 a 487 y ajusta el tarifa horaria de la tarea T002 en la actividad A002 a 97. Ahora, haz que la actividad A003 preceda a la actividad A007 y quita la regla que obligaba a la actividad A004 terminar antes de empezar la actividad A005. También, añade la regla para que la actividad A005 vaya después de la actividad A007 y agrega la dependencia para que la actividad A002 ahora también dependa de la actividad A008. Quita la regla que obligaba a la tarea T001 en la actividad A001 terminar antes de empezar la tarea T002, y añade una nueva regla para hacer que la tarea T002 en la actividad A007 empiece después de la tarea T001. Finalmente, quita la dependencia que obligaba a la tarea T001 terminar antes de empezar la tarea T002 en la actividad A003 y añade una nueva regla para hacer que la tarea T002 en la actividad A006 empiece después de la tarea T001.

**Fidelity of the new request**: ok; direction warnings: #9 A005.Activity_Order_Before = A007 (activity 5 before activity 7), text reads 'activity 5 ... despues ... activity 7': "anade la regla para que la actividad a005 vaya despues de la actividad a007" | #11 A002.Activity_Order_Before = A008 (activity 2 before activity 8), text reads 'activity 2 ... depend ... activity 8': "agrega la dependencia para que la actividad a002 ahora tambien dependa de la actividad a008" | #13 A007.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 2 ... despues ... task 1': "anade una nueva regla para hacer que la tarea t002 en la actividad a007 empiece despues de la tarea t001" | #15 A006.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 2 ... despues ... task 1': "anade una nueva regla para hacer que la tarea t002 en la actividad a006 empiece despues de la tarea t001"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `SET Teams = 10`
- `SET A007.tasks.T001.Requires_Shutdown = false`
- `SET A006.Team members = 8`
- `DELETE A006.Team members`
- `SET A001.tasks.T001.Cost_per_hour = 487`
- `SET A002.tasks.T002.Cost_per_hour = 97`
- `APPEND A003.Activity_Order_Before = "A007"`
- `APPEND A005.Activity_Order_Before = "A007"`
- `APPEND A002.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A004.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A005.Activity_Order_Before = "A006"`
- `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
- `REMOVE_ITEM A003.tasks.T001.Order_Before = "T002"`
- `APPEND A007.tasks.T002.Order_Before = "T001"`
- `APPEND A006.tasks.T002.Order_Before = "T001"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A007.tasks.T001.Requires_Shutdown = false`
- `SET Teams = 10`
- `SET A006.Team members = 8`
- `DELETE A006.Team members`
- `SET A001.tasks.T001.Cost_per_hour = 487`
- `SET A002.tasks.T002.Cost_per_hour = 97`
- `APPEND A003.Activity_Order_Before = "A007"`
- `REMOVE_ITEM A004.Activity_Order_Before = "A005"`
- `APPEND A007.Activity_Order_Before = "A005"`
- `APPEND A008.Activity_Order_Before = "A002"`
- `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
- `APPEND A007.tasks.T001.Order_Before = "T002"`
- `REMOVE_ITEM A003.tasks.T001.Order_Before = "T002"`
- `APPEND A006.tasks.T001.Order_Before = "T002"`

**Edits that differ from the GT in C**

- `A002.Activity_Order_Before`: GT ["A003", "A008"] / prediction ["A003"]
- `A005.Activity_Order_Before`: GT ["A007"] / prediction ["A006"]
- `A006.tasks.T001.Order_Before`: GT ["T002"] / prediction ["T002", "T002"]
- `A006.tasks.T002.Order_Before`: GT ["T001"] / prediction []
- `A007.Activity_Order_Before`: GT [] / prediction ["A005"]
- `A007.tasks.T001.Order_Before`: GT ["T002"] / prediction ["T002", "T002"]
- `A007.tasks.T002.Order_Before`: GT ["T001"] / prediction []
- `A008.Activity_Order_Before`: GT [] / prediction ["A002"]


## completeness level 15, sample 725 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A005.Activity_Order_Enforced`
2. `DELETE A002.tasks.T002.Order_Enforced`
3. `DELETE A004.tasks.T002.Requires_Shutdown`
4. `DELETE A005.Shift_duration`
5. `SET Simulation_period = 8947`
6. `DELETE A005.Start_disp`
7. `APPEND A007.Activity_Order_Before = "A002"`
8. `REMOVE_ITEM A005.Activity_Order_Before = "A006"`
9. `APPEND A008.Activity_Order_Before = "A005"`
10. `REMOVE_ITEM A004.Activity_Order_Before = "A005"`
11. `APPEND A002.Activity_Order_Before = "A007"`
12. `REMOVE_ITEM A002.tasks.T001.Order_Before = "T002"`
13. `APPEND A007.Activity_Order_Before = "A006"`
14. `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
15. `APPEND A002.Activity_Order_Before = "A005"`

**Original request (B)**: Borra la regla de orden forzado de la actividad 5, la regla que obliga a la tarea 2 de la actividad 2 a seguir secuencia, la necesidad de parada para la tarea 2 de la actividad 4, la duración del turno de la actividad 5 y el desplazamiento inicial de la actividad 5, y pon el horizonte de simulación a 8947. Añade que la actividad 7 debe terminar antes de que empiece la actividad 2, que la actividad 8 debe terminar antes de que empiece la actividad 5, que la actividad 2 debe terminar antes de que empiece la actividad 7, que la actividad 7 debe terminar antes de que empiece la actividad 6 y que la actividad 2 debe terminar antes de que empiece la actividad 5. Quita la regla que obligaba a que la actividad 5 terminara antes de que empezara la actividad 6, la regla que obligaba a que la actividad 4 terminara antes de que empezara la actividad 5, la regla que obligaba a que la tarea 1 de la actividad 2 terminara antes de la tarea 2, y la regla que obligaba a que la tarea 1 de la actividad 8 terminara antes de la tarea 2.

**New request (C)**: Necesito que borres las restricciones de orden para la actividad 5 y su duración del turno, además quita el parámetro de obligatoriedad de la secuencia estricta para la tarea 2 dentro de la actividad 2 y el requisito de parada para la tarea 2 en la actividad 4. También ajusta el horizonte de simulación a 8947 y elimina el retraso inicial de la actividad 5. Ahora, añade que la actividad 7 precede a la actividad 2 y también que la actividad 5 va antes que la actividad 8; además quita la regla que obligaba a que la actividad 6 terminara antes de empezar la actividad 5 y elimina el bloqueo que tenía la tarea 1 en la actividad 2 sobre la tarea 2. Finalmente, añade también que la actividad 7 va antes que la actividad 5 y quita la dependencia entre la tarea 1 y la tarea 2 dentro de la actividad 8.

**Fidelity of the new request**: ok; direction warnings: #8 A005.Activity_Order_Before = A006 (activity 5 before activity 6), text reads 'activity 6 ... antes ... activity 5': "ademas quita la regla que obligaba a que la actividad 6 terminara antes de empezar la actividad 5" | #9 A008.Activity_Order_Before = A005 (activity 8 before activity 5), text reads 'activity 5 ... antes ... activity 8': "tambien que la actividad 5 va antes que la actividad 8" | #11 A002.Activity_Order_Before = A007 (activity 2 before activity 7), text reads 'activity 7 ... preced ... activity 2': "anade que la actividad 7 precede a la actividad 2"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A005.Activity_Order_Enforced`
- `DELETE A002.tasks.T002.Order_Enforced`
- `DELETE A004.tasks.T002.Requires_Shutdown`
- `DELETE A005.Shift_duration`
- `DELETE A005.Start_disp`
- `SET Simulation_period = 8947`
- `APPEND A007.Activity_Order_Before = "A002"`
- `APPEND A008.Activity_Order_Before = "A005"`
- `APPEND A002.Activity_Order_Before = "A007"`
- `APPEND A007.Activity_Order_Before = "A006"`
- `APPEND A002.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A005.Activity_Order_Before = "A006"`
- `REMOVE_ITEM A004.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A002.tasks.T001.Order_Before = "T002"`
- `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A005.Activity_Order_Enforced`
- `DELETE A005.Shift_duration`
- `DELETE A002.tasks.T002.Order_Enforced`
- `DELETE A004.tasks.T002.Requires_Shutdown`
- `SET Simulation_period = 8947`
- `DELETE A005.Start_disp`
- `APPEND A007.Activity_Order_Before = "A002"`
- `APPEND A005.Activity_Order_Before = "A008"`
- `REMOVE_ITEM A006.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A002.tasks.T001.Order_Before = "T002"`
- `APPEND A007.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`

**Edits that differ from the GT in C**

- `A002.Activity_Order_Before`: GT ["A007", "A005"] / prediction []
- `A004.Activity_Order_Before`: GT [] / prediction ["A005"]
- `A005.Activity_Order_Before`: GT [] / prediction ["A006", "A008"]
- `A007.Activity_Order_Before`: GT ["A002", "A006"] / prediction ["A002", "A005"]
- `A008.Activity_Order_Before`: GT ["A005"] / prediction []


## completeness level 15, sample 727 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A006.tasks.T002.Duration`
2. `DELETE A007.T_wait`
3. `SET A008.tasks.T001.Requires_Shutdown = false`
4. `SET A008.Team members = 6`
5. `DELETE A008.Activity_Order_Before`
6. `SET Teams = 9`
7. `APPEND A006.tasks.T002.Order_Before = "T001"`
8. `REMOVE_ITEM A006.tasks.T001.Order_Before = "T002"`
9. `APPEND A005.Activity_Order_Before = "A001"`
10. `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
11. `APPEND A008.tasks.T002.Order_Before = "T001"`
12. `REMOVE_ITEM A003.tasks.T001.Order_Before = "T002"`
13. `APPEND A008.Activity_Order_Before = "A005"`
14. `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
15. `APPEND A002.Activity_Order_Before = "A004"`

**Original request (B)**: Elimina la duración de la tarea 2 de la actividad 6 y borra la restricción de tiempo de espera de la actividad 7; deja que la tarea 1 de la actividad 8 no requiera parada, asigna 6 operarios a esa actividad y borra la regla de que la actividad 8 deba terminar antes de otra, mientras actualizas el número total de equipos a 9. Añade que la tarea 2 de la actividad 6 debe terminar antes de la tarea 1 y quita la regla que obligaba a la tarea 1 de la actividad 6 a terminar antes de la tarea 2; haz que la actividad 5 termine antes de la actividad 1, quita la regla que obligaba a la tarea 1 de la actividad 8 a terminar antes de la tarea 2, y añade que la tarea 2 de la actividad 8 debe terminar antes de la tarea 1. Además, quita la regla que obligaba a la tarea 1 de la actividad 3 a terminar antes de la tarea 2, haz que la actividad 8 termine antes de la actividad 5, quita la regla que obligaba a la tarea 1 de la actividad 1 a terminar antes de la tarea 2, y haz que la actividad 2 termine antes de la actividad 4.

**New request (C)**: Mira, necesito que borres el tiempo de ejecución para la tarea 2 de la actividad 6 y también quites el margen de espera de la actividad 7. Además, ajusta la segunda tarea de la actividad 8 para que no requiera parada y deja la dotación del equipo asignado a esa misma actividad en 6 operarios. Quita la regla de orden estricto entre las actividades en A008 y actualiza el número total de equipos disponibles a 9. Ahora, haz que la tarea 2 de la actividad 6 dependa de la tarea 1 y quita la dependencia que obligaba a la tarea 1 de la misma actividad a terminar antes de empezar la tarea 2. Añade una nueva regla para que la actividad 5 preceda a la actividad 1 y también quita la dependencia que requería que la tarea 2 termine antes de iniciar la tarea 1 en la actividad 8. Hacer lo mismo con la tarea 2 de la actividad 6, asegurándote de que va después de la tarea 1, y haz que la primera tarea de A003 ya no dependa de T002. Ajusta también la actividad 8 para que vaya ahora antes de la actividad 5 y finalmente añade a la actividad 2 una dependencia de que termine la actividad 4 primero.

**Fidelity of the new request**: ok; direction warnings: #7 A006.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 2 ... depend ... task 1': "haz que la tarea 2 de la actividad 6 dependa de la tarea 1" | #10 A008.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 2 ... antes ... task 1': "tambien quita la dependencia que requeria que la tarea 2 termine antes de iniciar la tarea 1 en la actividad 8" | #11 A008.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 1 ... antes ... task 2': "quita la dependencia que obligaba a la tarea 1 de la misma actividad a terminar antes de empezar la tarea 2" | #12 A003.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 1 ... depend ... task 2': "haz que la primera tarea de a003 ya no dependa de t002" | #15 A002.Activity_Order_Before = A004 (activity 2 before activity 4), text reads 'activity 2 ... depend ... activity 4': "finalmente anade a la actividad 2 una dependencia de que termine la actividad 4 primero"; unit warnings: none

**Batch emitted by gpt-oss:20b in B**

- `DELETE A006.tasks.T002.Duration`
- `DELETE A007.T_wait`
- `SET A008.tasks.T001.Requires_Shutdown = false`
- `SET A008.Team members = 6`
- `DELETE A008.Activity_Order_Before`
- `SET Teams = 9`
- `APPEND A006.tasks.T002.Order_Before = "T001"`
- `REMOVE_ITEM A006.tasks.T001.Order_Before = "T002"`
- `APPEND A005.Activity_Order_Before = "A001"`
- `REMOVE_ITEM A008.tasks.T001.Order_Before = "T002"`
- `APPEND A008.tasks.T002.Order_Before = "T001"`
- `REMOVE_ITEM A003.tasks.T001.Order_Before = "T002"`
- `APPEND A008.Activity_Order_Before = "A005"`
- `REMOVE_ITEM A001.tasks.T001.Order_Before = "T002"`
- `APPEND A002.Activity_Order_Before = "A004"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A006.tasks.T002.Duration`
- `DELETE A007.T_wait`
- `SET A008.tasks.T002.Requires_Shutdown = false`
- `SET A008.Team members = 6`
- `DELETE A008.Activity_Order_Enforced`
- `SET Teams = 9`
- `APPEND A006.tasks.T002.Order_Before = "T001"`
- `REMOVE_ITEM A006.tasks.T001.Order_Before = "T002"`
- `APPEND A005.Activity_Order_Before = "A001"`
- `REMOVE_ITEM A008.tasks.T002.Order_Before = "T001"`
- `REMOVE_ITEM A003.tasks.T001.Order_Before = "T002"`
- `APPEND A008.Activity_Order_Before = "A005"`
- `APPEND A002.Activity_Order_Before = "A004"`

**Edits that differ from the GT in C**

- `A001.tasks.T001.Order_Before`: GT [] / prediction ["T002"]
- `A008.Activity_Order_Enforced`: missing from the prediction (GT false)
- `A008.tasks.T001.Order_Before`: GT [] / prediction ["T002"]
- `A008.tasks.T001.Requires_Shutdown`: GT false / prediction true
- `A008.tasks.T002.Order_Before`: GT ["T001"] / prediction []


## completeness level 15, sample 735 (EM B 1, EM C 0)

**Technical instruction**

1. `SET A001.T_wait = 23`
2. `SET A001.Shift_duration = 11`
3. `SET A001.T_wait = 29`
4. `SET A001.tasks.T002.Order_Enforced = true`
5. `DELETE A001.tasks.T002.Duration`
6. `SET runId = 8220`
7. `APPEND A002.tasks.T004.Order_Before = "T001"`
8. `REMOVE_ITEM A004.tasks.T003.Order_Before = "T004"`
9. `APPEND A004.tasks.T002.Order_Before = "T004"`
10. `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
11. `APPEND A001.Activity_Order_Before = "A004"`
12. `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
13. `APPEND A003.tasks.T004.Order_Before = "T003"`
14. `REMOVE_ITEM A004.tasks.T001.Order_Before = "T003"`
15. `APPEND A004.tasks.T003.Order_Before = "T002"`

**Original request (B)**: Cambia el tiempo de espera de la actividad 1 a 29, ajusta su duración de turno a 11 horas, activa la obligatoriedad de la secuencia de la tarea 2 y elimina la duración de esa tarea. Modifica el identificador de la ejecución a 8220 y añade que la tarea 4 de la actividad 2 debe terminar antes de la tarea 1, mientras quitas la regla que obligaba a la tarea 3 de la actividad 4 a terminar antes de la tarea 4. Añade que la tarea 2 de la actividad 4 debe terminar antes de la tarea 4, quita la regla que obligaba a la tarea 2 de la actividad 2 a terminar antes de la tarea 3, y añade que la actividad 1 debe terminar antes de la actividad 4. Quita la regla que obligaba a la actividad 3 a terminar antes de la actividad 4, añade que la tarea 4 de la actividad 3 debe terminar antes de la tarea 3, quita la regla que obligaba a la tarea 1 de la actividad 4 a terminar antes de la tarea 3 y añade que la tarea 3 de la actividad 4 debe terminar antes de la tarea 2.

**New request (C)**: Mira, ajusta la demora antes de repetir de la actividad 1 a 29 minutos y también cambia la duración del turno a 11 horas. Ahora, activa la secuencia estricta para la tarea 2 de esa misma actividad, pero quita el dato de tiempo operativo de esa tarea. Cambia el identificador de ejecución a 8220. Además, haz que ahora también dependa de T001 la tarea 4 de la actividad 2 y quita la regla que obligaba a que la tarea 3 de la actividad 4 terminara antes de empezar T004. Añade a T004 en las dependencias de la tarea 2 de la actividad 4, pero quita la dependencia de que T002 de la actividad 2 vaya antes que T003. Hacer que la actividad 1 termine antes de empezar la actividad 4, y elimina la regla que obligaba a que la actividad 3 terminara antes de empezar la actividad 4. Añade una dependencia en la tarea 4 de la actividad 3 para que T003 vaya primero y quita la regla que obligaba a que la tarea 1 de la actividad 4 termine antes de empezar T003, además añade a T002 como requisito previo para la tarea 3 de la misma actividad.

**Fidelity of the new request**: #1 SET A001.T_wait = 23: missing value; direction warnings: #15 A004.tasks.T003.Order_Before = T002 (task 3 before task 2), text reads 'task 2 ... previ ... task 3': "ademas anade a t002 como requisito previo para la tarea 3 de la misma actividad"; unit warnings: #3 T_wait = 29: '29 minutos'

**Batch emitted by gpt-oss:20b in B**

- `SET A001.T_wait = 29`
- `SET A001.Shift_duration = 11`
- `SET A001.tasks.T002.Order_Enforced = true`
- `DELETE A001.tasks.T002.Duration`
- `SET runId = 8220`
- `APPEND A002.tasks.T004.Order_Before = "T001"`
- `REMOVE_ITEM A004.tasks.T003.Order_Before = "T004"`
- `APPEND A004.tasks.T002.Order_Before = "T004"`
- `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
- `APPEND A001.Activity_Order_Before = "A004"`
- `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
- `APPEND A003.tasks.T004.Order_Before = "T003"`
- `REMOVE_ITEM A004.tasks.T001.Order_Before = "T003"`
- `APPEND A004.tasks.T003.Order_Before = "T002"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `SET A001.T_wait = 0.4833`
- `SET A001.Shift_duration = 11`
- `SET A001.tasks.T002.Order_Enforced = true`
- `DELETE A001.tasks.T002.Duration`
- `SET runId = 8220`
- `APPEND A002.tasks.T004.Order_Before = "T001"`
- `REMOVE_ITEM A004.tasks.T003.Order_Before = "T004"`
- `APPEND A004.tasks.T002.Order_Before = "T004"`
- `REMOVE_ITEM A002.tasks.T002.Order_Before = "T003"`
- `APPEND A001.Activity_Order_Before = "A004"`
- `REMOVE_ITEM A003.Activity_Order_Before = "A004"`
- `APPEND A003.tasks.T004.Order_Before = "T003"`
- `REMOVE_ITEM A004.tasks.T001.Order_Before = "T003"`
- `APPEND A004.tasks.T003.Order_Before = "T002"`

**Edits that differ from the GT in C**

- `A001.T_wait`: GT 29 / prediction 0.4833


## completeness level 15, sample 743 (EM B 1, EM C 0)

**Technical instruction**

1. `DELETE A001.Shift_duration`
2. `SET A001.tasks.T001.Cost_per_hour = 706`
3. `DELETE A001.tasks.T003.Order_Enforced`
4. `SET A001.Shift_duration = 7`
5. `DELETE A001.tasks.T007.Requires_Shutdown`
6. `SET A001.tasks.T006.Cost_per_hour = 477`
7. `APPEND A001.tasks.T002.Order_Before = "T014"`
8. `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
9. `APPEND A001.tasks.T016.Order_Before = "T006"`
10. `REMOVE_ITEM A001.tasks.T001.Order_Before = "T003"`
11. `APPEND A001.tasks.T004.Order_Before = "T003"`
12. `REMOVE_ITEM A001.tasks.T008.Order_Before = "T009"`
13. `APPEND A001.tasks.T013.Order_Before = "T003"`
14. `REMOVE_ITEM A001.tasks.T002.Order_Before = "T003"`
15. `APPEND A001.tasks.T004.Order_Before = "T013"`

**Original request (B)**: Cambia el turno de la actividad 1, borrándolo primero y luego poniéndolo a 7 horas, y actualiza el costo por hora de la tarea 1 a 706 y el de la tarea 6 a 477, además elimina la regla de orden de la tarea 3 y la necesidad de apagar la máquina en la tarea 7. Añade que la tarea 2 debe terminar antes de la tarea 14, que la tarea 16 debe terminar antes de la tarea 6, que la tarea 4 debe terminar antes de la tarea 3 y antes de la tarea 13, y que la tarea 13 debe terminar antes de la tarea 3, mientras quitas que la tarea 4 debía terminar antes de la tarea 5, que la tarea 8 debía terminar antes de la tarea 9, y que la tarea 1 y la tarea 2 debían terminar antes de la tarea 3.

**New request (C)**: Mira, necesito que borres el dato del largo del turno para la actividad 1 y ajustes el costo por hora de la tarea 1 a 706 euros. Además, elimina la obligatoriedad de la secuencia de la tarea 3 en la actividad 1 y actualiza el horario del turno de la misma actividad a 7 horas. También quita la necesidad de parar la máquina para la tarea 7, y ajusta el costo por hora de la tarea 6 a 477 euros. Ahora, añade una nueva dependencia para que la tarea 2 vaya antes que la tarea 14, y elimina la regla que obligaba a que la tarea 4 terminara antes de empezar la tarea 5. Añade también que la tarea 16 va ahora también después de la tarea 6, quita la dependencia que hacía que la tarea 1 vaya antes que la tarea 3, y agrega una nueva regla para que la tarea 4 ahora debe terminar antes de la tarea 3. Luego, elimina el requisito anterior que obligaba a que la tarea 8 termine antes de comenzar la tarea 9, añade también que la tarea 13 precede a la tarea 3 y finalmente agrega otra regla para que la tarea 4 va ahora antes de la tarea 13.

**Fidelity of the new request**: ok; direction warnings: #9 A001.tasks.T016.Order_Before = T006 (task 16 before task 6), text reads 'task 16 ... despues ... task 6': "anade tambien que la tarea 16 va ahora tambien despues de la tarea 6"; unit warnings: #2 Cost_per_hour = 706: '706 euros' | #6 Cost_per_hour = 477: '477 euros'

**Batch emitted by gpt-oss:20b in B**

- `DELETE A001.Shift_duration`
- `SET A001.Shift_duration = 7`
- `SET A001.tasks.T001.Cost_per_hour = 706`
- `SET A001.tasks.T006.Cost_per_hour = 477`
- `DELETE A001.tasks.T003.Order_Enforced`
- `DELETE A001.tasks.T007.Requires_Shutdown`
- `APPEND A001.tasks.T002.Order_Before = "T014"`
- `APPEND A001.tasks.T016.Order_Before = "T006"`
- `APPEND A001.tasks.T004.Order_Before = "T003"`
- `APPEND A001.tasks.T004.Order_Before = "T013"`
- `APPEND A001.tasks.T013.Order_Before = "T003"`
- `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
- `REMOVE_ITEM A001.tasks.T008.Order_Before = "T009"`
- `REMOVE_ITEM A001.tasks.T001.Order_Before = "T003"`
- `REMOVE_ITEM A001.tasks.T002.Order_Before = "T003"`

**Edits that differ from the GT in B**

- none (exact match)

**Batch emitted by gpt-oss:20b in C**

- `DELETE A001.Shift_duration`
- `SET A001.Shift_duration = 7`
- `SET A001.tasks.T001.Cost_per_hour = 706`
- `DELETE A001.tasks.T003.Order_Enforced`
- `DELETE A001.tasks.T007.Requires_Shutdown`
- `SET A001.tasks.T006.Cost_per_hour = 477`
- `APPEND A001.tasks.T002.Order_Before = "T014"`
- `REMOVE_ITEM A001.tasks.T004.Order_Before = "T005"`
- `APPEND A001.tasks.T004.Order_Before = "T003"`
- `APPEND A001.tasks.T004.Order_Before = "T013"`
- `APPEND A001.tasks.T006.Order_Before = "T016"`
- `REMOVE_ITEM A001.tasks.T001.Order_Before = "T003"`
- `REMOVE_ITEM A001.tasks.T008.Order_Before = "T009"`
- `APPEND A001.tasks.T013.Order_Before = "T003"`

**Edits that differ from the GT in C**

- `A001.tasks.T002.Order_Before`: GT ["T014"] / prediction ["T003", "T014"]
- `A001.tasks.T006.Order_Before`: GT ["T007"] / prediction ["T007", "T016"]
- `A001.tasks.T016.Order_Before`: GT ["T006"] / prediction []
