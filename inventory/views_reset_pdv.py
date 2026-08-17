# -*- coding: utf-8 -*-
"""
Flux de réinitialisation d'un point de vente (PDV / terminal MAUI).

⚠️ Contrôle en 2 étapes :
  1. Le COMMERÇANT crée la demande (statut EN_ATTENTE) via un bouton.
  2. L'ADMINISTRATEUR valide (exécution réelle) ou refuse la demande.

La réinitialisation force le terminal MAUI à re-valider tous les articles :
  - est_valide_client = False  → l'article n'est plus disponible à la vente
  - quantite_envoyee   = 0     → le terminal doit tout re-synchroniser
Ceci déclenche une re-validation complète (quantités + stocks) côté MAUI.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DemandeResetPdv, Client
from .views_commercant import commercant_required, boutique_access_required

logger = logging.getLogger(__name__)


def _est_administrateur(user):
    return user.is_authenticated and user.is_staff


def _verifier_administrateur(request):
    if not _est_administrateur(request.user):
        return HttpResponseForbidden("Accès réservé aux administrateurs.")
    return None


def executer_reset_boutique(terminal, utilisateur):
    """
    Exécute la réinitialisation d'un point de vente (terminal).

    Retourne (nb_reinitialises, nb_total, resultat_text).
    ⚠️ Réutilisé par : la validation d'une demande commerçant ET la
    réinitialisation directe côté Django admin (bouton admin).
    """
    from .models import Article

    boutique = terminal.boutique
    if not boutique:
        return (0, 0, "Terminal sans boutique associée : aucune action.")

    articles = Article.objects.filter(boutique=boutique)
    nb_total = articles.count()
    nb_reinitialises = articles.filter(
        est_valide_client=True
    ).update(
        est_valide_client=False,
        quantite_envoyee=0,
        date_envoi=None,
        date_validation=None,
    )

    # Activer le terminal s'il avait été désactivé
    if not terminal.est_actif:
        terminal.est_actif = True
        terminal.save(update_fields=['est_actif'])

    resultat_text = (
        f"{nb_reinitialises}/{nb_total} article(s) remis en attente de validation "
        f"(est_valide_client=False, quantite_envoyee=0) pour le terminal "
        f"{terminal.numero_serie} ({boutique.nom}). "
        "Le terminal devra re-synchroniser et re-valider l'ensemble de son stock."
    )
    logger.info(
        f"[ResetPdv] Réinitialisation exécutée par {utilisateur} — {resultat_text}"
    )
    return (nb_reinitialises, nb_total, resultat_text)


def executer_reset_serveur_boutique(boutique, utilisateur):
    """
    ⚠️ Réinitialisation SERVEUR COMPLÈTE d'un point de vente (DESTRUCTIF).
    Remet à zéro tout ce qui a été ajouté côté Django pour cette boutique :
    articles, variantes, ventes, lignes, mouvements, alertes, ventes rejetées,
    négociations, retours, journal de valeur de stock, catégories.

    Le terminal MAUI lui-même (Client) n'est PAS supprimé.
    Retourne (compte_rendu_dict, texte_résumé).
    """
    from .models import (Article, VarianteArticle, Vente, LigneVente,
                         MouvementStock, AlerteStock, VenteRejetee,
                         ArticleNegocie, RetourArticle, JournalValeurStock,
                         Categorie)

    compte_rendu = {}

    # 1. Lignes de vente puis ventes
    compte_rendu['lignes_vente'] = LigneVente.objects.filter(vente__boutique=boutique).delete()[0]
    compte_rendu['ventes'] = Vente.objects.filter(boutique=boutique).delete()[0]

    # 2. Mouvements de stock (avant les articles, FK article)
    compte_rendu['mouvements_stock'] = MouvementStock.objects.filter(article__boutique=boutique).delete()[0]

    # 3. Données liées à la boutique
    compte_rendu['alertes_stock'] = AlerteStock.objects.filter(boutique=boutique).delete()[0]
    compte_rendu['ventes_rejetees'] = VenteRejetee.objects.filter(boutique=boutique).delete()[0]
    compte_rendu['articles_negocies'] = ArticleNegocie.objects.filter(boutique=boutique).delete()[0]
    compte_rendu['retours_articles'] = RetourArticle.objects.filter(boutique=boutique).delete()[0]
    compte_rendu['journal_valeur_stock'] = JournalValeurStock.objects.filter(boutique=boutique).delete()[0]

    # 4. Variantes puis articles
    compte_rendu['variantes'] = VarianteArticle.objects.filter(article_parent__boutique=boutique).delete()[0]
    compte_rendu['articles'] = Article.objects.filter(boutique=boutique).delete()[0]

    # 5. Catégories liées à la boutique
    compte_rendu['categories'] = Categorie.objects.filter(boutique=boutique).delete()[0]

    texte = (
        f"Réinitialisation SERVEUR COMPLÈTE du PDV « {boutique.nom} » "
        f"(déclenchée par {utilisateur}) : "
        f"{compte_rendu['articles']} article(s), "
        f"{compte_rendu['variantes']} variante(s), "
        f"{compte_rendu['ventes']} vente(s), "
        f"{compte_rendu['lignes_vente']} ligne(s), "
        f"{compte_rendu['mouvements_stock']} mouvement(s) de stock, "
        f"{compte_rendu['journal_valeur_stock']} ligne(s) de journal, "
        f"{compte_rendu['alertes_stock']} alerte(s), "
        f"{compte_rendu['ventes_rejetees']} vente(s) rejetée(s), "
        f"{compte_rendu['articles_negocies']} négociation(s), "
        f"{compte_rendu['retours_articles']} retour(s), "
        f"{compte_rendu['categories']} catégorie(s) — tout est remis à zéro."
    )
    logger.warning(f"[ResetPdv] {texte}")
    return (compte_rendu, texte)


# ─────────────────────────────────────────────
# 1) CÔTÉ COMMERÇANT : créer la demande
# ─────────────────────────────────────────────
@login_required
@commercant_required
@boutique_access_required
@require_POST
def demander_reset_pdv(request, boutique_id, terminal_id):
    """Crée une demande de réinitialisation (ne réinitialise RIEN).

    type_reset (POST) :
      - 'MAUI'    (défaut) : re-validation des articles par le terminal
      - 'SERVEUR'         : remise à zéro SÉRVÉR complète (articles, ventes…)
    """
    boutique = request.boutique
    terminal = get_object_or_404(Client, id=terminal_id, boutique=boutique)
    type_reset = (request.POST.get('type_reset') or 'MAUI').upper()
    if type_reset not in ('MAUI', 'SERVEUR'):
        type_reset = 'MAUI'

    # Pas de demande en double tant que la précédente n'est pas traitée (par type)
    deja_en_attente = DemandeResetPdv.objects.filter(
        terminal=terminal, statut='EN_ATTENTE', type_reset=type_reset
    ).exists()
    if deja_en_attente:
        messages.warning(
            request,
            f"Une demande de réinitialisation ({'serveur complète' if type_reset == 'SERVEUR' else 'terminal MAUI'}) "
            f"pour « {terminal.nom_terminal} » est déjà en attente de validation."
        )
        return redirect('inventory:commercant_terminaux_boutique', boutique_id)

    motif = (request.POST.get('motif') or '').strip()

    demande = DemandeResetPdv.objects.create(
        terminal=terminal,
        boutique=boutique,
        demandeur=request.user,
        motif=motif,
        statut='EN_ATTENTE',
        type_reset=type_reset,
    )

    logger.info(
        f"[ResetPdv] Demande #{demande.id} ({type_reset}) créée par {request.user.username} "
        f"pour le terminal {terminal.numero_serie} ({boutique.nom})"
    )
    if type_reset == 'SERVEUR':
        messages.warning(
            request,
            f"Demande de RÉINITIALISATION SERVEUR COMPLÈTE de « {terminal.nom_terminal} » envoyée. "
            "⚠️ Elle supprimera tous les articles, ventes et mouvements côté serveur "
            "— exécutée UNIQUEMENT après validation par l'administrateur."
        )
    else:
        messages.success(
            request,
            f"Demande de réinitialisation de « {terminal.nom_terminal} » envoyée. "
            "Elle sera exécutée UNIQUEMENT après validation par l'administrateur."
        )
    return redirect('inventory:commercant_terminaux_boutique', boutique_id)


# ─────────────────────────────────────────────
# 2) CÔTÉ ADMINISTRATEUR : liste + validation/refus
# ─────────────────────────────────────────────
@login_required
def liste_demandes_reset(request):
    """Liste des demandes de réinitialisation (administrateurs uniquement)."""
    bloquer = _verifier_administrateur(request)
    if bloquer:
        return bloquer

    demandes = DemandeResetPdv.objects.select_related(
        'terminal', 'boutique', 'boutique__commercant', 'demandeur', 'traite_par'
    ).all()

    filtres = {
        'en_attente': demandes.filter(statut='EN_ATTENTE'),
        'validees': demandes.filter(statut='VALIDEE'),
        'refusees': demandes.filter(statut='REFUSEE'),
    }

    return render(request, 'inventory/admin/demandes_reset.html', {
        'demandes': filtres,
    })


@login_required
@require_POST
def valider_demande_reset(request, demande_id):
    """Valide la demande : la réinitialisation est réellement exécutée ici."""
    bloquer = _verifier_administrateur(request)
    if bloquer:
        return bloquer

    demande = get_object_or_404(DemandeResetPdv, id=demande_id)
    if demande.statut != 'EN_ATTENTE':
        messages.warning(request, "Cette demande a déjà été traitée.")
        return redirect('inventory:liste_demandes_reset')

    # ── Exécution selon le TYPE de réinitialisation ──
    if demande.type_reset == 'SERVEUR':
        # ⚠️ Remise à zéro SERVEUR COMPLÈTE (destructif)
        compte_rendu, resultat_text = executer_reset_serveur_boutique(
            demande.boutique, request.user
        )
        nb_reinitialises = compte_rendu.get('articles', 0)
        nb_total = compte_rendu.get('articles', 0)
        messages.warning(
            request,
            f"Demande validée — RÉINITIALISATION SERVEUR COMPLÈTE exécutée : "
            f"{compte_rendu['articles']} article(s), {compte_rendu['ventes']} vente(s), "
            f"{compte_rendu['mouvements_stock']} mouvement(s) supprimés. Le PDV est reparti de zéro."
        )
    else:
        # Re-validation terminal MAUI (stock/historique conservés)
        nb_reinitialises, nb_total, resultat_text = executer_reset_boutique(
            demande.terminal, request.user
        )
        messages.success(
            request,
            f"Demande validée. {nb_reinitialises} article(s) remis en attente de "
            "re-validation — le terminal devra re-synchroniser son stock."
        )

    # ── Finaliser la demande ──
    demande.statut = 'VALIDEE'
    demande.traite_par = request.user
    demande.date_traitement = timezone.now()
    demande.reponse_admin = (request.POST.get('reponse') or '').strip()
    demande.resultat = resultat_text
    demande.save(update_fields=[
        'statut', 'traite_par', 'date_traitement', 'reponse_admin', 'resultat'
    ])

    return redirect('inventory:liste_demandes_reset')


@login_required
@require_POST
def refuser_demande_reset(request, demande_id):
    """Refuse la demande : aucune action n'est exécutée."""
    bloquer = _verifier_administrateur(request)
    if bloquer:
        return bloquer

    demande = get_object_or_404(DemandeResetPdv, id=demande_id)
    if demande.statut != 'EN_ATTENTE':
        messages.warning(request, "Cette demande a déjà été traitée.")
        return redirect('inventory:liste_demandes_reset')

    demande.statut = 'REFUSEE'
    demande.traite_par = request.user
    demande.date_traitement = timezone.now()
    demande.reponse_admin = (request.POST.get('reponse') or '').strip()
    demande.resultat = "Demande refusée par l'administrateur. Aucune action exécutée."
    demande.save(update_fields=[
        'statut', 'traite_par', 'date_traitement', 'reponse_admin', 'resultat'
    ])

    logger.info(
        f"[ResetPdv] Demande #{demande.id} REFUSÉE par {request.user.username}"
    )
    messages.success(request, "Demande refusée. Le point de vente reste inchangé.")
    return redirect('inventory:liste_demandes_reset')


