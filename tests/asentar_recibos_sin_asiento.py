"""Genera el asiento de los recibos que quedaron sin asentar.

Un recibo guardado NO mueve la cuenta: solo lo mueve su asiento. Este script
genera los que se pueden, y avisa con el motivo de los que no.

Uso:  python asentar_recibos_sin_asiento.py [--ver]
"""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"


def pedir(metodo, ruta, token=None, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            texto = r.read().decode()
            return r.status, json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:250]


def main():
    solo_ver = "--ver" in sys.argv
    _, tok = pedir("POST", "/api/auth/login",
                   cuerpo={"usuario": "admin", "password": "admin123"})
    token = tok["access_token"]

    _, recibos = pedir("GET", "/api/recibos", token)
    sin_asiento = [r for r in recibos if not r.get("id_asiento")
                   and r["estado"] == "emitido"]
    print(f"recibos emitidos sin asiento: {len(sin_asiento)}\n")

    _, plan = pedir("GET", "/api/plan-cuentas", token)
    nombres = {p["id_cuenta"]: f"{p['codigo']} {p['nombre']}" for p in plan}

    hechos = []
    for r in sin_asiento:
        pagos = r.get("pagos") or []
        if not pagos:
            continue  # los viejos, sin forma de pago: no se pueden asentar
        detalle = " + ".join(
            f"{nombres.get(p['cuenta_id'], '?')} {p['importe']:,.0f}" for p in pagos
        )
        st, res = pedir("GET", f"/api/recibos/{r['id']}/aplicaciones", token)
        aplicadas = sum(a["importe"] for a in (res or []))
        print(f"  recibo {r['numero']}  {r['cliente_nombre'][:26]:<26} "
              f"{r['importe']:>12,.2f}")
        print(f"      pagos:      {detalle}")
        print(f"      facturas:   {len(res or [])} · aplicado {aplicadas:,.2f}")

        if solo_ver:
            print()
            continue

        cod, respuesta = pedir("POST", f"/api/recibos/{r['id']}/asiento", token)
        if cod == 200 and respuesta.get("generado"):
            print(f"      -> ASENTADO  {respuesta['numero_completo']}")
            hechos.append(r["numero"])
        else:
            motivo = respuesta if isinstance(respuesta, str) else respuesta.get("detail")
            print(f"      -> NO se pudo asentar: {motivo}")
        print()

    if solo_ver:
        print("(--ver: no se generó nada)")
        return
    print(f"asentados: {len(hechos)}  {hechos}")


if __name__ == "__main__":
    main()