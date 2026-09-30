"""Validador anterior (v1): las reglas de input_agent/src/tools.py en el commit e0f1d0a (con el formato
normalizado por ruff) y el cuerpo de ValidatorEngine.validate de input_agent/sub_agents/feedback.py en
ese commit. Solo para tests: todo lo que v1 rechazaba lo tiene que seguir rechazando el validador
actual, salvo los cambios aprobados (límite de 100 actividades y 100 tareas subido a 1000)."""

from input_agent.pn_models import PetriInput


def check_resource_limits(data, activity_keys):
    """Valida que el número de equipos únicos no supere el límite global."""
    max_teams = data.get("Teams", float("inf"))
    used_teams = set()

    for act_id in activity_keys:
        activity = data[act_id]
        if "Team" in activity:
            used_teams.add(activity["Team"])

    if len(used_teams) > max_teams:
        return [f"Resource Error: Max teams limit exceeded ({len(used_teams)}/{max_teams})."]
    return []


def check_sanity_rules(batch_object):
    """Valida tipos de datos y valores lógicos en las instrucciones del batch."""
    issues = []
    numeric_fields = ["T_period", "T_wait", "Start_disp", "Shift_duration", "Duration"]

    for instr in batch_object.instructions:
        val = instr.value
        if not isinstance(val, dict):
            continue

        for field in numeric_fields:
            num_val = val.get(field)
            if num_val is not None and (not isinstance(num_val, (int, float)) or num_val < 0):
                issues.append(
                    f"Sanity Error: {field} must be a non-negative number at {instr.path}."
                )

        members = val.get("Team members")
        if members is not None and (not isinstance(members, int) or members < 0):
            issues.append(
                f"Sanity Error: Team members must be a non-negative integer at {instr.path}."
            )
    return issues


def check_topology_references(data, activity_keys):
    """Valida que todas las dependencias (activityCode y taskCode) existan."""
    issues = []
    existing_activity_ids = set(activity_keys)

    for act_id in activity_keys:
        activity = data[act_id]

        # 1. Dependencias de Actividad
        if activity.get("activityDependency") is True:
            for dep_id in activity.get("activityCode", []):
                if dep_id not in existing_activity_ids:
                    issues.append(
                        f"Topology Error: Activity {act_id} depends on non-existent Activity '{dep_id}'."
                    )

        # 2. Dependencias de Tareas
        tasks = activity.get("tasks", {})
        existing_task_ids = set(tasks.keys())

        for t_id, t_data in tasks.items():
            if isinstance(t_data, dict) and t_data.get("taskDependency") is True:
                for dep_task_id in t_data.get("taskCode", []):
                    if dep_task_id not in existing_task_ids:
                        issues.append(
                            f"Topology Error: Task {t_id} (in {act_id}) depends on non-existent Task '{dep_task_id}'."
                        )
    return issues


def deterministic_validator(batch_object, engine):
    """Orquestador de validaciones deterministas."""
    new_data = engine.data
    global_keys = {"runId", "Teams", "Simulation_period"}
    activity_keys = [k for k in new_data.keys() if k not in global_keys]

    # Ejecutar todos los checks
    issues = []
    issues.extend(check_resource_limits(new_data, activity_keys))
    issues.extend(check_sanity_rules(batch_object))
    issues.extend(check_topology_references(new_data, activity_keys))

    return (len(issues) == 0, issues)


def legacy_validate(batch, engine):
    """ValidatorEngine.validate en e0f1d0a."""
    is_valid, issues = deterministic_validator(batch, engine)
    copy_data = engine.data.copy()
    if is_valid:
        try:
            PetriInput.model_validate(copy_data)
            return True, []
        except Exception as e:
            return False, [f"Schema Error: {e!s}"]
    return False, issues
