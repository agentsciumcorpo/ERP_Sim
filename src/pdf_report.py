"""Generation du rapport PDF post-partie."""

from __future__ import annotations

import io
from fpdf import FPDF

from src.memory import get_memory_for_download, AGENT_NAMES


def generate_report(state) -> bytes:
    """Genere le rapport PDF complet de la partie."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Page de titre ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 40, "ERPsim - Rapport de Partie", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, f"Cycles joues: {len(state.cycle_results)}", new_x="LMARGIN", new_y="NEXT", align="C")

    if state.cycle_results:
        last = state.cycle_results[-1]
        pdf.cell(0, 10, f"Cash final: {last.metrics.cash_projection.current_cash:,.0f} EUR", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.cell(0, 10, f"Phase finale: {last.metrics.game_phase.phase}", new_x="LMARGIN", new_y="NEXT", align="C")

    # --- Resume KPIs ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Resume des KPIs", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 11)
    if state.cycle_results:
        last = state.cycle_results[-1]
        kpis = [
            f"Rounds joues: {last.round_number}",
            f"Cash final: {last.metrics.cash_projection.current_cash:,.0f} EUR",
            f"Stock central final: {last.metrics.total_central_stock}",
            f"Plateau detecte: {'Oui' if last.metrics.plateau.is_plateau else 'Non'}",
        ]
        for kpi in kpis:
            pdf.cell(0, 8, kpi, new_x="LMARGIN", new_y="NEXT")

    # --- Evolution cash ---
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Evolution du cash", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    for cr in state.cycle_results:
        cash = cr.metrics.cash_projection.current_cash
        phase = cr.metrics.game_phase.phase
        pdf.cell(0, 7, f"Round {cr.round_number}: {cash:,.0f} EUR ({phase})", new_x="LMARGIN", new_y="NEXT")

    # --- Chronologie des decisions ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Chronologie des decisions", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    for cr in state.cycle_results:
        if cr.is_manual_mode:
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 7, f"Round {cr.round_number}: Mode manuel", new_x="LMARGIN", new_y="NEXT")
            continue

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"Round {cr.round_number}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)

        if cr.pricing:
            for rec in cr.pricing.recommendations:
                line = f"  Prix {rec.product}: {rec.current_price} -> {rec.recommended_price} ({rec.confidence})"
                pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")

        if cr.stock:
            pdf.cell(0, 6, f"  Commande: {cr.stock.order_quantity}", new_x="LMARGIN", new_y="NEXT")

        if cr.finance_veto and not cr.finance_veto.approved:
            pdf.set_text_color(200, 0, 0)
            for v in cr.finance_veto.vetoes:
                pdf.cell(0, 6, f"  VETO: {v}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

        pdf.ln(3)

    # --- Memoires agents ---
    for agent in AGENT_NAMES:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, f"Memoire Agent {agent.capitalize()}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 9)

        memory_text = get_memory_for_download(state.memories, agent)
        # fpdf2 ne gere pas bien le markdown, on ecrit le texte brut
        for line in memory_text.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(3)
                continue
            # Gerer les caracteres speciaux
            safe_line = line.encode("latin-1", errors="replace").decode("latin-1")
            pdf.cell(0, 5, safe_line, new_x="LMARGIN", new_y="NEXT")

    # --- Export ---
    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
