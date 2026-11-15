"""How crew members are named on screen."""

ROLE_TITLES = {"ASTRONAUT": "Astronaut", "PILOT": "Pilot", "OPERATOR": "Operator",
               "PHYSICIAN": "Physician"}


def short_name(full_name: str) -> str:
    """``Elena Vargas`` -> ``E. VARGAS`` for the session card."""
    parts = full_name.replace("Dr. ", "").strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}".upper()
    return full_name.upper()


def display_title(row) -> str:
    """Crew position shown under the name (falls back to the system role)."""
    return row["title_en"] or ROLE_TITLES.get(row["role"], row["role"].title())


def physician_name(full_name: str) -> str:
    """``Amara Okafor`` -> ``Dr. A. Okafor``."""
    parts = full_name.replace("Dr. ", "").strip().split()
    return f"Dr. {parts[0][0]}. {parts[-1]}" if len(parts) >= 2 else f"Dr. {full_name}"
