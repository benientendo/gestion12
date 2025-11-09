# ✅ Checklist Déploiement Scalingo

## Avant le Déploiement

- [ ] Compte Scalingo créé et vérifié
- [ ] CLI Scalingo installé (optionnel)
- [ ] Git installé et configuré
- [ ] Code testé localement et fonctionnel

## Fichiers Créés (Déjà fait ✅)

- [x] `Procfile` - Configuration serveur
- [x] `runtime.txt` - Version Python
- [x] `requirements.txt` - Dépendances complètes
- [x] `scalingo.json` - Configuration Scalingo
- [x] `.scalingoignore` - Fichiers à ignorer
- [x] `.env.example` - Exemple variables d'environnement
- [x] `settings.py` - Adapté pour production

## Configuration Initiale

- [ ] Repository Git initialisé
- [ ] `.gitignore` créé
- [ ] Premier commit effectué
- [ ] Application Scalingo créée
- [ ] Addon PostgreSQL ajouté

## Variables d'Environnement

- [ ] `SECRET_KEY` générée et configurée
- [ ] `DEBUG=False` configuré
- [ ] `ALLOWED_HOSTS` configuré avec `.scalingo.io`
- [ ] `DATABASE_URL` vérifiée (automatique avec PostgreSQL)

## Déploiement

- [ ] Remote Git Scalingo ajouté
- [ ] Code poussé sur Scalingo (`git push scalingo master`)
- [ ] Build réussi (vérifier les logs)
- [ ] Application démarrée

## Post-Déploiement

- [ ] Migrations exécutées (`python manage.py migrate`)
- [ ] Superutilisateur créé (`python manage.py createsuperuser`)
- [ ] Fichiers statiques collectés (automatique via Procfile)
- [ ] Application accessible via URL Scalingo
- [ ] Admin Django accessible (`/admin/`)
- [ ] API fonctionne (`/api/v2/`)

## Tests Fonctionnels

- [ ] Connexion admin réussie
- [ ] Création d'un commerçant
- [ ] Création d'une boutique
- [ ] Ajout d'articles
- [ ] Test API avec MAUI (si applicable)
- [ ] Fichiers statiques (CSS/JS) chargent correctement
- [ ] Génération QR codes fonctionne
- [ ] Export PDF fonctionne

## Configuration MAUI

- [ ] URL API mise à jour vers Scalingo
- [ ] Test d'authentification MAUI réussi
- [ ] Test de synchronisation articles
- [ ] Test de création vente

## Sécurité

- [ ] `DEBUG=False` vérifié
- [ ] `SECRET_KEY` unique et sécurisée
- [ ] HTTPS actif (automatique Scalingo)
- [ ] Variables sensibles dans variables d'environnement
- [ ] Pas de clés/secrets dans le code

## Monitoring

- [ ] Logs vérifiés (pas d'erreurs)
- [ ] Métriques consultées (CPU, RAM)
- [ ] Notifications configurées (optionnel)
- [ ] Backups PostgreSQL vérifiés

## Documentation

- [ ] Guide de déploiement lu
- [ ] URLs notées (app, admin, API)
- [ ] Identifiants superuser sauvegardés (sécurisé)
- [ ] Documentation utilisateur mise à jour

## 🎉 Déploiement Terminé !

Une fois tous les points cochés, votre application est prête pour la production !

---

**Date de déploiement** : _______________  
**URL Production** : _______________  
**Nom App Scalingo** : _______________
