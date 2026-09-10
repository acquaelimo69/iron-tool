def fmt(val, decimali=0):
    """Formatta un numero in stile italiano: 1.234,56"""
    if decimali == 0:
        s = f"{round(val):,}"
    else:
        s = f"{val:,.{decimali}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
