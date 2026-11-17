"""Faux fournisseur IA, utilisé uniquement en dry-run quand aucune clé n'est disponible (et dans les tests).

Il lit les identifiants présents dans le prompt et renvoie un JSON plausible, ce qui permet de tester
toute la chaîne (validation, association des liens, rendu) sans réseau ni quota.
"""
from __future__ import annotations

import json
import re

MOCK_WORDS = [
    ("Modèle de langage (LLM)", "C'est le moteur des assistants comme ChatGPT"),
    ("Hallucination", "C'est quand une IA invente une réponse avec aplomb"),
    ("Données d'entraînement", "Ce sont les textes et images dont une IA s'est nourrie"),
    ("Agent IA", "C'est une IA qui ne se contente pas de répondre mais agit"),
]

_LOREM = (
    "Ceci est un texte de simulation généré sans IA, pour vérifier que la mise en page fonctionne. "
    "Dans un vrai numéro, ce paragraphe résume l'article en français simple, sans jargon, "
    "avec une analogie du quotidien pour que tout le monde comprenne de quoi il retourne. "
)


class MockProvider:
    label = "mock"

    def complete(self, system: str, user: str) -> str:
        titles = dict(re.findall(r"- id: (\w+)\n\s+titre: (.*)", user))
        if '"top": "<id>"' in user:  # prompt de sélection
            ids = list(titles)
            return json.dumps({"top": ids[0], "briefs": ids[1:6]})

        top_id = re.search(r"id « (\w+) »", user).group(1)
        brief_ids = json.loads(re.search(r"dans cet ordre : (\[.*?\])", user).group(1))
        banned = json.loads(re.search(r"Termes INTERDITS[^:]*: (\[.*?\])", user).group(1))
        banned_norm = {b.lower() for b in banned}
        term, hook = next(((t, h) for t, h in MOCK_WORDS if t.lower() not in banned_norm),
                          (f"Terme de test n°{len(banned) + 1}", "Un terme de démonstration"))
        tool = re.search(r"Présente l'outil « (.*?) »", user)
        tool_name = tool.group(1) if tool else "Outil de démonstration"
        return json.dumps(
            {
                "title": "[Simulation] L'IA de la semaine, en clair",
                "intro": "Ce numéro a été généré en mode simulation, sans appel à une IA. "
                "Il sert à vérifier la collecte, la sélection et la mise en page.",
                "top_story": {
                    "id": top_id,
                    "headline": f"[Simulation] {titles.get(top_id, 'Info de la semaine')}",
                    "summary": (_LOREM * 3).strip(),
                    "why_it_matters": "Pourquoi c'est important : en vrai, cette partie explique "
                    "l'impact concret de l'info sur votre quotidien, en deux ou trois phrases.",
                },
                "briefs": [
                    {"id": b, "headline": f"[Simulation] {titles.get(b, 'Brève')}", "summary": _LOREM.strip()}
                    for b in brief_ids
                ],
                "word_of_the_week": {
                    "term": term,
                    "explanation": f"{hook}. " + _LOREM.strip(),
                },
                "tool_of_the_week": {
                    "name": tool_name,
                    "description": "Description de simulation : à quoi sert l'outil, une idée pour "
                    "l'essayer ce soir, et sa principale limite.",
                },
                "conclusion": "Fin de la simulation : tout fonctionne. À lundi prochain !",
            },
            ensure_ascii=False,
        )
