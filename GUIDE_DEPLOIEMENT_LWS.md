# Mettre EazyMarket en ligne — LWS / cPanel

Montage retenu : **un sous-domaine du domaine ESVE**, une **base MySQL**, sur le
**même compte cPanel** que l'application ESVE.

Dans tout ce guide, remplacez :

| À remplacer | Par |
|---|---|
| `VOTRE-DOMAINE.com` | le domaine sur lequel tourne ESVE |
| `UTILISATEUR` | votre nom d'utilisateur cPanel |
| `3.11` | la version de Python que cPanel vous propose |

L'application ESVE n'est jamais touchée : nouveau sous-domaine, nouvelle base,
nouvelle application Python. En cas de problème, elle continue de tourner.

**Comptez une heure la première fois.** Faites les étapes dans l'ordre.

---

## Étape 0 — Préparer le paquet sur votre ordinateur

Double-cliquez sur **`faire_le_paquet.bat`**.

Un fichier `paquets/eazymarket-AAAAMMJJ-HHMM.zip` apparaît (environ 2 Mo). Il
contient le code et **rien d'autre** : ni votre base locale, ni votre `.env`, ni
vos photos de test. C'est voulu — ces éléments se recréent sur le serveur.

---

## Étape 1 — Créer le sous-domaine

cPanel → **Domaines** (ou **Sous-domaines**) → **Créer un sous-domaine**

- Sous-domaine : `boutique`
- Domaine : `VOTRE-DOMAINE.com`
- Racine du document : laissez ce que cPanel propose

**Notez précisément la racine du document affichée.** Ce sera par exemple
`/home/UTILISATEUR/boutique.VOTRE-DOMAINE.com` ou
`/home/UTILISATEUR/public_html/boutique`. Vous en aurez besoin trois fois.

Dans la suite, on l'appelle **DOSSIER_PUBLIC**.

---

## Étape 2 — Créer la base MySQL

cPanel → **Bases de données MySQL**

1. **Créer une base** : `eazymarket`
   → cPanel la nomme `UTILISATEUR_eazymarket`. Notez le nom complet.
2. **Créer un utilisateur** : `eazyuser`, avec un mot de passe long généré par
   cPanel. **Copiez-le tout de suite**, il ne sera plus affiché.
   → nom complet : `UTILISATEUR_eazyuser`
3. **Ajouter l'utilisateur à la base** → cochez **TOUS LES PRIVILÈGES**.

> **Le préfixe `UTILISATEUR_` fait partie du nom, mais ne le tapez pas vous-même :**
> cPanel l'ajoute tout seul. Si vous saisissez `eazymarket`, la base s'appellera
> `UTILISATEUR_eazymarket` — c'est ce nom complet qu'il faut donner ensuite.

> **Encodage.** Si cPanel vous laisse choisir la « collation », prenez
> **`utf8mb4_unicode_ci`**. C'est le seul encodage qui accepte les emoji — et
> vos vendeurs en mettront dans les noms de produits, vos clients dans les
> messages. Si l'option n'est pas proposée, ce n'est pas grave : la mise en
> ligne le corrige automatiquement (étape 7).

---

## Étape 3 — Créer l'application Python

cPanel → **Setup Python App** → **Create Application**

| Champ | Valeur |
|---|---|
| Python version | la plus récente proposée (3.9 minimum) |
| Application root | `eazymarket` |
| Application URL | `boutique.VOTRE-DOMAINE.com` (laisser le chemin vide) |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

Cliquez **Create**.

cPanel affiche en haut une ligne à copier, du type :

```
source /home/UTILISATEUR/virtualenv/eazymarket/3.11/bin/activate && cd /home/UTILISATEUR/eazymarket
```

**Gardez-la dans un coin** : c'est la commande qui vous met dans le bon
environnement à chaque fois.

---

## Étape 4 — Envoyer le code

cPanel → **Gestionnaire de fichiers** → ouvrez `/home/UTILISATEUR/eazymarket`

1. **Téléverser** votre ZIP.
2. Clic droit sur le ZIP → **Extraire** → dans le dossier courant.
3. Supprimez le ZIP une fois extrait.

Vérifiez que `manage.py`, `passenger_wsgi.py` et `requirements.txt` sont bien
**directement** dans `eazymarket/`, pas dans un sous-dossier. Si l'extraction a
créé un niveau en trop, remontez le contenu d'un cran.

> `passenger_wsgi.py` existe déjà (créé par cPanel) : **écrasez-le** par le nôtre.

---

## Étape 5 — Installer les dépendances

**Avec le Terminal** (cPanel → Terminal) :

