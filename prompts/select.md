Voici ${count} articles candidats collectés cette semaine (titre, source, date, extrait, et nombre de médias qui couvrent le même sujet).

Choisis pour la newsletter :
- « top » : l'identifiant de l'info LA plus importante de la semaine pour le grand public (impact concret sur la vie des gens, ampleur, nouveauté).
- « briefs » : entre ${briefs_min} et ${briefs_max} autres identifiants, classés du plus au moins intéressant, sur des sujets VARIÉS (évite deux articles sur le même sujet ou la même entreprise si possible).

Critères : intérêt pour un public non technique, importance réelle, diversité des sujets. Écarte les articles trop techniques (benchmarks de recherche, détails d'ingénierie), purement promotionnels ou de simples tests de produits.

Réponds UNIQUEMENT avec ce JSON :
{"top": "<id>", "briefs": ["<id>", "<id>", "..."]}

Candidats :
${candidates}
