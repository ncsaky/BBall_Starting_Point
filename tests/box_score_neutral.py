"""Neutralize the four per-player box-score columns that deliberate engine fixes changed.

Evidence: 6a3c90c (steal tie-break), 114c7c1 (free throws), a1e87ee (fouls), c29f301 (rebounds).
Frozen pre-fix references differ from the current engine only in each player's assists,
personal_fouls, rebounds and steals; everything else must still match exactly.
"""
from copy import deepcopy

BOX_COLUMNS = ("assists", "personal_fouls", "rebounds", "steals")


def box_neutral(plain):
    out = deepcopy(plain)

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "player_lines" and isinstance(value, list):
                    for line in value:
                        if isinstance(line, dict):
                            for column in BOX_COLUMNS:
                                if column in line:
                                    line[column] = None
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(out)
    return out
