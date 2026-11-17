# Mission : newsletter hebdomadaire « Actu Data & IA vulgarisée », 100 % automatisée et 100 % gratuite

Tu travailles en **totale autonomie**. Ne me pose pas de questions pendant le développement : quand un choix se présente, prends la décision la plus simple, robuste et gratuite, puis note-la dans `DECISIONS.md`. Ne t'arrête qu'une fois que tout est terminé et testé.

## 1. Objectif

Créer un dépôt GitHub qui, **chaque lundi matin, sans aucune intervention humaine** :
1. collecte les actualités data et IA de la semaine écoulée ;
2. sélectionne les plus importantes ;
3. les fait résumer et vulgariser en français par une IA gratuite ;
4. génère un email HTML propre ;
5. l'envoie à tous les abonnés ;
6. publie le numéro dans les archives d'un site GitHub Pages, qui contient aussi le formulaire d'inscription.

Le projet doit tourner **pendant des années, sans coût**, et sans que j'aie besoin d'intervenir. Après la configuration initiale, je ne dois plus rien faire.

## 2. Contraintes non négociables

- **Coût zéro** : uniquement des offres gratuites. Pas de serveur, pas de carte bancaire.
- **Hébergement** : GitHub Actions (cron) pour l'exécution, GitHub Pages pour le site.
- **IA de rédaction** : API Google Gemini, offre gratuite (j'en ai déjà une clé pour un autre projet). Le modèle doit pouvoir se changer via une variable d'environnement `GEMINI_MODEL`, car les modèles gratuits changent avec le temps. Choisis un modèle « flash » gratuit actuel comme valeur par défaut. Prévois un **fallback** vers un second fournisseur gratuit (par exemple Groq ou OpenRouter avec des modèles gratuits), activé seulement si sa clé est présente en secret.
- **Langage** : Python 3.11+, peu de dépendances, versions épinglées dans `requirements.txt`.
- **Aucune intervention** pendant le fonctionnement normal : pas de validation manuelle avant l'envoi.
- **Pas d'API payante** de Claude ou d'OpenAI.

## 3. Public et ton

- **Public** : des personnes curieuses mais **non techniques** (étudiants, salariés, parents) qui veulent comprendre ce qui se passe dans l'IA et la data sans jargon.
- **Ton** : clair, accessible, un peu d'humour léger, jamais condescendant. Chaque terme technique est expliqué en une phrase simple ou remplacé par une analogie.
- **Langue** : français, même si la source est en anglais.
- **Temps de lecture** : 4 à 6 minutes.

## 4. Structure de chaque numéro

1. **Titre du numéro** accrocheur et un chapeau de 2 phrases.
2. **L'info de la semaine** : la plus importante, en 120 à 180 mots, avec « Pourquoi c'est important pour vous ».
3. **En bref** : 4 à 6 autres actus, chacune en 40 à 70 mots, avec un lien vers la source.
4. **Le mot de la semaine** : un terme data ou IA expliqué simplement (sans répétition d'un numéro à l'autre : garde un historique).
5. **L'outil à tester** : un outil IA gratuit et grand public, en 2 ou 3 phrases (sans répétition non plus).
6. **Conclusion** courte, puis un footer avec le lien de désinscription, le lien vers les archives et une phrase indiquant que la newsletter est rédigée avec l'aide d'une IA.

## 5. Collecte des sources

- Utilise des **flux RSS et des API publiques gratuites et sans authentification**. Propositions à **vérifier une par une** (garde seulement celles qui fonctionnent réellement) : blogs officiels de Google AI, OpenAI, Anthropic, Meta AI, Mistral AI et Hugging Face ; MIT Technology Review (rubrique IA) ; The Verge (IA) ; TechCrunch (IA) ; Ars Technica ; médias français (Numerama, Les Numériques, Usine Digitale, Le Monde Informatique, Siècle Digital) ; Hacker News via l'API Algolia filtrée sur des mots-clés IA et data avec un score minimum.
- La liste des sources doit se trouver dans un fichier de config éditable (`config/sources.yaml`).
- Ne garde que les articles des **7 derniers jours**.
- **Une source en panne ne doit jamais faire planter l'ensemble** : log, puis on continue.
- Ajoute un User-Agent correct, des timeouts et des retries.

## 6. Sélection

- **Déduplication** : même URL, ou titres très proches (même sujet couvert par plusieurs médias). Utilise une similarité simple, sans modèle lourd.
- **Historique** : stocke dans `data/history.json` les URL et sujets déjà publiés, pour ne jamais réutiliser une info d'un numéro précédent.
- **Score** : récence, nombre de sources qui couvrent le sujet, poids de la source, mots-clés grand public. L'IA peut ensuite affiner le classement parmi les 20 à 30 meilleurs candidats, mais en un seul appel.
- **Économie de quota** : un numéro complet doit nécessiter **au maximum 3 à 5 appels à l'IA**. Regroupe les tâches dans un seul prompt qui renvoie du JSON.

## 7. Rédaction par l'IA : fiabilité avant tout

- L'IA renvoie du **JSON strict** validé par un schéma (pydantic ou jsonschema). Si le JSON est invalide, réessaie avec backoff, puis bascule sur le fallback.
- **Aucune hallucination de liens** : les URL viennent uniquement des données collectées, jamais de l'IA. Le code associe chaque résumé à son URL d'origine par identifiant.
- L'IA ne travaille **qu'à partir du titre et de l'extrait fournis** et ne doit pas inventer de chiffres ou de faits. Écris-le explicitement dans le prompt système.
- **Pas de recopie** des articles : de vrais résumés reformulés, avec un lien vers la source.
- Gère les erreurs 429 (quota) avec un backoff exponentiel.
- Stocke les prompts dans des fichiers séparés (`prompts/*.md`) pour pouvoir les ajuster facilement.

## 8. Envoi des emails

- Choisis le service d'envoi **gratuit** le plus adapté. Je te suggère **Brevo**, qui propose une offre gratuite avec une API, gère les listes de contacts, la désinscription automatique et les formulaires d'inscription avec double opt-in. Vérifie quand même les limites actuelles de l'offre gratuite et justifie ton choix dans `DECISIONS.md`.
- Envoi via l'API : création d'une campagne vers la liste d'abonnés, puis envoi immédiat.
- Le HTML de l'email doit fonctionner dans tous les clients mail : CSS inline, mise en page responsive en une colonne, largeur maximale de 600 px, sans JavaScript. Prévois aussi une version texte.
- **Conformité RGPD** : double opt-in, lien de désinscription dans chaque email, aucune donnée d'abonné dans le dépôt GitHub.
- **Garde-fous** : n'envoie rien si moins de 4 actus valides ont été trouvées (le workflow échoue proprement et GitHub m'envoie automatiquement un email). N'envoie **jamais deux fois** le même numéro : verrou basé sur la date ISO de la semaine, enregistré dans `data/`.

