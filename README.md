# Edicom Score Entreprise (v0.3)

Application web : on cherche une entreprise, on voit son **score de santé financière (A à E)** et son **statut d'activité**, et on génère le **rapport PDF de 3 pages** en un clic.

## Démarrer (2 minutes)
1. Installer Python 3.10 ou plus.
2. Double-cliquer sur **`lancer.bat`** (Windows) ou lancer `./lancer.sh` (Mac/Linux). Le navigateur s'ouvre sur http://localhost:8000.
3. Page **Données** : déposer le classeur d'exemple `exemple/Edicom_Donnees_2018-2019.xlsx` (ou vos propres fichiers) puis **Calculer les scores**.

Ou en ligne de commande : `pip install -r requirements.txt` puis `python -m edicom_score serve`.

## Les écrans
| Écran | Rôle |
|---|---|
| **Accueil** | Recherche en direct (nom, ICE, RC) avec score et statut dans la liste de suggestions ; vue d'ensemble du panel (ruban des classes, ruban des statuts, points à regarder en priorité, villes). Raccourci `/` partout. |
| **Entreprises** | Liste filtrable (texte, classe, statut d'activité, ville, forme juridique, évolution, plage de score), tri, pagination, bouton **PDF** sur chaque ligne, sélection multiple, **Comparer** (2 ou 3), **Exporter en Excel** et **Rapports PDF en ZIP** (jusqu'à 1 000). Les filtres sont dans l'adresse : une vue filtrée se partage par lien. |
| **Fiche entreprise** | Score et échelle A-E, statut d'activité avec preuves, recommandation, piliers, points forts et de vigilance, indicateurs face à la médiane, chiffres clés N-1/N, et le **PDF affiché à côté** (télécharger, imprimer). |
| **Données** | Dépôt glisser-déposer, détection automatique des feuilles et des années, contrôle avant calcul, calcul avec progression. |
| **Aide** | Comment lire le score, les piliers, les statuts, les limites. |

## Formats d'import acceptés
Déposez tout en une fois, dans n'importe quel ordre. Les feuilles sont reconnues par leurs **colonnes** (`ACTIF_*_NET`, `PASSIF_*_EXACT`, `Raison Sociale`) et l'année par le **nom de la feuille ou du fichier**.
* **Un seul classeur** : feuilles `2018`, `2019` (colonnes Actif et Passif ensemble) et `Edicom`. Voir `exemple/`.
* **Un seul classeur, version détaillée** : `Actif 2018`, `Passif 2018`, `Actif 2019`, `Passif 2019`, `Edicom`.
* **Les fichiers d'origine** : OMPIC 2018, OMPIC 2019, fichier Edicom.
Il faut deux exercices consécutifs. S'il y en a davantage, les deux derniers sont utilisés. Pour mettre à jour (par exemple 2022 et 2023), il suffit de déposer les nouveaux bilans : le calcul remplace les données actuelles.

## Ligne de commande
```bash
python -m edicom_score build exemple/Edicom_Donnees_2018-2019.xlsx     # ou plusieurs fichiers
python -m edicom_score status "Sonofet"                                # code, ICE ou nom
python -m edicom_score pdf 001535901000016 -o sonofet.pdf
python -m edicom_score batch --cls A,B --activity ACTIVE --out-dir output/pdfs
python -m edicom_score export -o output/scores.xlsx
python -m edicom_score serve --host 0.0.0.0 --port 8000                # accès depuis le réseau
```
`--store DIR` (avant la sous-commande) change le dossier des données (défaut `output/`).

## API HTTP (pour intégrer à Telecontact)
Documentation interactive : `/docs`.
| Route | Rôle |
|---|---|
| `GET /health` | état du service |
| `GET /v1/suggest?q=…` | suggestions rapides |
| `GET /v1/companies?q=&class=A,B&activity=ACTIVE&city=&form=&persp=&smin=&smax=&sort=&order=&page=&size=` | liste filtrée |
| `GET /v1/companies/{code}` | fiche complète (JSON) |
| `GET /v1/companies/{code}/status` | statut d'activité seul |
| `GET /v1/companies/{code}/report.pdf` | rapport PDF (cache disque) |
| `GET /v1/export.xlsx?…` | export Excel des filtres |
| `POST /v1/batch` puis `GET /v1/jobs/{id}`, `/download` | ZIP de PDF |
| `POST /v1/import/scan`, `POST /v1/import/{id}/build` | import par API |

Protection : `EDICOM_API_KEY=…` exige l'en-tête `X-API-Key` (l'interface demande la clé à la première visite).
Variables : `EDICOM_STORE_DIR`, `EDICOM_RECENT_WINDOW` (3 ans), `EDICOM_SUBSTANCE_DH` (1 000 000).

## Déployer sur Vercel
Le dossier est prêt : `store/` contient déjà les scores calculés, `public/` les fichiers de l'interface, `vercel.json` et `api/index.py` la fonction. Vérifié avec le build local de Vercel (Python 3.12, 197 Mo sur 250 Mo autorisés).

