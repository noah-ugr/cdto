# Original vs re-humanised requests (20 random pairs, seed 42)

## 1. completeness level 1, sample 20

Technical: SET Simulation_period = 15930

- Original (gpt-oss:20b): Cambia el horizonte de simulación a 15930
- New (qwen2.5:32b): Mira, ajusta el horizonte de simulación a 15930 y anota por ahí que tenemos 8 actividades totales con 10 equipos disponibles en fábrica.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 2. completeness level 5, sample 233

Technical: SET A001.Team members = 10; SET runId = 8530; DELETE A001.Team members; APPEND A001.tasks.T010.Order_Before = T015; REMOVE_ITEM A001.tasks.T011.Order_Before = T013

- Original (gpt-oss:20b): Pon la dotación de la actividad 1 a 10 operarios y luego elimina ese dato, actualiza el identificador de ejecución a 8530, añade que la tarea 10 debe terminar antes de que empiece la tarea 15 y elimina la regla que hacía obligatoria que la tarea 11 terminara antes de la tarea 13.
- New (qwen2.5:32b): Por favor, ajusta el personal asignado a 10 para la actividad A-001 y también actualiza el ID de ejecución a 8530, luego borra por completo el dato del tamaño de la cuadrilla en esa misma actividad, además añade que ahora la tarea T010 debe terminar antes de que empiece T015, y finalmente quita la regla que obligaba a que T011 termine antes de empezar T013.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 3. completeness level 10, sample 452

Technical: DELETE A003.tasks.T001.Requires_Shutdown; SET A002.Team = TeamF; DELETE A004.tasks.T002.Requires_Shutdown; DELETE A002.tasks.T002.Order_Before; SET A003.Shift_duration = 6; APPEND A001.Activity_Order_Before = A004; REMOVE_ITEM A001.tasks.T002.Order_Before = T003; APPEND A004.tasks.T003.Order_Before = T001; REMOVE_ITEM A001.Activity_Order_Before = A002; APPEND A004.Activity_Order_Before = A003

- Original (gpt-oss:20b): Elimina la necesidad de parada para la tarea 1 de la actividad 3 y para la tarea 2 de la actividad 4, borra la regla que la tarea 2 de la actividad 2 deba terminar antes de otra, quita la restricción que la tarea 2 de la actividad 1 deba terminar antes de la tarea 3 y elimina la regla que la actividad 1 deba terminar antes de la actividad 2. Cambia el equipo asignado de la actividad 2 a TeamF y ajusta la duración del turno de la actividad 3 a 6 horas. Añade que la actividad 1 debe terminar antes de la actividad 4, que la tarea 3 de la actividad 4 debe terminar antes de la tarea 1 y que la actividad 4 debe terminar antes de la actividad 3.
- New (qwen2.5:32b): Mira, necesito que borres el requisito de parada para la tarea 1 de la actividad A-003 y también elimines la misma restricción para la tarea 2 de la actividad A-004. Además, ajusta la cuadrilla asignada a la actividad A-002 al equipo TeamF y cámbiale el largo del turno a 6 horas. También hay que quitar el requisito secuencial entre la tarea 2 de la actividad A-002 y su siguiente paso. Luego, haz que ahora también dependa la actividad 1 de terminar antes de empezar la actividad 4, pero borra la regla que obligaba a que la actividad 1 vaya antes que la actividad 2 y quita la regla que decía que la tarea 3 debe terminar antes de empezar la tarea 2. Finalmente, asegúrate de añadir una nueva dependencia para que la tarea 1 termine antes de poder iniciar la tarea 3 de la actividad A-004, y también haz que la actividad 3 deba terminar antes de que empiece la actividad 4.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: direction: #7 A001.tasks.T002.Order_Before = T003 (task 2 before task 3), text reads 'task 3 ... antes ... task 2': "quita la regla que decia que la tarea 3 debe terminar antes de empezar la tarea 2" | #8 A004.tasks.T003.Order_Before = T001 (task 3 before task 1), text reads 'task 1 ... antes ... task 3': "asegurate de anadir una nueva dependencia para que la tarea 1 termine antes de poder iniciar la tarea 3 de la actividad a-004" | #10 A004.Activity_Order_Before = A003 (activity 4 before activity 3), text reads 'activity 3 ... antes ... activity 4': "tambien haz que la actividad 3 deba terminar antes de que empiece la actividad 4"
- Warnings original: none