## 9. Site GitHub Pages

- Une landing page simple et soignée : nom de la newsletter, promesse en une phrase, exemple de contenu, et formulaire d'inscription (le formulaire intégrable du service d'envoi, sans backend).
- Une page `/archives` qui liste tous les numéros, et une page HTML par numéro. C'est utile pour le référencement et pour convaincre de s'inscrire.
- Un flux RSS des numéros.
- Un site statique généré par le script Python, sans framework lourd.
- Balises meta, Open Graph et `sitemap.xml` pour le SEO.
- **Propose 3 noms** de newsletter dans `DECISIONS.md`, puis utilise le premier par défaut. Il doit pouvoir se changer dans `config/settings.yaml`.

## 10. GitHub Actions

- `newsletter.yml` : un cron le lundi à 06:00 UTC, plus `workflow_dispatch` pour lancer à la main avec une option `dry_run` (qui génère le numéro sans l'envoyer).
- À chaque exécution, le workflow commit `data/` (historique, verrous) et les pages du site.
- **Important** : GitHub désactive les workflows planifiés après 60 jours sans activité sur le dépôt. Le commit hebdomadaire suffit normalement à garder le dépôt actif, mais ajoute un mécanisme de sécurité (par exemple un commit de « keepalive » mensuel si rien n'a été commité) et explique-le dans le README.
- Mets en cache les dépendances pip.
- Les secrets sont lus depuis les GitHub Secrets : `GEMINI_API_KEY`, la clé du service d'envoi, l'ID de la liste, l'email expéditeur. Ajoute éventuellement une clé de fallback.
- Ajoute un second workflow de **tests** sur chaque push.

## 11. Qualité du code

- Une architecture claire : `collect/`, `select/`, `write/`, `render/`, `send/`, `site/`, plus `main.py` comme orchestrateur.
- Des logs lisibles dans GitHub Actions.
- Des **tests pytest** : parsing des sources (avec des fixtures, sans réseau), déduplication, validation du JSON de l'IA, rendu HTML, verrou anti double envoi. Les appels réseau sont mockés.
- Une commande locale : `python main.py --dry-run` génère le numéro dans `output/` et l'aperçu HTML, sans rien envoyer.
- Lance le dry-run toi-même avant de finir. Si une clé Gemini est disponible dans l'environnement, fais une génération réelle. Sinon, utilise un mock et signale-le.

## 12. Documentation finale

- **README.md** en français : ce que fait le projet, le schéma du pipeline, comment modifier les sources, le ton ou le nom, et comment changer de modèle IA si le modèle gratuit disparaît.
- **SETUP.md** : une checklist **pas à pas, pour un débutant**, de la configuration initiale unique. Créer le compte du service d'envoi, vérifier l'adresse expéditeur, créer la liste et le formulaire double opt-in, récupérer les clés API, ajouter les GitHub Secrets, activer GitHub Pages, lancer un premier test en dry-run, puis un vrai envoi vers ma seule adresse.
- **DECISIONS.md** : tous les choix que tu as faits et pourquoi.

## 13. Définition de « terminé »

- [ ] Tous les tests passent.
- [ ] Le dry-run produit un numéro HTML complet et lisible dans `output/`.
- [ ] Les workflows GitHub Actions sont valides (syntaxe vérifiée).
- [ ] Le site statique se génère correctement.
- [ ] Aucun secret ni aucune donnée personnelle dans le code.
- [ ] README, SETUP et DECISIONS sont rédigés.
- [ ] À la fin, tu m'affiches un **résumé court** : ce qui a été fait, et la liste exacte des actions manuelles que je dois faire une seule fois (celles de SETUP.md).

Commence maintenant.
