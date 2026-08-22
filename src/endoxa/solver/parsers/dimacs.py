from pathlib import Path


def parse_dimacs(file_path: str) -> tuple[int, list[list[int]]]:
    num_vars = 0
    clauses = []

    with Path(file_path).open(encoding="utf-8") as f:
        tokens = []
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith(("c", "%", "0\n")):
                continue
            if stripped.startswith("p cnf"):
                parts = stripped.split()
                num_vars = int(parts[2])
                continue

            tokens.extend(stripped.split())

    current_clause = []
    for token in tokens:
        lit = int(token)
        if lit == 0:
            if current_clause:
                clauses.append(current_clause)
                current_clause = []
        else:
            current_clause.append(lit)

    if current_clause:
        clauses.append(current_clause)

    return num_vars, clauses