## 4. completeness level 10, sample 474

Technical: DELETE A001.tasks.T001.Duration; SET A001.Team members = 10; DELETE A008.tasks.T001.Order_Before; SET A004.tasks.T001.Duration = 50; SET A005.tasks.T001.Cost_per_hour = 563; APPEND A003.Activity_Order_Before = A010; REMOVE_ITEM A013.Activity_Order_Before = A014; APPEND A007.Activity_Order_Before = A010; REMOVE_ITEM A008.Activity_Order_Before = A009; APPEND A006.Activity_Order_Before = A016

- Original (gpt-oss:20b): Necesito que borres el parámetro de duración de la tarea 1 de la actividad 1, cambies la dotación de esa misma actividad a 10 operarios y elimines la regla de precedencia de la tarea 1 de la actividad 8. Además, cambia la duración de la tarea 1 de la actividad 4 a 50 y el costo por hora de la tarea 1 de la actividad 5 a 563. Añade también a las actividades 3 y 7 la regla de que deben terminar antes de la actividad 10, y a la actividad 6 la regla de que debe terminar antes de la actividad 16, mientras quitas la regla que obligaba a que la actividad 13 terminara antes de la actividad 14 y la regla que obligaba a que la actividad 8 terminara antes de la actividad 9.
- New (qwen2.5:32b): Mira, necesito que borres el tiempo de proceso de la tarea 1 en la actividad A-001, y ajustes la cantidad de operarios a 10 para esa actividad. Además, quita cualquier regla que indicara que la tarea 1 de la actividad A008 debía terminar antes de otra, y ahora pon la duración de la tarea 1 en la actividad A-004 en 50 minutos. Ajusta el costo operativo de la tarea 1 de la actividad A-005 a 563 por hora. Haz que la actividad A-003 también dependa de terminar antes de empezar la actividad A-010, y quita la regla que obligaba a que la actividad A-013 terminara antes de comenzar la actividad A-014. Ahora, asegúrate de añadir una nueva dependencia para que la actividad A-007 también tenga que cumplirse antes de iniciar la A-010 y por último, agrega una regla en A-006 indicando que debe terminar antes de que comience la actividad A-016.
- Fidelity new: #9 REMOVE_ITEM A008.Activity_Order_Before = A009: missing value
- Fidelity original: ok
- Warnings new: direction: #6 A003.Activity_Order_Before = A010 (activity 3 before activity 10), text reads 'activity 3 ... depend ... activity 10': "haz que la actividad a-003 tambien dependa de terminar antes de empezar la actividad a-010"; units: #4 Duration = 50: '50 minutos'
- Warnings original: none

## 5. completeness level 10, sample 493

Technical: SET A002.T_period = 4357; SET runId = 3817; SET Simulation_period = 14630; DELETE A002.tasks.T004.Cost_per_hour; SET A002.tasks.T005.Cost_per_hour = 871; APPEND A001.tasks.T004.Order_Before = T003; REMOVE_ITEM A002.tasks.T001.Order_Before = T002; APPEND A001.tasks.T001.Order_Before = T005; REMOVE_ITEM A001.tasks.T001.Order_Before = T002; APPEND A001.tasks.T004.Order_Before = T002

