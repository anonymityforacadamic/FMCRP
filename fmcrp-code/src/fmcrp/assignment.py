from __future__ import annotations


def hungarian(costs: list[list[float]]) -> list[int]:
    """Minimum-cost row assignment for a rectangular matrix (rows >= columns)."""
    if not costs:
        return []
    rows, columns = len(costs), len(costs[0])
    if rows < columns or any(len(row) != columns for row in costs):
        raise ValueError("cost matrix must be rectangular with rows >= columns")
    u, v = [0.0] * (rows + 1), [0.0] * (columns + 1)
    p, way = [0] * (columns + 1), [0] * (columns + 1)
    for i in range(1, rows + 1):
        p[0], j0 = i, 0
        minv, used = [float("inf")] * (columns + 1), [False] * (columns + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], float("inf"), 0
            for j in range(1, columns + 1):
                if not used[j]:
                    current = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if current < minv[j]:
                        minv[j], way[j] = current, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(columns + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    result = [-1] * columns
    for j in range(1, columns + 1):
        result[j - 1] = p[j] - 1
    return result