# ─────────────────────────────────────────────
# 3) CÔTÉ DJANGO ADMIN : réinitialisation DIRECTE d'un PDV
#    (l'administrateur n'a pas besoin de passer par une demande)
# ─────────────────────────────────────────────
@login_required
def reinitialiser_pdv_direct(request, terminal_id):
    """
    Réinitialise immédiatement un point de vente, sans demande préalable.
    Réservé aux administrateurs.
      - GET  : page de confirmation (bouton « Réinitialiser » visible dans l'admin Django)
      - POST : exécution réelle de la réinitialisation
    Historique conservé via DemandeResetPdv (statut VALIDEE).
    """
    bloquer = _verifier_administrateur(request)
    if bloquer:
        return bloquer

    terminal = get_object_or_404(Client, id=terminal_id)

    from .models import Article
    nb_total = Article.objects.filter(boutique=terminal.boutique).count() if terminal.boutique else 0

    if request.method == 'GET':
        return render(request, 'inventory/admin/confirmer_reset_pdv.html', {
            'terminal': terminal,
            'nb_articles': nb_total,
        })

    # POST : exécution
    nb_reinitialises, nb_total, resultat_text = executer_reset_boutique(
        terminal, request.user
    )

    # Historique : une ligne VALIDEE tracée dans la même table que les demandes
    DemandeResetPdv.objects.create(
        terminal=terminal,
        boutique=terminal.boutique,
        demandeur=request.user,
        motif="Réinitialisation directe depuis l'admin Django",
        statut='VALIDEE',
        traite_par=request.user,
        date_traitement=timezone.now(),
        reponse_admin=(request.POST.get('reponse') or '').strip(),
        resultat=resultat_text,
    )

    messages.success(
        request,
        f"✔ Point de vente réinitialisé : {nb_reinitialises}/{nb_total} article(s) "
        "remis en attente de re-validation."
    )
    return redirect(request.META.get('HTTP_REFERER') or 'admin:index')