- Original (gpt-oss:20b): Cambia la frecuencia de mantenimiento de la actividad 2 a 4357, pon el identificador de ejecución a 3817 y ajusta el horizonte de simulación a 14630. Borra el costo por hora de la tarea 4 de la actividad 2 y actualiza el costo por hora de la tarea 5 de la actividad 2 a 871. Añade que la tarea 4 de la actividad 1 debe terminar antes de que empiece la tarea 3 y también antes de que empiece la tarea 2, y elimina la regla que obligaba a que la tarea 1 de la actividad 2 terminara antes de empezar la tarea 2. Añade que la tarea 1 de la actividad 1 debe terminar antes de que empiece la tarea 5 y elimina la regla que obligaba a que la tarea 1 de la actividad 1 terminara antes de empezar la tarea 2.
- New (qwen2.5:32b): Cambia el periodo entre intervenciones para actividad 2 a 4357 y también ajusta la identificación de ejecución a 3817. Ahora, actualiza el horizonte de simulación a 14630 y borra el costo por hora de la tarea 4 en la actividad 2. Ajusta el costo por hora para la tarea 5 en la actividad 2 a 871. Además, haz que ahora también dependa la tarea 4 de la tarea 3 en la actividad 1 y quita la regla que obligaba a que la tarea 1 termine antes de empezar la tarea 2 en la actividad 2. Finalmente, añade que la tarea 1 en la actividad 1 debe terminar antes de empezar la tarea 5 y también que la tarea 4 en la actividad 1 va antes que la tarea 2, pero quita la regla del inicio de la tarea 1 antes de la tarea 2.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 6. completeness level 15, sample 727

Technical: DELETE A006.tasks.T002.Duration; DELETE A007.T_wait; SET A008.tasks.T001.Requires_Shutdown = False; SET A008.Team members = 6; DELETE A008.Activity_Order_Before; SET Teams = 9; APPEND A006.tasks.T002.Order_Before = T001; REMOVE_ITEM A006.tasks.T001.Order_Before = T002; APPEND A005.Activity_Order_Before = A001; REMOVE_ITEM A008.tasks.T001.Order_Before = T002; APPEND A008.tasks.T002.Order_Before = T001; REMOVE_ITEM A003.tasks.T001.Order_Before = T002; APPEND A008.Activity_Order_Before = A005; REMOVE_ITEM A001.tasks.T001.Order_Before = T002; APPEND A002.Activity_Order_Before = A004

