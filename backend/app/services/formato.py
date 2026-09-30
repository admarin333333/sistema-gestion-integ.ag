def pesos(valor: float) -> str:
    """60000.0 -> "60.000,00" (formato argentino, no el inglés)."""
    texto = f"{valor:,.2f}"
    miles, _punto, centavos = texto.rpartition(".")
    return f"{miles.replace(',', '.')},{centavos}"
