# Décisions techniques

Tous les choix faits pendant le développement (17/11/2026), avec leur justification.

## Nom de la newsletter

Trois propositions :

1. **L'IA sans jargon** ← utilisé par défaut. Dit exactement la promesse (l'IA, expliquée simplement), mémorisable, bon pour le référencement (« IA » + « sans jargon »).
2. **Le Café Data** : convivial, évoque une lecture rapide du lundi matin.
3. **Lundi Neurones** : ludique, rappelle le rendez-vous hebdomadaire.

Modifiable dans `config/settings.yaml` (`newsletter.name`).

## Service d'envoi : Brevo

- **Offre gratuite vérifiée** (novembre 2026, sources : comparatifs 2026 citant la page tarifs officielle) : **300 emails / jour**, jusqu'à 100 000 contacts stockés, API complète, sans carte bancaire. Limites : logo Brevo dans les emails, automatisations limitées (non utilisées ici).
- **Pourquoi Brevo** : seul service gratuit qui réunit API de campagnes, gestion des listes, formulaire d'inscription hébergé avec **double opt-in**, page de désinscription automatique et conformité RGPD (entreprise française, données en UE). Les alternatives gratuites (Mailchimp gratuit, MailerLite, Buttondown) ont soit des plafonds de contacts plus bas, soit une API de campagnes réservée aux offres payantes, soit pas de formulaire double opt-in gratuit.
- **Conséquence** : ~300 abonnés maximum en restant gratuit (un envoi hebdomadaire = 1 email par abonné, sous la limite quotidienne).
- **Envoi** : `POST /v3/emailCampaigns` (liste d'abonnés) puis `POST /v3/emailCampaigns/{id}/sendNow`. Le lien de désinscription utilise la balise Brevo `{{ unsubscribe }}`, remplacée par Brevo pour chaque destinataire.
- **Version texte** : générée (`output/issue.txt`, résumé GitHub), mais l'API de campagnes de Brevo n'accepte que le HTML ; Brevo produit lui-même la partie texte de l'email multipart.

## IA de rédaction

- **Gemini, modèle par défaut `gemini-3.6-flash`** : modèle « Flash » stable, gratuit (page tarifs Google consultée le 17/11/2026). `gemini-2.5-flash` est déprécié (redirigé à partir du 01/12/2026), donc écarté.
- **Modèles Gemini de secours automatiques** : `gemini-flash-latest` (alias Google qui suit le dernier Flash ; s'il n'existe pas, il est simplement sauté) puis `gemini-3.5-flash-lite`. Si un modèle renvoie « introuvable », on passe au suivant sans intervention.
- **Fournisseur de secours** : n'importe quelle API compatible OpenAI, activée seulement si le secret `FALLBACK_API_KEY` existe. Par défaut **Groq** (`https://api.groq.com/openai/v1`, modèle `openai/gpt-oss-120b`, offre gratuite sans carte). Remplaçable par OpenRouter via des variables.
- **Économie de quota** : 2 appels par numéro (sélection + rédaction groupée en un seul JSON). Plafond dur de 6 appels retries compris (`ai.max_calls`).
- **Appels HTTP directs** (sans SDK Google / OpenAI) : moins de dépendances, et les SDK changent souvent ; l'API REST est plus stable dans le temps.
- **Anti-hallucination** : les URL ne sont jamais demandées à l'IA ; chaque texte est rattaché à son article par un identifiant (hash de l'URL) et le code refuse tout identifiant inconnu. Le prompt système interdit d'inventer chiffres et faits, et l'IA ne reçoit que titre + extrait.
- **Mot de la semaine** : choisi par l'IA, refusé s'il figure dans l'historique (nouvel essai avec message d'erreur).
- **Outil à tester** : choisi par le code dans une liste curatée (`config/tools.yaml`, 40 outils avec URL vérifiées), l'IA n'écrit que la description. Ainsi aucun lien inventé. Quand la liste est épuisée : l'IA propose un outil, présenté sans lien.
- **Repli** : si l'appel de sélection échoue, on garde le classement par score (la newsletter part quand même) ; si la rédaction échoue partout, le workflow échoue proprement (pas d'envoi).

## Sources (vérifiées une par une le 17/11/2026)