1. Installez Node.js puis `npm i -g vercel`, et connectez-vous : `vercel login`.
2. **Créez la clé d'accès** (obligatoire : sans elle le site refuse de servir les données). Générez une clé longue (`python -c "import secrets; print(secrets.token_urlsafe(32))"`), puis `vercel env add EDICOM_API_KEY production` et collez-la.
3. Depuis ce dossier : `vercel --prod`. Vercel affiche l'adresse du site.
4. Ouvrez le site : il demande la clé à la première visite (mémorisée dans le navigateur).

**Mettre à jour les données.** Importez les nouveaux bilans en local (`lancer.bat`, page Données), puis dans ce dossier : `python -m edicom_score vercel` (copie les scores dans `store/` et rafraîchit `public/`) et `vercel --prod`. Ou en une commande : `python -m edicom_score vercel mon_classeur.xlsx`.

**Ce qui change en ligne.** Le disque est en lecture seule : pas d'import depuis le site (la page Données explique la marche à suivre). Les ZIP de rapports sont limités à 12 PDF (Vercel plafonne les réponses à 4,5 Mo) ; pour un gros lot, utilisez `python -m edicom_score batch` en local. Chaque PDF est généré à la demande (environ 1 s). La région est Paris (`cdg1`, modifiable dans `vercel.json`).

**À savoir avant de publier.**
* Les données sont privées (coordonnées de dirigeants incluses) : ne les mettez jamais dans un dépôt public. Avec `vercel --prod` depuis ce dossier, `store/` part directement, sans passer par Git. Pour un déploiement via un dépôt Git **privé**, retirez la ligne `store/` de `.gitignore`.
* Le plan gratuit « Hobby » de Vercel est réservé à un usage personnel non commercial : pour Telecontact, prévoyez un plan Pro ou équipe. Avec Pro, activez aussi « Deployment Protection » pour une deuxième barrière devant la clé.
* Données de dirigeants hébergées hors du Maroc : vérifiez avec votre juriste la conformité à la loi 09-08 (CNDP).
* La clé est une protection simple (un secret partagé). Pour des comptes individuels, il faudra placer le site derrière votre authentification.

## Autres hébergements (Docker)
* `docker build -t edicom-score .` puis monter un volume sur `/data/store` (ici l'import depuis le site reste possible).
* L'application n'a pas de comptes utilisateurs : placez-la derrière votre authentification (reverse proxy) ou utilisez la clé d'API. Les fichiers importés sont supprimés après le calcul.
* Un seul processus (état en mémoire pour les tâches). Pour plusieurs instances, partagez le dossier des données.

## Architecture
`ingest` (détection des feuilles) → `loaders` → `features` (CGNC : actif/passif, FR/BFR/TN) → `scoring` (5 piliers, plafonds légaux) + `activity` (preuves + modèle de dormance) → `pipeline` → `store` → `report` (PDF) / `export` (xlsx) / `service` / `api` (+ `web/` : l'interface) / `cli`.

## Méthode (résumé)
* **Score** : Solvabilité 30 % · Liquidité 10 % · Rentabilité 28 % · Dynamique 10 % · Profil Edicom 22 %. Plafonds : fonds propres < ¼ du capital (art. 357 loi 17-95 ; art. 86 loi 5-96) → 45 ; fonds propres négatifs → 30. Classes A ≥ 75, B ≥ 60, C ≥ 45, D ≥ 30, E < 30 ; non noté si total bilan < 10 000 DH.
* **Test rétrospectif 2018→2019** : AUC 0,79 (Altman Z'' : 0,67). Situation défavorable observée : A 2,8 % · B 4,1 % · C 14,2 % · D 45,7 % · E 92 %.
* **Statut** : CA Edicom récent → active ; sinon CA ancien + empreinte du bilan → probablement active ; sinon ressemblance à une société dormante (AUC 0,90 en validation croisée) ; bilan ≥ 1 M DH ou société patrimoniale sans CA → à vérifier, jamais « inactive ».

## Limites à connaître
* Bilans de l'exercice 2019 uniquement ; pas de compte de produits et charges, pas de secteur, pas de données de défaillance judiciaire : la calibration utilise un proxy « situation défavorable à N+1 ».
* La colonne FDA d'Edicom n'est pas documentée : non utilisée.
* Le statut d'activité est une estimation. Il ne remplace pas la vérification officielle (registre du commerce OMPIC, ice.gov.ma, attestations DGI et CNSS).
* Avec des bilans récents, re-mesurer `OBSERVED_ADVERSE_RATE` (config.py).

## Tests
`pip install -r requirements-dev.txt` puis `python -m pytest` (49 tests). Avec `EDICOM_RAW_DIR=dossier_des_fichiers_bruts`, deux tests supplémentaires rejouent tout le calcul à partir des fichiers d'origine.