@login_required
def reinitialiser_pdv_serveur_direct(request, terminal_id):
    """
    ⚠️ RÉINITIALISATION SERVEUR COMPLÈTE directe (DESTRUCTIVE).
    Remet à zéro côté Django : articles, ventes, mouvements, journal…
      - GET  : page de confirmation avec décompte de ce qui sera supprimé
      - POST : exécution
    Réservé aux administrateurs.
    """
    bloquer = _verifier_administrateur(request)
    if bloquer:
        return bloquer

    terminal = get_object_or_404(Client, id=terminal_id)
    boutique = terminal.boutique

    from .models import (Article, VarianteArticle, Vente, LigneVente,
                         MouvementStock, AlerteStock, VenteRejetee,
                         ArticleNegocie, RetourArticle, JournalValeurStock, Categorie)

    def _compter():
        return {
            'articles': Article.objects.filter(boutique=boutique).count(),
            'variantes': VarianteArticle.objects.filter(article_parent__boutique=boutique).count(),
            'ventes': Vente.objects.filter(boutique=boutique).count(),
            'lignes_vente': LigneVente.objects.filter(vente__boutique=boutique).count(),
            'mouvements_stock': MouvementStock.objects.filter(article__boutique=boutique).count(),
            'alertes_stock': AlerteStock.objects.filter(boutique=boutique).count(),
            'ventes_rejetees': VenteRejetee.objects.filter(boutique=boutique).count(),
            'articles_negocies': ArticleNegocie.objects.filter(boutique=boutique).count(),
            'retours_articles': RetourArticle.objects.filter(boutique=boutique).count(),
            'journal_valeur_stock': JournalValeurStock.objects.filter(boutique=boutique).count(),
            'categories': Categorie.objects.filter(boutique=boutique).count(),
        }

    if request.method == 'GET':
        return render(request, 'inventory/admin/confirmer_reset_serveur_pdv.html', {
            'terminal': terminal,
            'boutique': boutique,
            'decompte': _compter(),
        })

    # POST : exécution
    compte_rendu, resultat_text = executer_reset_serveur_boutique(boutique, request.user)

    # Historique tracé comme demande VALIDEE de type SERVEUR
    DemandeResetPdv.objects.create(
        terminal=terminal,
        boutique=boutique,
        demandeur=request.user,
        motif="Réinitialisation serveur complète (admin Django direct)",
        type_reset='SERVEUR',
        statut='VALIDEE',
        traite_par=request.user,
        date_traitement=timezone.now(),
        reponse_admin=(request.POST.get('reponse') or '').strip(),
        resultat=resultat_text,
    )

    messages.warning(
        request,
        f"⚠️ RÉINITIALISATION SERVEUR COMPLÈTE exécutée : {compte_rendu['articles']} "
        f"article(s), {compte_rendu['ventes']} vente(s), "
        f"{compte_rendu['mouvements_stock']} mouvement(s) supprimés. "
        "Le point de vente est reparti de zéro côté serveur."
    )
    return redirect(request.META.get('HTTP_REFERER') or 'admin:index')
