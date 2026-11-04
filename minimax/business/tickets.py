"""Small ticket query service. Input rows belong to the caller."""


def list_tickets(rows, owner=None, status=None):
    """Return matching tickets sorted by id."""
    normalized_status = None
    if status is not None:
        if not isinstance(status, str):
            raise ValueError("status must be 'open' or 'closed'")
        normalized_status = status.strip().lower()
        if normalized_status not in ("open", "closed"):
            raise ValueError("status must be 'open' or 'closed'")

    selected = [
        row
        for row in rows
        if (owner is None or row["owner"] == owner)
        and (normalized_status is None or row["status"] == normalized_status)
    ]
    return [dict(row) for row in sorted(selected, key=lambda row: row["id"])]
