from django import template

register = template.Library()


@register.filter
def format_number(value, separator=' '):
    """
    Formate un nombre avec des séparateurs de milliers.
    
    Usage:
        {{ montant|format_number }}        → 1 000 000
        {{ montant|format_number:"," }}    → 1,000,000
        {{ montant|format_number:"." }}    → 1.000.000
    """
    try:
        if value is None:
            return '0'
        
        # Convertir en nombre
        if isinstance(value, str):
            value = float(value.replace(',', '.').replace(' ', ''))
        
        # Arrondir à l'entier
        num = int(round(float(value)))
        
        # Formater avec séparateur
        is_negative = num < 0
        num = abs(num)
        
        result = ''
        num_str = str(num)
        
        for i, digit in enumerate(reversed(num_str)):
            if i > 0 and i % 3 == 0:
                result = separator + result
            result = digit + result
        
        if is_negative:
            result = '-' + result
        
        return result
    except (ValueError, TypeError):
        return str(value)


@register.filter
def format_number_decimal(value, decimals=2):
    """
    Formate un nombre avec séparateurs et décimales.
    
    Usage:
        {{ montant|format_number_decimal }}     → 1 000 000,00
        {{ montant|format_number_decimal:0 }}   → 1 000 000
    """
    try:
        if value is None:
            return '0'
        
        num = float(value)
        is_negative = num < 0
        num = abs(num)
        
        # Séparer partie entière et décimale
        int_part = int(num)
        dec_part = round((num - int_part) * (10 ** decimals))
        
        # Formater partie entière avec espaces
        int_str = ''
        int_part_str = str(int_part)
        for i, digit in enumerate(reversed(int_part_str)):
            if i > 0 and i % 3 == 0:
                int_str = ' ' + int_str
            int_str = digit + int_str
        
        # Ajouter décimales si demandé
        if decimals > 0:
            result = f"{int_str},{str(dec_part).zfill(decimals)}"
        else:
            result = int_str
        
        if is_negative:
            result = '-' + result
        
        return result
    except (ValueError, TypeError):
        return str(value)
