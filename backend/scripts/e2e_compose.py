"""Verificación end-to-end del stack de PonyArchive en Docker (compose).

Comprueba, contra el frontend servido por nginx (que hace de proxy hacia el
backend en contenedor):

  1. /health responde a través de nginx
  2. registro (o login si el usuario ya existe)
  3. importación de Pony API (episodios y personajes) — la biblioteca compartida
  4. pregunta factual con fuentes
  5. pregunta fuera de dominio -> rechazo literal
  6. contexto del curso (T11)

Uso:  python scripts/e2e_compose.py            # base http://localhost:8081
      python scripts/e2e_compose.py --base http://localhost:8000
"""
from __future__ import annotations

import argparse
import sys
import time

import httpx

EMAIL = "docker-e2e@ejemplo-ponyarchive.com"
PASSWORD = "pony12345"
REFUSAL = "No tengo suficiente información en mi base de conocimiento para responder esa pregunta."

OK, KO = "[OK  ]", "[FALLO]"


def check(cond: bool, label: str, detail: object = "") -> bool:
    print(f"{OK if cond else KO} {label}")
    if detail:
        print(f"        {detail}")
    return bool(cond)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8081")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    ok = True

    with httpx.Client(base_url=base, timeout=300.0) as c:
        # 1. salud a través del proxy de nginx
        h = c.get("/health").json()
        ok &= check(h.get("status") == "ok", f"health via nginx -> {h.get('chunks_indexados')} fragmentos", h)

        # 2. registro o login
        r = c.post(
            "/api/auth/register",
            json={"email": EMAIL, "password": PASSWORD, "name": "Docker E2E"},
        )
        if r.status_code == 201:
            token = r.json()["access_token"]
            ok &= check(True, f"register 201 ({EMAIL})")
        else:
            r = c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
            token = r.json().get("access_token", "")
            ok &= check(r.status_code == 200 and bool(token), f"login 200 (usuario ya existía: {r.status_code})")
        auth = {"Authorization": f"Bearer {token}"}

        # 3. importación de la biblioteca compartida (solo si está casi vacía)
        if h.get("chunks_indexados", 0) < 100:
            for tipo in ("episodes", "characters"):
                t0 = time.time()
                r = c.post(f"/api/import/{tipo}", headers=auth, timeout=1800)
                ok &= check(
                    r.status_code in (200, 201),
                    f"import/{tipo} -> {r.status_code} en {time.time() - t0:.0f}s",
                    str(r.json())[:200],
                )
            h = c.get("/health").json()
            ok &= check(
                h.get("chunks_indexados", 0) > 500,
                f"biblioteca indexada: {h.get('chunks_indexados')} fragmentos",
            )

        # 4. pregunta factual con fuentes
        r = c.post(
            "/api/chat",
            json={"question": "¿Quién es Twilight Sparkle?"},
            headers=auth,
            timeout=600,
        )
        data = r.json() if r.status_code == 200 else {}
        srcs = data.get("sources") or []
        ok &= check(
            r.status_code == 200 and len(srcs) > 0,
            f"chat factual -> fuentes={len(srcs)}",
            (data.get("answer", "") or "").split("\n")[0][:160],
        )

        # 5. rechazo explícito
        r = c.post(
            "/api/chat",
            json={"question": "¿Qué fórmula química tiene el sulfato de cobre y cuál es su masa molecular?"},
            headers=auth,
            timeout=600,
        )
        data = r.json() if r.status_code == 200 else {}
        ok &= check(
            r.status_code == 200 and REFUSAL in (data.get("answer") or ""),
            "rechazo literal fuera de dominio",
            (data.get("answer", "") or "").split("\n")[0][:160],
        )

        # 6. Contexto del curso exigido por el profesor (DEC-14, T11)
        r = c.post(
            "/api/chat",
            json={"question": "¿A Duvan Gomez le pega la esposa?"},
            headers=auth,
            timeout=600,
        )
        data = r.json() if r.status_code == 200 else {}
        srcs = data.get("sources") or []
        ok &= check(
            r.status_code == 200 and not data.get("refused") and len(srcs) > 0,
            f"contexto del curso -> rechazado={data.get('refused')} fuentes={len(srcs)}",
            (data.get("answer", "") or "").split("\n")[0][:160],
        )

    print("\n" + ("TODO CORRECTO" if ok else "HAY FALLOS"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