- Original (gpt-oss:20b): Elimina la duración de la tarea 2 de la actividad 6 y borra la restricción de tiempo de espera de la actividad 7; deja que la tarea 1 de la actividad 8 no requiera parada, asigna 6 operarios a esa actividad y borra la regla de que la actividad 8 deba terminar antes de otra, mientras actualizas el número total de equipos a 9. Añade que la tarea 2 de la actividad 6 debe terminar antes de la tarea 1 y quita la regla que obligaba a la tarea 1 de la actividad 6 a terminar antes de la tarea 2; haz que la actividad 5 termine antes de la actividad 1, quita la regla que obligaba a la tarea 1 de la actividad 8 a terminar antes de la tarea 2, y añade que la tarea 2 de la actividad 8 debe terminar antes de la tarea 1. Además, quita la regla que obligaba a la tarea 1 de la actividad 3 a terminar antes de la tarea 2, haz que la actividad 8 termine antes de la actividad 5, quita la regla que obligaba a la tarea 1 de la actividad 1 a terminar antes de la tarea 2, y haz que la actividad 2 termine antes de la actividad 4.
- New (qwen2.5:32b): Mira, necesito que borres el tiempo de ejecución para la tarea 2 de la actividad 6 y también quites el margen de espera de la actividad 7. Además, ajusta la segunda tarea de la actividad 8 para que no requiera parada y deja la dotación del equipo asignado a esa misma actividad en 6 operarios. Quita la regla de orden estricto entre las actividades en A008 y actualiza el número total de equipos disponibles a 9. Ahora, haz que la tarea 2 de la actividad 6 dependa de la tarea 1 y quita la dependencia que obligaba a la tarea 1 de la misma actividad a terminar antes de empezar la tarea 2. Añade una nueva regla para que la actividad 5 preceda a la actividad 1 y también quita la dependencia que requería que la tarea 2 termine antes de iniciar la tarea 1 en la actividad 8. Hacer lo mismo con la tarea 2 de la actividad 6, asegurándote de que va después de la tarea 1, y haz que la primera tarea de A003 ya no dependa de T002. Ajusta también la actividad 8 para que vaya ahora antes de la actividad 5 y finalmente añade a la actividad 2 una dependencia de que termine la actividad 4 primero.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: direction: #7 A006.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 2 ... depend ... task 1': "haz que la tarea 2 de la actividad 6 dependa de la tarea 1" | #10 A008.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 2 ... antes ... task 1': "tambien quita la dependencia que requeria que la tarea 2 termine antes de iniciar la tarea 1 en la actividad 8" | #11 A008.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 1 ... antes ... task 2': "quita la dependencia que obligaba a la tarea 1 de la misma actividad a terminar antes de empezar la tarea 2" | #12 A003.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 1 ... depend ... task 2': "haz que la primera tarea de a003 ya no dependa de t002" | #15 A002.Activity_Order_Before = A004 (activity 2 before activity 4), text reads 'activity 2 ... depend ... activity 4': "finalmente anade a la actividad 2 una dependencia de que termine la actividad 4 primero"
- Warnings original: direction: #7 A006.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 1 ... antes ... task 2': "quita la regla que obligaba a la tarea 1 de la actividad 6 a terminar antes de la tarea 2" | #8 A006.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 2 ... antes ... task 1': "anade que la tarea 2 de la actividad 6 debe terminar antes de la tarea 1" | #10 A008.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 2 ... antes ... task 1': "anade que la tarea 2 de la actividad 8 debe terminar antes de la tarea 1" | #11 A008.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 1 ... antes ... task 2': "quita la regla que obligaba a la tarea 1 de la actividad 8 a terminar antes de la tarea 2"

## 7. completeness level 15, sample 728

Technical: SET A005.Activity_Order_Enforced = False; DELETE A006.tasks.T002.Order_Before; SET Simulation_period = 3364; DELETE A007.tasks.T002.Order_Enforced; DELETE A005.tasks.T001.Duration; SET A001.tasks.T002.Duration = 64; APPEND A008.Activity_Order_Before = A004; REMOVE_ITEM A005.tasks.T001.Order_Before = T002; APPEND A008.Activity_Order_Before = A007; REMOVE_ITEM A008.tasks.T001.Order_Before = T002; APPEND A001.tasks.T002.Order_Before = T001; REMOVE_ITEM A007.tasks.T001.Order_Before = T002; APPEND A001.Activity_Order_Before = A004; REMOVE_ITEM A001.tasks.T001.Order_Before = T002; APPEND A004.Activity_Order_Before = A001

