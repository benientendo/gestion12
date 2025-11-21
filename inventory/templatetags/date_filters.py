from django import template
from datetime import datetime, timedelta
import locale
from decimal import Decimal, InvalidOperation

register = template.Library()

# Définir la locale en français
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'French_France.1252')
    except:
        pass

@register.filter
def format_date_vente(date_vente):
    """
    Formate la date de vente de manière intelligente:
    - Aujourd'hui: "Aujourd'hui à 14:30" (si datetime) ou "Aujourd'hui" (si date)
    - Cette semaine: "Vendredi 12/11/2025"
    - Plus ancien: "12/11/2025 à 14:30" (si datetime) ou "12/11/2025" (si date)
    """
    if not date_vente:
        return ""
    
    from datetime import date as date_type
    
    maintenant = datetime.now()
    aujourd_hui = maintenant.date()
    
    # Déterminer si c'est un datetime ou un date
    is_datetime = isinstance(date_vente, datetime)
    date_only = date_vente.date() if is_datetime else date_vente
    
    # Si c'est aujourd'hui
    if date_only == aujourd_hui:
        if is_datetime:
            return f"Aujourd'hui à {date_vente.strftime('%H:%M')}"
        return "Aujourd'hui"
    
    # Si c'est hier
    hier = aujourd_hui - timedelta(days=1)
    if date_only == hier:
        if is_datetime:
            return f"Hier à {date_vente.strftime('%H:%M')}"
        return "Hier"
    
    # Si c'est cette semaine (dans les 7 derniers jours)
    il_y_a_7_jours = aujourd_hui - timedelta(days=7)
    if date_only > il_y_a_7_jours:
        jours_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        jour_semaine = jours_fr[date_vente.weekday()]
        return f"{jour_semaine} {date_vente.strftime('%d/%m/%Y')}"
    
    # Pour les dates plus anciennes
    if is_datetime:
        return date_vente.strftime('%d/%m/%Y à %H:%M')
    return date_vente.strftime('%d/%m/%Y')


@register.filter
def group_period(date_vente):
    """
    Retourne la période de regroupement pour la date:
    - "Aujourd'hui"
    - "Hier"
    - "Cette semaine"
    - "Ce mois"
    - "Plus ancien"
    """
    if not date_vente:
        return "Date inconnue"
    
    maintenant = datetime.now()
    aujourd_hui = maintenant.date()
    
    # Déterminer si c'est un datetime ou un date
    is_datetime = isinstance(date_vente, datetime)
    date_only = date_vente.date() if is_datetime else date_vente
    
    # Aujourd'hui
    if date_only == aujourd_hui:
        return "Aujourd'hui"
    
    # Hier
    hier = aujourd_hui - timedelta(days=1)
    if date_only == hier:
        return "Hier"
    
    # Cette semaine (dans les 7 derniers jours)
    il_y_a_7_jours = aujourd_hui - timedelta(days=7)
    if date_only > il_y_a_7_jours:
        return "Cette semaine"
    
    # Ce mois
    if date_only.year == aujourd_hui.year and date_only.month == aujourd_hui.month:
        return "Ce mois"
    
    # Mois précédent
    mois_precedent = aujourd_hui.replace(day=1) - timedelta(days=1)
    if date_only.year == mois_precedent.year and date_only.month == mois_precedent.month:
        return "Mois précédent"
    
    # Plus ancien
    mois_fr = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
               'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    return f"{mois_fr[date_only.month - 1]} {date_only.year}"


@register.filter
def format_cdf(value, decimals=0):
    """Formate un montant en CDF avec des espaces entre milliers.

    Exemple: 1234567.89 -> "1 234 567.89"
    """
    if value is None:
        return "0"

    try:
        decimals = int(decimals)
    except (TypeError, ValueError):
        decimals = 0

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    formatted = f"{amount:,.{decimals}f}"
    # Remplacer les séparateurs de milliers par des espaces
    return formatted.replace(",", " ")
