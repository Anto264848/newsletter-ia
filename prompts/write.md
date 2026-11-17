Rédige le numéro ${issue_number} de la newsletter (semaine ${week_label}).

## Articles retenus
L'info de la semaine (id « ${top_id} ») et les brèves sont décrites ci-dessous. N'utilise QUE ces informations.

${articles}

## Ce que tu dois produire
1. « title » : un titre de numéro accrocheur (8 à 12 mots maximum), en lien avec l'info de la semaine.
2. « intro » : un chapeau de exactement 2 phrases qui donne envie de lire.
3. « top_story » : l'info de la semaine.
   - « id » : "${top_id}"
   - « headline » : un titre clair en français (max 14 mots)
   - « summary » : 120 à 180 mots, vulgarisés, sans jargon
   - « why_it_matters » : 2 ou 3 phrases « Pourquoi c'est important pour vous », concrètes, liées à la vie quotidienne
4. « briefs » : une entrée pour CHACUN de ces identifiants, dans cet ordre : ${brief_ids}
   - « id » : l'identifiant
   - « headline » : un titre clair en français (max 12 mots)
   - « summary » : 40 à 70 mots, vulgarisés
5. « word_of_the_week » : un terme data ou IA utile pour comprendre l'actualité (idéalement lié à un article du numéro).
   - « term » : le terme
   - « explanation » : 50 à 90 mots, avec une analogie du quotidien
   - Termes INTERDITS (déjà expliqués dans des numéros précédents) : ${banned_words}
6. « tool_of_the_week » : ${tool_instruction}
   - « name » : le nom de l'outil
   - « description » : 2 ou 3 phrases : à quoi il sert, une idée concrète pour l'essayer, et sa limite principale.
7. « conclusion » : 1 ou 2 phrases de conclusion chaleureuses, éventuellement avec une pointe d'humour.

Rappels : aucune URL, aucun chiffre ou fait inventé, reformulation totale, français.

Réponds UNIQUEMENT avec ce JSON :
{
  "title": "...",
  "intro": "...",
  "top_story": {"id": "${top_id}", "headline": "...", "summary": "...", "why_it_matters": "..."},
  "briefs": [{"id": "...", "headline": "...", "summary": "..."}],
  "word_of_the_week": {"term": "...", "explanation": "..."},
  "tool_of_the_week": {"name": "...", "description": "..."},
  "conclusion": "..."
}