- Original (gpt-oss:20b): Desactiva la obligación de secuencia de la actividad 5, borra la restricción de que la tarea 2 de la actividad 6 termine antes de otra, cambia el horizonte de simulación a 3364 y elimina la regla que hacía que la tarea 2 de la actividad 7 terminara antes de otra. Borra la duración de la tarea 1 de la actividad 5, pon la duración de la tarea 2 de la actividad 1 a 64 y añade que la actividad 8 debe terminar antes de que empiece la actividad 4. Quita la regla que obligaba a que la tarea 1 de la actividad 5 terminara antes de la tarea 2 y añade que la actividad 8 debe terminar antes de que empiece la actividad 7. Quita la regla que obligaba a que la tarea 1 de la actividad 8 terminara antes de la tarea 2, añade que la tarea 2 de la actividad 1 debe terminar antes de la tarea 1, quita la regla que obligaba a que la tarea 1 de la actividad 7 terminara antes de la tarea 2, añade que la actividad 1 debe terminar antes de que empiece la actividad 4, quita la regla que obligaba a que la tarea 1 de la actividad 1 terminara antes de la tarea 2 y añade que la actividad 4 debe terminar antes de que empiece la actividad 1.
- New (qwen2.5:32b): Oye, necesito que desactives la obligatoriedad de la ruta para la actividad A005 y también borres la restricción de precedencia de la tarea T002 en la actividad A006. Además, ajusta el horizonte de simulación a 3364 y borra la regla que forzaba la secuencia estricta para la tarea T002 en la actividad A007. Luego, quita toda la duración de la tarea T001 en la actividad A005 y ajusta el tiempo operativo de la tarea T002 en la actividad A001 a 64 horas. Ahora, añade que la actividad A008 debe terminar antes de empezar A004 y también quita la regla que obligaba a que la tarea T001 termine antes de empezar T002 en la actividad A005. También añade que la actividad A008 ahora depende de A007, elimina la precedencia entre las tareas T001 y T002 dentro de la actividad A008 y añade que la tarea T002 en la actividad A001 debe terminar antes de empezar T001. Además, quita la regla de precedencia entre las tareas T001 y T002 en la actividad A007. Por último, añade que la actividad A001 ahora también depende de A004 y asegúrate de que A004 debe terminar antes de que empiece A001.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: direction: #9 A008.Activity_Order_Before = A007 (activity 8 before activity 7), text reads 'activity 8 ... depend ... activity 7': "tambien anade que la actividad a008 ahora depende de a007" | #13 A001.Activity_Order_Before = A004 (activity 1 before activity 4), text reads 'activity 1 ... depend ... activity 4': "anade que la actividad a001 ahora tambien depende de a004" | #14 A001.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 2 ... antes ... task 1': "anade que la tarea t002 en la actividad a001 debe terminar antes de empezar t001"
- Warnings original: direction: #11 A001.tasks.T002.Order_Before = T001 (task 2 before task 1), text reads 'task 1 ... antes ... task 2': "quita la regla que obligaba a que la tarea 1 de la actividad 1 terminara antes de la tarea 2" | #13 A001.Activity_Order_Before = A004 (activity 1 before activity 4), text reads 'activity 4 ... antes ... activity 1': "anade que la actividad 4 debe terminar antes de que empiece la actividad 1" | #14 A001.tasks.T001.Order_Before = T002 (task 1 before task 2), text reads 'task 2 ... antes ... task 1': "anade que la tarea 2 de la actividad 1 debe terminar antes de la tarea 1" | #15 A004.Activity_Order_Before = A001 (activity 4 before activity 1), text reads 'activity 1 ... antes ... activity 4': "anade que la actividad 1 debe terminar antes de que empiece la actividad 4"

## 8. complexity level 1, sample 13

Technical: SET A001.T_period = 8974

- Original (gpt-oss:20b): Mira, cambia a 8974 horas la frecuencia de mantenimiento de la actividad A-001.
- New (qwen2.5:32b): Mira, ajusta el periodo entre intervenciones de la actividad A001 para que sea de 8974.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 9. complexity level 1, sample 15

Technical: SET A001.Team members = 10

- Original (gpt-oss:20b): Mira, cambia la dotación a 10 operarios de la actividad 1.
- New (qwen2.5:32b): Cambia la dotación de la actividad A001 para que tenga 10 operarios asignados.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 10. complexity level 1, sample 16

Technical: SET A001.Shift_duration = 8

- Original (gpt-oss:20b): En la actividad A001, cambia la duración del turno a 8 horas.
- New (qwen2.5:32b): Cambia la duración del turno de la actividad A001 a 8 horas.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 11. complexity level 1, sample 41

Technical: DELETE A001.tasks.T001.Duration