```bash
source /home/UTILISATEUR/virtualenv/eazymarket/3.11/bin/activate && cd /home/UTILISATEUR/eazymarket
pip install --upgrade pip
pip install -r requirements.txt
```

**Sans Terminal** : cPanel → Setup Python App → votre application → champ
**Configuration files** → saisissez `requirements.txt` → **Run Pip Install**.

L'installation prend deux à trois minutes.

> Si `Pillow` échoue à se compiler, lancez `pip install --only-binary :all: Pillow`.
> Si `Django` refuse de s'installer, c'est que la version de Python est trop
> ancienne : `pip install "Django>=4.2,<5"` fonctionne à partir de Python 3.8.

---

## Étape 6 — Créer le fichier de configuration

**Une seule commande, et tout est rempli correctement :**

```bash
source /home/UTILISATEUR/virtualenv/eazymarket/3.11/bin/activate && cd /home/UTILISATEUR/eazymarket
python deploiement/configurer.py
```

Le script détecte votre compte, vos chemins et le dossier public de votre
sous-domaine, génère la clé secrète, et vous pose cinq questions :

1. **L'adresse du site** — `boutique.VOTRE-DOMAINE.com`
2. **Le dossier public** — il vous propose les dossiers trouvés sur le compte,
   vous tapez le numéro du bon
3. **La base MySQL** — nom, utilisateur, mot de passe (il propose déjà les noms
   préfixés par votre compte)
4. **Le HTTPS est-il actif ?** — répondez **non** si vous n'avez pas encore
   lancé AutoSSL
5. **L'e-mail** — vous pouvez répondre non et le configurer plus tard

Il écrit `.env` en permissions 600 (lisible par vous seul), crée les dossiers
`static/` et `media/` dans le dossier public, et y pose le `.htaccess` de
protection. **L'étape 8 est donc déjà faite.**

Si un `.env` existait, il est sauvegardé en `.env.sauvegarde` avant d'être
remplacé.

> **Vous ne pouvez plus vous tromper** : si une valeur d'exemple traîne encore
> dans le `.env`, l'application refuse de démarrer et affiche exactement quelle
> ligne corriger, au lieu d'une erreur illisible.

<details>
<summary>Le faire à la main plutôt qu'avec le script</summary>

Copiez `deploiement/.env.production.example` vers `eazymarket/.env` (à la
racine, pas dans `deploiement/`) et remplacez **toutes** les valeurs contenant
`A_REMPLIR`, `VOTRE-DOMAINE` ou `UTILISATEUR`. Aucune ne doit subsister.
Pour la clé secrète : `python -c "import secrets;print(secrets.token_urlsafe(60))"`.

</details>

---

## Étape 7 — Migrations, catalogue, fichiers statiques

Une seule commande fait tout :

```bash
source /home/UTILISATEUR/virtualenv/eazymarket/3.11/bin/activate && cd /home/UTILISATEUR/eazymarket
python deploiement/mise_en_ligne.py
```

Elle applique les migrations, **convertit la base en utf8mb4** (support des
emoji), installe les 12 pays, les 22 rayons et les 65 métiers, rassemble les
fichiers statiques, puis affiche un rapport de vérification.

**Sans Terminal** : Setup Python App → champ **Execute python script** →
`deploiement/mise_en_ligne.py` → Execute.

Puis créez votre compte administrateur :

```bash
python manage.py createsuperuser
```

*(Sans Terminal : `manage.py admin_reset --creer votre_nom --mdp VotreMotDePasse`
dans « Execute python script ».)*

---

## Étape 8 — Protéger les dossiers publics

**Déjà fait par `configurer.py`** à l'étape 6. Vérifiez simplement que les deux
fichiers existent (Gestionnaire de fichiers → *Paramètres → Afficher les
fichiers cachés*) :

- `DOSSIER_PUBLIC/static/.htaccess`
- `DOSSIER_PUBLIC/media/.htaccess`

S'ils manquent, collez-y le contenu de
`deploiement/htaccess-pour-static-et-media.txt`.

Ce n'est pas qu'une question de vitesse : ce fichier **interdit l'exécution de
code** dans le dossier des photos. Sans lui, quelqu'un qui parvient à envoyer un
faux fichier « image » pourrait exécuter du code sur votre serveur.

> **Filet de sécurité.** Le `.env` contient `DJANGO_SERVE_MEDIA=True` : si Apache
> ne sert pas `/media/` correctement, Django s'en charge lui-même et les photos
> s'affichent quand même. Une fois les deux `.htaccess` en place et les photos
> vérifiées, vous pouvez passer ce réglage à `False` pour gagner en rapidité.

