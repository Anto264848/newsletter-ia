# Configuration initiale (à faire une seule fois)

Comptez 30 à 45 minutes. Aucune carte bancaire n'est demandée. Cochez au fur et à mesure.

Vous aurez besoin de noter 4 informations secrètes (gardez-les dans un endroit sûr, jamais dans le code) :

| Nom | Exemple | Où le trouver |
|---|---|---|
| `GEMINI_API_KEY` | `AIza...` | Étape 1 |
| `BREVO_API_KEY` | `xkeysib-...` | Étape 6 |
| `BREVO_LIST_ID` | `3` | Étape 4 |
| `BREVO_SENDER_EMAIL` | `bonjour@mondomaine.fr` | Étape 3 |

---

## Étape 1 — Clé Google Gemini (vous l'avez déjà)

- [ ] Allez sur <https://aistudio.google.com/apikey>, connectez-vous et copiez votre clé existante (ou cliquez sur **Create API key**).
- [ ] Vérifiez qu'elle est sur l'offre gratuite (pas de facturation activée sur le projet Google Cloud associé) : c'est ce qui garantit le coût zéro.

## Étape 2 — Créer le compte Brevo

- [ ] Allez sur <https://www.brevo.com/fr/> → **S'inscrire gratuitement**.
- [ ] Remplissez le profil (nom, adresse postale : elle est légalement obligatoire et apparaîtra en bas des emails). Choisissez l'offre **Free**.
- [ ] Brevo peut demander une validation du compte (quelques questions sur votre usage) : répondez « newsletter d'information, inscrits via formulaire double opt-in ».

## Étape 3 — Vérifier l'adresse expéditeur

- [ ] Dans Brevo : menu en haut à droite (votre nom) → **Expéditeurs, domaines et IP dédiées** → onglet **Expéditeurs** → **Ajouter un expéditeur**.
- [ ] Nom : `L'IA sans jargon` (ou le nom choisi) ; email : votre adresse expéditeur. Validez le code reçu par email.
- [ ] **Important pour la délivrabilité** : avec une adresse Gmail / Outlook / Yahoo, Brevo doit remplacer l'expéditeur par une adresse technique, et vos emails risquent davantage les spams. Si vous avez un nom de domaine (même à 1 €/an), ajoutez-le dans l'onglet **Domaines** et suivez l'assistant (DKIM / DMARC). C'est facultatif mais recommandé.
- [ ] Notez l'adresse : c'est `BREVO_SENDER_EMAIL`.

## Étape 4 — Créer la liste d'abonnés

