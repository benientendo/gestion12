"""
Commande Django pour envoyer des rappels de paiement par SMS (Infobip)
aux commerçants actifs ayant un numéro de téléphone enregistré.

Usage:
    python manage.py send_payment_reminders
    python manage.py send_payment_reminders --dry-run          # Aperçu sans envoyer
    python manage.py send_payment_reminders --commercant-id 5  # Un seul commerçant
    python manage.py send_payment_reminders --abonnement GRATUIT  # Filtre par abonnement

Variables d'environnement requises:
    INFOBIP_API_KEY   - Votre clé API Infobip
    INFOBIP_BASE_URL  - URL de base Infobip (ex: xxxxxx.api.infobip.com)
    INFOBIP_SENDER    - Nom ou numéro expéditeur (ex: GestionNum)
"""

import http.client
import json
import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from inventory.models import Commercant


# ─── Message de rappel (personnalisé avec {nom} et {abonnement}) ───────────────

MESSAGE_RAPPEL = (
    "Bonjour {nom},\n\n"
    "Nous vous rappelons cordialement que votre abonnement {abonnement} "
    "à GestionNumerique est en attente de renouvellement.\n\n"
    "Votre fidélité est essentielle — elle nous permet de continuer à "
    "améliorer la plateforme et à vous offrir un service de qualité.\n\n"
    "Merci de régulariser votre situation dès que possible pour éviter "
    "toute interruption de service.\n\n"
    "Pour toute question, répondez à ce message ou contactez-nous.\n"
    "— L'équipe GestionNumerique"
)


def normaliser_telephone(telephone: str) -> str | None:
    """
    Normalise un numéro de téléphone au format international E.164.
    Gère les formats congolais (+243, 0XXXXXXXXX, 243XXXXXXXXX).
    Retourne None si le numéro est invalide.
    """
    if not telephone:
        return None

    # Supprimer espaces, tirets, parenthèses
    numero = re.sub(r"[\s\-\(\)\.]+", "", telephone)

    # Déjà au format international
    if numero.startswith("+"):
        return numero if len(numero) >= 10 else None

    # Format 243XXXXXXXXX (sans +)
    if numero.startswith("243") and len(numero) == 12:
        return "+" + numero

    # Format local 0XXXXXXXXX (DRC: 09 chiffres après le 0)
    if numero.startswith("0") and len(numero) == 10:
        return "+243" + numero[1:]

    # Format local sans 0 (9 chiffres, DRC)
    if len(numero) == 9:
        return "+243" + numero

    return None


