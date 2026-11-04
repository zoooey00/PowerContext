"""Small ticket query service. Input rows belong to the caller."""


def list_tickets(rows, owner=None, status=None):
    """Return tickets sorted by id, optionally restricted to an owner."""
    selected = [row for row in rows if owner is None or row['owner'] == owner]
    return [dict(row) for row in sorted(selected, key=lambda row: row['id'])]