| Source | Statut | Remarque |
|---|---|---|
| Google AI blog, Google DeepMind, Google Research | ✅ | Research : poids faible (souvent technique) |
| OpenAI | ✅ | |
| Anthropic | ⚠️ pas de flux officiel | Miroir communautaire open source (`Olshansk/rss-feeds` sur GitHub) |
| Meta AI | ⚠️ `ai.meta.com` sans flux (404) | Remplacé par le blog ingénierie Meta, rubrique ML |
| Mistral AI | ✅ | `mistral.ai/rss.xml` |
| Hugging Face | ✅ | |
| MIT Technology Review (IA), The Verge (IA), TechCrunch (IA), Ars Technica (IA), Wired (IA) | ✅ | MIT et The Verge refusent les clients « python-requests » : le User-Agent honnête du bot (`NewsletterIA-Bot/1.0; RSS reader`) est accepté. |
| Numerama | ✅ | Flux général filtré sur les mots-clés IA (le flux de la rubrique IA n'existe plus) |
| Les Numériques (IA), Le Monde Informatique (IA), Siècle Digital (IA) | ✅ | |
| L'Usine Digitale | ❌ HTTP 403 (anti-robots) | Laissé dans la config avec `enabled: false` |
| Ajouts : Journal du Net (IA), 01net, Frandroid, ActuIA | ✅ | Pour compenser, médias français ; 01net et Frandroid filtrés |
| Hacker News (API Algolia) | ✅ | Requêtes par mots-clés, ≥ 150 points, 7 derniers jours |

Si un site refuse notre robot, on respecte son choix : la source est ignorée (et peut être désactivée).

## Sélection

- **Déduplication** : URL normalisée (sans paramètres de tracking, `www`, `/` final), puis regroupement des titres similaires : Jaccard des mots significatifs, chevauchement relatif (titre court inclus dans un long) et ratio de caractères uniquement s'il est très élevé. Les mots trop génériques (« Introducing », « lance », « IA »…) sont ignorés. Seuil 0,4, réglé sur les données réelles de la semaine : par ex. 12 articles FR/EN sur Jensen Huang/Nvidia regroupés en un sujet, sans fusionner des sujets différents. Pas de modèle d'embeddings (dépendance lourde, inutile ici).
- **Score** : `poids_source × (1 + récence + 1,5 × log2(1 + nb_médias) + bonus mots-clés grand public)`.
- **Historique** : `data/history.json` garde les URL et titres publiés (2 000 derniers), les mots et outils déjà présentés. Un article dont le titre ressemble à un sujet déjà publié est écarté.

## Anti double envoi

1. Verrou local `data/locks/<semaine ISO>.json`, écrit immédiatement après l'envoi et commité même si une étape suivante échoue.
2. Vérification côté Brevo : le nom de campagne contient `[AAAA-Www]` ; si une campagne de cette semaine est déjà envoyée/en cours, on n'envoie pas (protège même si le commit du verrou a échoué).
3. `concurrency` GitHub : deux exécutions ne peuvent pas se chevaucher.
4. Les brouillons Brevo orphelins d'un essai raté sont supprimés avant de recréer la campagne.

## Architecture

- Les modules `collect/`, `select/`, `write/`, `render/`, `send/`, `site/` sont dans le package **`newsletter/`** et non à la racine : un dossier `select` à la racine masquerait le module standard `select` de Python, utilisé par `requests`/`urllib3`, et casserait tout appel réseau.
- **Dépendances minimales** (épinglées) : `requests`, `feedparser`, `PyYAML`, `pydantic`, `Jinja2` ; `pytest` et `actionlint-py` pour le développement.
- **Site** : HTML statique généré par Jinja2 dans `docs/`, servi par GitHub Pages en « Deploy from a branch → /docs » (pas de workflow de déploiement supplémentaire). `.nojekyll` désactive Jekyll. Le site est entièrement reconstruit à partir de `data/issues/*.json` (source de vérité).
- **URL du site** : déduite automatiquement de `GITHUB_REPOSITORY` dans Actions (`https://<user>.github.io/<repo>`), surchargeable par `site.url` ou la variable `SITE_URL`.
- **Email** : tableaux HTML, styles inline, 600 px, une colonne ; un seul bloc `<style>` pour la media query mobile (ignoré sans dommage par les clients qui ne le gèrent pas). Aucune image (rien à bloquer, rien à héberger).
- **Formulaire** : iframe du formulaire hébergé Brevo (pas de backend, double opt-in géré par Brevo) + lien de secours.

## GitHub Actions

- Python 3.12 pour la production ; tests sur 3.11 et 3.13.
- Le dry-run manuel est **coché par défaut** (sécurité : un clic par erreur n'envoie rien).
- Les **tests unitaires tournent avant chaque envoi** : un code cassé n'envoie jamais un numéro cassé.
- Cache pip via `actions/setup-python` (`cache: pip`).
- `GEMINI_MODEL`, `FALLBACK_MODEL`, `FALLBACK_BASE_URL`, `SITE_URL` sont des **variables** (non secrètes) ; les clés et l'email expéditeur sont des **secrets**. L'ID de liste est aussi mis en secret, comme demandé.
- **Keepalive** mensuel : commit si inactif depuis 25 jours + réactivation explicite du workflow via `gh workflow enable`.
- Workflow `site.yml` en plus : pour que l'ajout de l'URL du formulaire (ou un changement de nom) mette le site à jour sans attendre le lundi.

## Tests et vérifications réalisés

- 47 tests pytest, sans réseau (un garde-fou fait échouer tout test qui tenterait un accès réseau) : parsing RSS/Atom/Hacker News sur fixtures, résilience aux sources en panne, déduplication, score, historique, validation du JSON de l'IA, retries/backoff/fallback/budget, liens jamais issus de l'IA, rendu HTML/texte, génération du site/RSS/sitemap, verrou anti double envoi (local et Brevo), orchestration complète de `main.py`.
- `actionlint` sur les 4 workflows : OK.
- Dry-run de bout en bout sur les vraies sources : 22 sources OK, 244 articles, 209 sujets distincts.
- **Aucune clé Gemini n'était disponible dans l'environnement de développement** : la génération a été faite avec le fournisseur simulé (`MockProvider`, textes « [Simulation] »). La première génération réelle se fera lors du dry-run de l'étape 11 de SETUP.md.