---

## Étape 9 — Redémarrer et tester

cPanel → Setup Python App → votre application → bouton **RESTART**.

*(En Terminal : `touch ~/eazymarket/tmp/restart.txt`)*

Ouvrez **http://boutique.VOTRE-DOMAINE.com**. Vérifiez dans l'ordre :

1. La page d'accueil s'affiche **avec les couleurs et les icônes**
   → sinon, l'étape 7 (collectstatic) ou le chemin `DJANGO_STATIC_ROOT`.
2. `/compte/inscription/` s'ouvre et le formulaire s'envoie
   → sinon, `DJANGO_CSRF_TRUSTED_ORIGINS`.
3. `/django-admin/` vous laisse entrer.
4. Depuis l'admin, ajoutez un produit avec une photo, puis regardez la fiche :
   **la photo doit s'afficher** → sinon, `DJANGO_MEDIA_ROOT` ou les droits du
   dossier `media` (permissions 755).

---

## Étape 10 — Activer le HTTPS

cPanel → **SSL/TLS Status** (ou **Let's Encrypt**) → cochez le sous-domaine →
**Run AutoSSL** / **Issue**. Comptez quelques minutes.

Une fois le cadenas visible sur `https://boutique.VOTRE-DOMAINE.com`, repassez
dans le `.env` :

```ini
SECURE_SSL_REDIRECT=True
```

et redémarrez l'application.

> Ne mettez `True` **qu'après** avoir le certificat, sinon le site boucle en
> redirections et devient inaccessible.

---

## Étape 10 bis — Autoriser l'envoi des vidéos

Par défaut, un hébergement mutualisé refuse les fichiers de plus de 2 Mo.
Sans ce réglage, vos vendeurs verront leur envoi échouer sans explication.

cPanel → **Sélectionner la version de PHP** (ou *MultiPHP INI Editor*) →
onglet **Options**, puis mettre :

| Réglage | Valeur |
|---|---|
| `upload_max_filesize` | `20M` |
| `post_max_size` | `25M` |
| `max_execution_time` | `120` |
| `memory_limit` | `256M` |

> Ces valeurs concernent le serveur web, pas Python : elles s'appliquent quand
> même à l'application, car c'est Apache qui reçoit le fichier avant de le
> passer à Django.

Vérifiez ensuite qu'un vendeur peut bien envoyer une vidéo de 10 Mo depuis son
téléphone. Si l'envoi échoue toujours, baissez `VIDEO_MAX_MB` dans le `.env`
plutôt que de monter les valeurs ci-dessus : sur mutualisé, un envoi trop gros
finit en délai dépassé.

**Le disque.** Une vidéo de 30 secondes pèse environ 12 Mo. Surveillez
l'espace utilisé dans cPanel → *Utilisation du disque*. Quand ça monte,
baissez `VIDEO_FREE_SLOTS` : les vendeurs pourront toujours coller un lien
TikTok ou YouTube, qui ne vous coûte rien.

---

## Étape 11 — Les deux tâches automatiques

cPanel → **Tâches Cron** → Ajouter. Il en faut deux.

### 1. Toutes les heures — les commandes non confirmées

C'est la plus importante. Quand un vendeur ne répond pas dans les 24 heures,
c'est cette tâche qui annule la commande, remet l'article en stock et
rembourse le client. Sans elle, l'argent d'un client reste bloqué.

Réglage : **toutes les heures** (`0 * * * *`)

```bash
/home/UTILISATEUR/virtualenv/eazymarket/3.11/bin/python /home/UTILISATEUR/eazymarket/manage.py traiter_commandes >> /home/UTILISATEUR/eazymarket/logs/cron.log 2>&1
```

### 2. Une fois par jour — les gains des vendeurs

Elle rend disponibles au retrait les gains des vendeurs dont le délai de
sécurité est écoulé.

Réglage : **une fois par jour à 2 h du matin** (`0 2 * * *`)

```bash
/home/UTILISATEUR/virtualenv/eazymarket/3.11/bin/python /home/UTILISATEUR/eazymarket/manage.py liberer_gains >> /home/UTILISATEUR/eazymarket/logs/cron.log 2>&1
```

Si vous oubliez celle-ci, personne ne perd d'argent : les vendeurs attendent
simplement plus longtemps avant de pouvoir retirer.

### Vérifier que ça tourne

Après une heure, dans le Gestionnaire de fichiers, ouvrez
`eazymarket/logs/cron.log`. Vous devez y voir des lignes horodatées.
Un fichier vide signifie que la commande cron est mal écrite — le plus
souvent le chemin de `python` ou celui de `manage.py`.

---

## Mettre à jour le site plus tard

1. Sur votre ordinateur : `faire_le_paquet.bat`
2. **Sauvegardez d'abord** (voir ci-dessous).
3. Gestionnaire de fichiers → téléverser le ZIP dans `eazymarket/` → Extraire →
   **Écraser** les fichiers existants.
   Votre `.env`, votre base et vos photos ne sont pas dans le ZIP : ils survivent.
4. Terminal :
   ```bash
   source /home/UTILISATEUR/virtualenv/eazymarket/3.11/bin/activate && cd /home/UTILISATEUR/eazymarket
   pip install -r requirements.txt
   python deploiement/mise_en_ligne.py
   ```
5. **RESTART** dans Setup Python App.

C'est exactement la méthode que vous utilisez déjà pour ESVE.

---

## Sauvegardes

**Avant chaque mise à jour, et une fois par semaine :**

- **La base** : cPanel → Sauvegarde → *Télécharger une sauvegarde de base de
  données MySQL*. Ou en Terminal :
  ```bash
  mysqldump -u UTILISATEUR_eazyuser -p UTILISATEUR_eazymarket > ~/sauvegarde-$(date +%F).sql
  ```
- **Les photos** : compressez `DOSSIER_PUBLIC/media` et téléchargez l'archive.
  C'est la seule chose **irremplaçable** : le code, vous l'avez ; les photos des
  vendeurs, non.

---

## Quand ça ne marche pas

| Ce que vous voyez | Ce que c'est | Quoi faire |
|---|---|---|
| **Bad Request (400)** | Le domaine n'est pas autorisé | Ajouter le sous-domaine dans `DJANGO_ALLOWED_HOSTS`, redémarrer |
| **500 / We're sorry…** | Erreur applicative | Lire `logs/eazymarket.log` et `~/eazymarket/stderr.log`. Mettre `DJANGO_DEBUG=True` cinq minutes pour voir le message, **puis le remettre à False** |
| **Page sans style, tout blanc** | Les statiques ne sont pas servis | Relancer `mise_en_ligne.py`, vérifier `DJANGO_STATIC_ROOT` et le `.htaccess` de l'étape 8 |
| **Les photos ne s'affichent pas** | Chemin ou droits des médias | Vérifier `DJANGO_MEDIA_ROOT`, permissions 755 sur `media`, et `DJANGO_SERVE_MEDIA=True` |
| **CSRF verification failed** | Origine non déclarée | Renseigner `DJANGO_CSRF_TRUSTED_ORIGINS` avec `https://…` |
| **Access denied for user** | Base MySQL | Le préfixe du compte manque dans le nom, ou l'utilisateur n'a pas les privilèges |
| **`Incorrect string value: '\xF0\x9F...'`** | La base n'accepte pas les emoji | `python manage.py reparer_utf8mb4` puis relancer `mise_en_ligne.py` |
| **Trop de redirections** | HTTPS forcé sans certificat | `SECURE_SSL_REDIRECT=False` en attendant l'AutoSSL |
| **« Le fichier .env contient encore des valeurs d'exemple »** | `.env` non rempli | Lancer `python deploiement/configurer.py` |
| **`PermissionError: /home/UTILISATEUR`** | Idem : chemin d'exemple | Lancer `python deploiement/configurer.py` |
| **Les changements n'apparaissent pas** | Passenger a gardé l'ancien code | Bouton **RESTART**, ou `touch tmp/restart.txt` |
| **ESVE est tombé** | Rien à voir, mais vérifiez | Les deux applications sont séparées ; regardez le quota disque du compte |

À tout moment, pour savoir où vous en êtes :

```bash
python manage.py verifier_production
```

Elle passe en revue la sécurité, la base, les fichiers, les données de départ,
l'encaissement et l'e-mail — et dit précisément quoi corriger.

---

## Le jour de l'ouverture

- [ ] `python manage.py verifier_production` ne renvoie aucune erreur
- [ ] HTTPS actif, `SECURE_SSL_REDIRECT=True`
- [ ] Compte administrateur créé, mot de passe solide
- [ ] Vos quatre numéros d'encaissement visibles sur une page de paiement
- [ ] Une commande de test passée de bout en bout, payée et validée par vous
- [ ] `upload_max_filesize` et `post_max_size` relevés pour les vidéos
- [ ] Tâche cron `traiter_commandes` planifiée **toutes les heures**
- [ ] Tâche cron `liberer_gains` planifiée une fois par jour
- [ ] Première sauvegarde téléchargée
- [ ] `ARTISAN_FREE_LAUNCH=True` pour remplir l'annuaire les premiers mois
