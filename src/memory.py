"""Systeme de memoire cumulative pour les agents IA."""

from __future__ import annotations

import datetime


AGENT_NAMES = ["prix", "stock", "finance"]


def init_memory() -> dict[str, str]:
    """Initialise les fichiers memoire vides pour chaque agent."""
    memories = {}
    for agent in AGENT_NAMES:
        memories[agent] = (
            f"# Memoire Agent {agent.capitalize()}\n\n"
            f"*Initialise le {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
            f"---\n\n"
        )
    return memories


def append_memory(
    memories: dict[str, str],
    agent: str,
    round_number: int,
    decision: str,
    reasoning: str,
    result: str | None = None,
) -> dict[str, str]:
    """Ajoute une entree dans la memoire d'un agent."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    entry = (
        f"## Round {round_number} — {timestamp}\n\n"
        f"**Decision:** {decision}\n\n"
        f"**Raisonnement:** {reasoning}\n\n"
    )
    if result:
        entry += f"**Resultat observe:** {result}\n\n"
    entry += "---\n\n"

    memories[agent] = memories.get(agent, "") + entry
    return memories


def get_memory_context(memories: dict[str, str], agent: str, max_chars: int = 3000) -> str:
    """Retourne le contexte memoire pour un agent, tronque si necessaire."""
    memory = memories.get(agent, "")
    if len(memory) > max_chars:
        # Garder le debut (header) et la fin (decisions recentes)
        header_end = memory.find("---") + 4
        header = memory[:header_end]
        recent = memory[-(max_chars - len(header)):]
        return header + "\n[...memoire tronquee...]\n\n" + recent
    return memory


def get_memory_for_download(memories: dict[str, str], agent: str) -> str:
    """Retourne le contenu complet pour telechargement."""
    return memories.get(agent, f"# Memoire Agent {agent.capitalize()}\n\nAucune donnee.")