- [ ] **Contacts** → **Listes** → **Créer une liste** → nom : `Abonnés newsletter`.
- [ ] Ouvrez la liste : son **ID** est affiché (colonne « ID » ou dans l'adresse de la page, ex. `.../lists/3`). Notez-le : c'est `BREVO_LIST_ID` (un nombre).

## Étape 5 — Créer le formulaire d'inscription (double opt-in)

- [ ] **Contacts** → **Formulaires** → **Créer un formulaire d'inscription**.
- [ ] Nom : `Inscription site`. Champs : gardez **Email** (évitez de demander plus : moins de données = plus simple pour le RGPD).
- [ ] Ajoutez la case de consentement RGPD proposée par Brevo (texte du type « J'accepte de recevoir la newsletter et je peux me désinscrire à tout moment »).
- [ ] Étape **Paramètres** → **Liste** : choisissez `Abonnés newsletter`.
- [ ] Étape **Confirmation** : choisissez **Double confirmation (double opt-in)**. Choisissez le modèle d'email de confirmation par défaut et une page de redirection (vous pouvez mettre l'URL de votre site, cf. étape 9).
- [ ] Enregistrez, puis **Partager** : copiez le **lien du formulaire** (adresse de la forme `https://xxxx.sibforms.com/serve/MUIFA...`).
- [ ] Dans le dépôt, ouvrez `config/settings.yaml` et collez ce lien dans `site.subscribe_form_url` (entre guillemets). Cette URL est publique, ce n'est pas un secret.

## Étape 6 — Clé API Brevo (et autoriser GitHub)

- [ ] Menu en haut à droite → **SMTP & API** → onglet **Clés API** → **Générer une nouvelle clé API**. Nom : `github-actions`. Copiez-la immédiatement (elle ne sera plus affichée) : c'est `BREVO_API_KEY`.
- [ ] Menu en haut à droite → **Sécurité** → **IP autorisées** : les serveurs de GitHub changent d'adresse IP à chaque exécution. Si le blocage des IP inconnues est actif, **désactivez-le** (sinon chaque envoi sera refusé avec une erreur « unrecognised IP address »).

## Étape 7 — (Facultatif) Clé de secours Groq

Utile si Gemini est en panne ou change ses conditions. Gratuit, sans carte.

- [ ] Allez sur <https://console.groq.com/keys>, créez un compte, **Create API Key**, copiez-la : ce sera `FALLBACK_API_KEY`.

## Étape 8 — Créer le dépôt GitHub et y mettre le code

- [ ] Sur <https://github.com/new> : nom `newsletter-ia` (par exemple), visibilité **Public** (nécessaire pour GitHub Pages gratuit et des minutes Actions illimitées ; aucun secret ni donnée d'abonné n'est dans le code). Ne cochez rien d'autre → **Create repository**.
- [ ] Dans un terminal, dans le dossier du projet :
  ```bash
  git remote add origin https://github.com/VOTRE-PSEUDO/newsletter-ia.git
  git branch -M main
  git push -u origin main
  ```
  (Avec GitHub CLI : `gh repo create newsletter-ia --public --source . --push`.)

## Étape 9 — Ajouter les secrets GitHub

- [ ] Sur la page du dépôt : **Settings** → **Secrets and variables** → **Actions** → onglet **Secrets** → **New repository secret**. Créez un par un :
  - `GEMINI_API_KEY`
  - `BREVO_API_KEY`
  - `BREVO_LIST_ID`
  - `BREVO_SENDER_EMAIL`
  - `FALLBACK_API_KEY` (seulement si étape 7)
- [ ] (Facultatif) onglet **Variables** : `GEMINI_MODEL` pour changer de modèle sans toucher au code ; `SITE_URL` si vous utilisez un nom de domaine personnalisé.
- [ ] **Settings** → **Actions** → **General** → section *Workflow permissions* : sélectionnez **Read and write permissions** → **Save** (le workflow doit pouvoir commiter l'historique et le site).

## Étape 10 — Activer GitHub Pages

- [ ] **Settings** → **Pages** → *Build and deployment* → Source : **Deploy from a branch** → Branch : **main**, dossier **/docs** → **Save**.
- [ ] Après 1 à 2 minutes, le site est en ligne à `https://VOTRE-PSEUDO.github.io/newsletter-ia/`.
- [ ] Faites une petite modification dans `config/settings.yaml` (par ex. l'URL du formulaire de l'étape 5) et poussez-la : le workflow **Reconstruire le site** régénère le site avec la bonne URL, le sitemap et le formulaire.
- [ ] (Recommandé) Dans Brevo, mettez l'URL du site comme page de redirection après confirmation de l'inscription (étape 5).

## Étape 11 — Premier test en dry-run (rien n'est envoyé)

- [ ] Onglet **Actions** du dépôt → si GitHub le demande, cliquez **I understand my workflows, go ahead and enable them**.
- [ ] Workflow **Newsletter hebdomadaire** → **Run workflow** → laissez **Dry-run** coché → **Run workflow**.
- [ ] Ouvrez l'exécution (2 à 4 minutes) : le résumé affiche le numéro rédigé par Gemini. En bas, section **Artifacts**, téléchargez `apercu-numero-…` et ouvrez `issue.html` dans votre navigateur.
- [ ] Si quelque chose ne va pas (ton, sources…), ajustez `prompts/` ou `config/` et relancez.

## Étape 12 — Premier vrai envoi, vers votre seule adresse

- [ ] Ouvrez votre site, inscrivez-vous avec **votre** adresse via le formulaire, et cliquez sur le lien de confirmation reçu par email (cela teste aussi le double opt-in).
- [ ] Dans Brevo → **Contacts** → liste `Abonnés newsletter` : vérifiez que **vous êtes le seul contact**.
- [ ] GitHub → **Actions** → **Newsletter hebdomadaire** → **Run workflow** → **décochez Dry-run** → **Run workflow**.
- [ ] Vérifiez votre boîte mail (et les spams). Vérifiez aussi que le lien « Se désinscrire » fonctionne (vous pourrez vous réinscrire ensuite).
- [ ] Vérifiez que le numéro apparaît dans les archives du site.

> Ce test compte comme le numéro de la semaine : le lundi suivant, le numéro suivant partira automatiquement. Pour renvoyer dans la même semaine, utilisez l'option **force** (déconseillé en temps normal).

## C'est fini 🎉

Partagez l'adresse de votre site. Chaque lundi, la newsletter part toute seule.

**Si un lundi le numéro ne part pas**, GitHub vous envoie un email « Run failed ». Ouvrez l'exécution : le résumé explique la cause (pas assez d'actus, quota IA, clé expirée…). Il n'y a rien à « rattraper » : le lundi suivant repart normalement. Vous pouvez aussi relancer à la main depuis l'onglet Actions (le verrou empêche tout double envoi).