- Original (gpt-oss:20b): Borra la duración de la tarea T001 dentro de la actividad A001.
- New (qwen2.5:32b): Borra el dato de la duración para la tarea T001 dentro de la actividad A001.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 12. complexity level 1, sample 43

Technical: SET A001.tasks.T001.Cost_per_hour = 559

- Original (gpt-oss:20b): Mira, cambia el costo por hora a 559 en la tarea 1 de la actividad 1.
- New (qwen2.5:32b): Cambia el costo por hora de la tarea T001 en la actividad A001 a 559.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 13. complexity level 16, sample 752

Technical: SET A010.Team = TeamA

- Original (gpt-oss:20b): Mira, cambia el equipo asignado de la actividad 010 a TeamA.
- New (qwen2.5:32b): Cambia el equipo asignado de la actividad A010 al equipo TeamA.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 14. complexity level 16, sample 754

Technical: REMOVE_ITEM A001.Activity_Order_Before = A002

- Original (gpt-oss:20b): Quita la regla que obliga a que la actividad 1 termine antes de empezar la actividad 2.
- New (qwen2.5:32b): Quita la regla que obliga a que la actividad A001 termine antes de empezar la actividad A002.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 15. complexity level 16, sample 767

Technical: SET Teams = 10

- Original (gpt-oss:20b): Mira, cambia el número de equipos totales del sistema a 10.
- New (qwen2.5:32b): Necesito que cambies el número de equipos totales en la fábrica a 10, esto afecta al sistema global.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 16. complexity level 50, sample 2457

Technical: REMOVE_ITEM A001.tasks.T002.Order_Before = T003

- Original (gpt-oss:20b): En la tarea T002 de la actividad A001, quita la dependencia que obligaba a que termine antes de empezar la tarea T003.
- New (qwen2.5:32b): Quita la dependencia que obligaba a que la tarea T002 de la actividad A001 terminara antes de empezar la tarea T003.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 17. complexity level 50, sample 2459

Technical: APPEND A007.Activity_Order_Before = A004

- Original (gpt-oss:20b): Añade una restricción para que la actividad 7 termine antes de empezar la actividad 4.
- New (qwen2.5:32b): Mira, añade una restricción para que la actividad A007 tenga que terminar antes de empezar la actividad A004.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 18. complexity level 50, sample 2462

Technical: APPEND A003.Activity_Order_Before = A004

- Original (gpt-oss:20b): Añade una restricción para que la actividad 3 termine antes de que empiece la actividad 4.
- New (qwen2.5:32b): Anota por ahí que la actividad 3 ahora también dependa de terminar antes de empezar la actividad 4.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: direction: #1 A003.Activity_Order_Before = A004 (activity 3 before activity 4), text reads 'activity 3 ... depend ... activity 4': "anota por ahi que la actividad 3 ahora tambien dependa de terminar antes de empezar la actividad 4"
- Warnings original: none

## 19. complexity level 50, sample 2465

Technical: SET A006.T_wait = 37

- Original (gpt-oss:20b): Necesito que ajustes el tiempo de espera de la actividad 6 a 37 horas.
- New (qwen2.5:32b): Por favor, ajusta la demora antes de repetir para la actividad A006 a 37 horas.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: none
- Warnings original: none

## 20. complexity level 50, sample 2485

Technical: APPEND A049.Activity_Order_Before = A031

- Original (gpt-oss:20b): Por favor, añade una restricción de que la actividad 49 debe terminar antes de que empiece la actividad 31.
- New (qwen2.5:32b): Haz que ahora la actividad 49 también dependa de terminar antes de empezar la actividad 31.
- Fidelity new: ok
- Fidelity original: ok
- Warnings new: direction: #1 A049.Activity_Order_Before = A031 (activity 49 before activity 31), text reads 'activity 49 ... depend ... activity 31': "haz que ahora la actividad 49 tambien dependa de terminar antes de empezar la actividad 31"
- Warnings original: none
