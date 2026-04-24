# Guide utilisateur — Raijin

Raijin automatise la saisie de tes factures fournisseurs. Tu uploades un PDF ou une image, le moteur OCR extrait les informations, tu valides (ou corriges) en quelques secondes, et tu exportes le tout vers Excel pour ta comptabilité.

## 1. Se connecter

1. Ouvre `https://app.<ton-domaine>.com`
2. Si c'est ta première visite, clique sur **Créer un compte**
   - Entreprise : nom de ta société (ex. *Boulangerie Athéna SA*)
   - Nom complet : ton nom
   - Email + mot de passe (8 caractères min.)
3. Sinon, utilise **Connexion**

La session dure 30 minutes, prolongée automatiquement pendant l'usage.

## 2. Importer des factures

### Depuis la page « Importer »

- Glisse-dépose une ou plusieurs factures dans la zone pointillée, ou clique pour ouvrir ton explorateur de fichiers
- Formats acceptés : **PDF, JPG, PNG**
- Taille max : **20 Mo** par fichier
- Clique sur **Importer** pour lancer le traitement

### Ce qui se passe ensuite

1. Le fichier est stocké en sécurité (région UE, chiffré)
2. Azure Document Intelligence extrait les champs (fournisseur, montants, dates, lignes)
3. Les données sont normalisées (formats EU, TVA grecque automatiquement préfixée `EL`)
4. La facture apparaît dans le tableau de bord avec le statut **À valider**

Le traitement prend en général 10 à 30 secondes.

## 3. Valider une facture (Review)

Depuis le tableau de bord, clique sur une facture en statut **À valider**.

### Écran de review

- À **gauche** : aperçu du PDF original
- À **droite** : formulaire éditable avec les champs extraits

### Champs à vérifier

- **Numéro de facture** — doit être unique par fournisseur
- **Date d'émission** et **Date d'échéance**
- **Total HT + TVA = TTC** — l'interface signale automatiquement si les totaux ne correspondent pas (tolérance 0,02 €)
- **Lignes de facture** — tu peux ajouter, modifier ou supprimer des lignes

### Indicateurs de validation

En haut du formulaire, un panneau récapitule les alertes :

- 🟢 **Vert** : tout est cohérent, tu peux valider
- 🟡 **Jaune** (warning) : anomalie non-bloquante (numéro manquant, confidence moyenne, doublon possible)
- 🔴 **Rouge** (error) : anomalie bloquante — le bouton Valider sera refusé

### Actions disponibles

- **Enregistrer** — sauvegarde tes modifications sans changer le statut
- **Valider** — passe en statut *Validée*, sera exportable
- **Rejeter** — marque la facture comme rejetée (demande une raison)
- **Passer** — remet à plus tard (reste en *À valider*)
- **Réouvrir** — disponible sur les factures *Validées* ou *Rejetées* pour corriger

Toutes tes corrections sont tracées (qui, quand, quoi) pour audit.

## 4. Tableau de bord

- Widgets KPI en haut : compte de factures par statut
- Filtres rapides : Toutes / À valider / Validées / Rejetées / etc.
- Pagination en bas de liste
- Clique sur une ligne pour ouvrir le review

## 5. Exporter vers Excel

Bouton **Exporter Excel** en haut du tableau de bord.

Le fichier généré contient :
- Un onglet **Factures** avec toutes les factures (tu peux filtrer par statut ou période via l'URL)
- Un onglet **Export** avec les métadonnées (date d'export, nombre de factures)
- En-têtes figés, colonnes formatées (dates, montants, %)
- Une ligne de totaux en bas (SUM HT, TVA, TTC)

L'export respecte les filtres actifs de la liste.

## 6. Statuts possibles

| Statut | Signification |
|--------|---------------|
| **Reçue** | Fichier uploadé, OCR pas encore lancé |
| **Traitement** | OCR en cours chez Azure |
| **À valider** | OCR terminé, prêt pour review humain |
| **Validée** | Confirmée, exportable |
| **Rejetée** | Marquée comme non-valide (doublon, erreur, etc.) |
| **Échec** | OCR a échoué définitivement — voir la raison |

## 7. Aide & contact

- Problème technique : contact@venio.paris
- Documentation API : `https://api.<ton-domaine>.com/docs`

## Conseils

- Uploade des PDFs natifs (pas des scans) quand tu peux — l'accuracy OCR est meilleure
- Pour les scans, choisis 300 dpi minimum
- Plus tes premières validations sont rigoureuses, plus le système apprendra (les corrections tracées alimenteront les améliorations futures)
