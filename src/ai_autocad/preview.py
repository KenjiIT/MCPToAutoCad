from html import escape

from .models import DrawingProposal


def render_svg(proposal: DrawingProposal) -> str:
    """Geometric review artifact, not a construction drawing or a CAD screenshot."""
    if not proposal.entities:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 80">'
            '<text x="10" y="40">Resolve missing dimensions before preview.</text></svg>'
        )
    xmin = min(e.origin.x for e in proposal.entities)
    ymin = min(e.origin.y for e in proposal.entities)
    xmax = max(e.origin.x + e.width.value_mm for e in proposal.entities)
    ymax = max(e.origin.y + e.height.value_mm for e in proposal.entities)
    span = max(xmax - xmin, ymax - ymin, 1)
    pad, font = span * 0.12, span * 0.025
    vb = f"{xmin - pad:g} {-ymax - pad:g} {xmax - xmin + 2 * pad:g} {ymax - ymin + 2 * pad:g}"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img">',
        f"<title>{escape(proposal.summary)} — preview, mm, WCS</title>",
        f'<rect x="{xmin - pad:g}" y="{-ymax - pad:g}" width="100%" height="100%" fill="#f7f7f5"/>',
    ]
    for e in proposal.entities:
        x, y, w, h = e.origin.x, e.origin.y, e.width.value_mm, e.height.value_mm
        parts.append(
            f'<rect x="{x:g}" y="{-y - h:g}" width="{w:g}" height="{h:g}" '
            'fill="none" stroke="#234" stroke-width="2" vector-effect="non-scaling-stroke"/>'
        )
        label = escape(f"{e.id}: {w:g} × {h:g} mm [{e.layer}]")
        parts.append(
            f'<text x="{x:g}" y="{-y - h - font:g}" font-size="{font:g}" fill="#234">{label}</text>'
        )
    return "".join(parts) + "</svg>"