class Command(BaseCommand):
    help = "Envoie des rappels de paiement par SMS aux commerçants via Infobip"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les messages sans les envoyer",
        )
        parser.add_argument(
            "--commercant-id",
            type=int,
            help="Envoyer uniquement au commerçant avec cet ID",
        )
        parser.add_argument(
            "--abonnement",
            type=str,
            help="Filtrer par type d'abonnement (GRATUIT, STANDARD, PREMIUM, ENTREPRISE)",
        )
        parser.add_argument(
            "--test-numero",
            type=str,
            help="Envoyer un SMS de test à ce numéro précis (ex: 0858223735 ou +243858223735)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        commercant_id = options.get("commercant_id")
        abonnement_filtre = options.get("abonnement")
        test_numero = options.get("test_numero")

        # ── Récupérer la configuration Infobip depuis les variables d'environnement ──
        api_key = os.environ.get("INFOBIP_API_KEY")
        base_url = os.environ.get("INFOBIP_BASE_URL")
        sender = os.environ.get("INFOBIP_SENDER", "GestionNum")

        # ── Mode test : envoyer à un numéro précis ─────────────────────────────────
        if test_numero:
            telephone_normalise = normaliser_telephone(test_numero)
            if not telephone_normalise:
                raise CommandError(f"Numéro invalide : '{test_numero}'")

            message = MESSAGE_RAPPEL.format(
                nom="[Client Test]",
                abonnement="Standard",
            )

            self.stdout.write(self.style.HTTP_INFO(
                f"\n{'[DRY-RUN] ' if dry_run else ''}TEST SMS → {telephone_normalise}\n" + "─" * 50
            ))
            self.stdout.write(f"Contenu:\n{self._indenter(message)}\n")

            if not dry_run:
                if not api_key:
                    raise CommandError("Variable INFOBIP_API_KEY manquante.")
                if not base_url:
                    raise CommandError("Variable INFOBIP_BASE_URL manquante.")
                succes = self._envoyer_sms(api_key, base_url, sender, telephone_normalise, message)
                if succes:
                    self.stdout.write(self.style.SUCCESS(f"✅ SMS de test envoyé à {telephone_normalise}"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Échec envoi à {telephone_normalise}"))
            else:
                self.stdout.write(self.style.SUCCESS("[DRY-RUN] SMS simulé ✓"))
            return

        if not dry_run:
            if not api_key:
                raise CommandError(
                    "Variable d'environnement INFOBIP_API_KEY manquante."
                )
            if not base_url:
                raise CommandError(
                    "Variable d'environnement INFOBIP_BASE_URL manquante. "
                    "Exemple: xxxxxx.api.infobip.com"
                )

        # ── Construire la queryset des commerçants ──────────────────────────────────
        qs = Commercant.objects.filter(est_actif=True).exclude(telephone="")

        if commercant_id:
            qs = qs.filter(id=commercant_id)

        if abonnement_filtre:
            qs = qs.filter(type_abonnement=abonnement_filtre.upper())

        commercants = list(qs.order_by("nom_entreprise"))

        if not commercants:
            self.stdout.write(self.style.WARNING("Aucun commerçant actif avec téléphone trouvé."))
            return

        self.stdout.write(
            self.style.HTTP_INFO(
                f"\n{'[DRY-RUN] ' if dry_run else ''}Rappels à envoyer : {len(commercants)} commerçant(s)\n"
                + ("─" * 60)
            )
        )

        envoyes = 0
        echecs = 0
        ignores = 0

        for commercant in commercants:
            telephone_normalise = normaliser_telephone(commercant.telephone)

            if not telephone_normalise:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠ {commercant.nom_entreprise} — numéro invalide: '{commercant.telephone}' (ignoré)"
                    )
                )
                ignores += 1
                continue

            message = MESSAGE_RAPPEL.format(
                nom=commercant.nom_responsable,
                abonnement=commercant.get_type_abonnement_display(),
            )

            self.stdout.write(
                f"\n  📱 {commercant.nom_entreprise} ({commercant.nom_responsable})\n"
                f"     Téléphone : {telephone_normalise}\n"
                f"     Abonnement: {commercant.get_type_abonnement_display()}\n"
            )

            if dry_run:
                self.stdout.write(self.style.SUCCESS("     [DRY-RUN] Message simulé ✓"))
                self.stdout.write(f"     Contenu:\n{self._indenter(message)}")
                envoyes += 1
                continue

            # ── Envoi via Infobip SMS API ──────────────────────────────────────────
            try:
                succes = self._envoyer_sms(
                    api_key=api_key,
                    base_url=base_url,
                    sender=sender,
                    destinataire=telephone_normalise,
                    message=message,
                )
                if succes:
                    self.stdout.write(self.style.SUCCESS("     ✅ SMS envoyé avec succès"))
                    envoyes += 1
                else:
                    self.stdout.write(self.style.ERROR("     ❌ Échec d'envoi (voir détails ci-dessus)"))
                    echecs += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"     ❌ Erreur: {exc}"))
                echecs += 1

        # ── Résumé ─────────────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Résumé: {envoyes} envoyé(s), {echecs} échec(s), {ignores} ignoré(s)"
            )
        )

    def _envoyer_sms(self, api_key: str, base_url: str, sender: str,
                     destinataire: str, message: str) -> bool:
        """Envoie un SMS via l'API Infobip SMS v2."""
        payload = json.dumps({
            "messages": [
                {
                    "from": sender,
                    "destinations": [{"to": destinataire}],
                    "text": message,
                }
            ]
        })

        headers = {
            "Authorization": f"App {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        conn = http.client.HTTPSConnection(base_url, timeout=15)
        try:
            conn.request("POST", "/sms/2/text/advanced", payload, headers)
            res = conn.getresponse()
            data = res.read().decode("utf-8")

            if res.status in (200, 201):
                response_json = json.loads(data)
                messages = response_json.get("messages", [])
                if messages:
                    status = messages[0].get("status", {})
                    group_name = status.get("groupName", "")
                    description = status.get("description", "")
                    self.stdout.write(f"     Infobip status: {group_name} — {description}")
                    return group_name in ("PENDING", "DELIVERED")
                return True
            else:
                self.stdout.write(self.style.ERROR(f"     HTTP {res.status}: {data}"))
                return False
        finally:
            conn.close()

    def _indenter(self, texte: str, prefixe: str = "     | ") -> str:
        return "\n".join(prefixe + ligne for ligne in texte.splitlines())
