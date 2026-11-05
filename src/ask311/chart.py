"""Choose a sensible chart from the shape of a result and save it as a PNG."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, ACCENT, MUTED = "#1f2933", "#2563eb", "#9aa5b1"


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def pick_chart(columns, rows) -> str:
    """'number', 'line', 'bar', or 'table'."""
    if not rows:
        return "table"
    if len(rows) == 1 and len(columns) == 1 and _is_num(rows[0][0]):
        return "number"
    time_cols = [i for i, c in enumerate(columns) if any(k in str(c).lower() for k in ("month", "date", "week", "day"))]
    if len(columns) >= 2 and time_cols and len(rows) > 3 and all(_is_num(r[-1]) for r in rows):
        return "line"
    if len(columns) == 2 and all(_is_num(r[1]) for r in rows):
        first = str(columns[0]).lower()
        if any(k in first for k in ("month", "date", "week", "day", "year", "hour")) and len(rows) > 3:
            return "line"
        if len(rows) <= 30:
            return "bar"
    return "table"


def save_chart(columns, rows, path, title=""):
    kind = pick_chart(columns, rows)
    if kind in ("table", "number"):
        return kind
    x = 0
    if kind == "line":
        x = next(i for k in ("month", "date", "week", "day", "year", "hour")
                 for i, c in enumerate(columns) if k in str(c).lower())
    labels = [str(r[x])[:32] for r in rows]
    values = [r[-1] for r in rows]
    fig, ax = plt.subplots(figsize=(8, max(3, 0.32 * len(rows) + 1)) if kind == "bar" else (8, 3.6), dpi=150)
    if kind == "bar":
        ax.barh(labels[::-1], values[::-1], color=ACCENT)
        ax.set_xlabel(columns[-1], color=MUTED)
    else:
        ax.plot(labels, values, color=ACCENT, linewidth=2)
        ax.set_ylabel(columns[-1], color=MUTED)
        step = max(1, len(labels) // 8)
        ax.set_xticks(range(0, len(labels), step), labels[::step], rotation=0, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK, labelsize=8)
    if title:
        ax.set_title(title, loc="left", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return kind
