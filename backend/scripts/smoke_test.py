"""Prueba de humo del backend (V05/V06/T01/T04).

Uso (con el servidor arrancado en http://127.0.0.1:8000):
    python scripts/smoke_test.py

Comprueba: salud, registro, rechazo sin token, respuesta sustentada con fuentes,
rechazo explícito fuera de dominio e historial por usuario.
"""
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
EMAIL = f"demo{int(time.time())}@ejemplo-ponyarchive.com"
PASSWORD = "demo12345"


def wait_server(timeout: int = 90) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            if httpx.get(f"{BASE}/health", timeout=3).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit("El servidor no respondió en el tiempo esperado.")


def main() -> None:
    wait_server()
    results: list[tuple[str, bool, str]] = []

    # 1. Salud e indexado inicial
    health = httpx.get(f"{BASE}/health", timeout=30).json()
    results.append(("/health", health.get("status") == "ok", str(health)))

    # 2. Registro
    r = httpx.post(
        f"{BASE}/api/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "display_name": "Demo"},
        timeout=30,
    )
    token = r.json().get("access_token", "") if r.status_code == 201 else ""
    results.append(("register 201", r.status_code == 201, f"HTTP {r.status_code} {r.text[:200]}"))

    # 3. Endpoint de negocio sin token -> 401
    r = httpx.post(f"{BASE}/api/chat", json={"question": "¿Quién es Twilight Sparkle?"}, timeout=30)
    results.append(("chat sin token -> 401", r.status_code == 401, f"HTTP {r.status_code}"))

    headers = {"Authorization": f"Bearer {token}"}
    if not token:
        print("ABORTADO: no se obtuvo token, no se pueden probar los endpoints de negocio.")
        for name, ok, detail in results:
            print(f"[{'OK  ' if ok else 'FAIL'}] {name} — {detail}")
        sys.exit(1)

    # 4. Pregunta factual con respuesta en la biblioteca
    t0 = time.time()
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"question": "¿Quién es Twilight Sparkle?"},
        headers=headers,
        timeout=300,
    )
    body = r.json()
    elapsed = round(time.time() - t0, 1)
    ok = r.status_code == 200 and not body.get("refused") and body.get("sources")
    results.append((f"chat factual (T01, {elapsed}s)", ok, body.get("answer", "")[:400]))
    print("FUENTES:", [f"{s['title']} ({s['doc_type']}, similitud {s['score']})" for s in body.get("sources", [])])
    print("NOTAS:", body.get("retrieval_notes"))

    # 5. Pregunta fuera de dominio -> rechazo explícito
    # (Antes se usaba la receta de sushi: el perfil de Sunset Shimmer contiene la
    # ocupación "Sushi chef" y superaba el umbral, con lo que el caso dependía del
    # clasificador de intención. Con esta pregunta ninguna coincidencia llega al
    # umbral, así que el rechazo lo garantiza la estrategia E1 de forma estable.)
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"question": "¿Qué fórmula química tiene el sulfato de cobre y cuál es su masa molecular?"},
        headers=headers,
        timeout=300,
    )
    body = r.json()
    ok = body.get("refused") is True and "No tengo suficiente información" in body.get("answer", "")
    results.append(("rechazo fuera de dominio (T04)", ok, body.get("answer", "")[:200]))

    # 6. Pregunta dentro del dominio sin evidencia suficiente -> rechazo/aclaración
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"question": "¿Qué personaje secundario aparece en el capítulo 47 con un sombrero morado?"},
        headers=headers,
        timeout=300,
    )
    body = r.json()
    results.append(
        ("consulta sin evidencia (T05)", r.status_code == 200 and body.get("refused") is True,
         f"refused={body.get('refused')} | razón={body.get('refusal_reason')} | {body.get('answer','')[:150]}")
    )

    # 7. Historial
    r = httpx.get(f"{BASE}/api/chat/conversations", headers=headers, timeout=30)
    ok = r.status_code == 200 and len(r.json()) >= 1
    results.append(("historial por usuario (B04)", ok, f"{len(r.json())} conversación(ones)"))

    # 8. Carga de documento y pregunta que depende de ese documento (T07)
    contenido = (
        "FICHA DE PRUEBA - PonyArchive\n"
        "La cebra Zecora vive en el Bosque Everfree y prepara remedios con hierbas.\n"
        "El número de la amiga es el 42 según el archivo de prueba de PonyArchive.\n"
    )
    r = httpx.post(
        f"{BASE}/api/documents",
        files={"file": ("prueba_zecora.txt", contenido.encode("utf-8"), "text/plain")},
        headers=headers,
        timeout=120,
    )
    cargado = r.status_code == 201
    results.append(("carga de documento (K07/T07)", cargado, f"HTTP {r.status_code} {r.text[:150]}"))

    if cargado:
        r = httpx.post(
            f"{BASE}/api/chat",
            json={"question": "¿De qué se ocupa la cebra Zecora según el archivo de prueba?"},
            headers=headers,
            timeout=300,
        )
        body = r.json()
        ok = (not body.get("refused")) and "remedios" in body.get("answer", "").lower()
        results.append(("pregunta sobre documento cargado (T07)", ok, body.get("answer", "")[:300]))
        print("FUENTES T07:", [f"{s['title']} ({s['doc_type']})" for s in body.get("sources", [])])

    # 9. Aislamiento de documentos entre usuarios (T10/B05)
    r = httpx.post(
        f"{BASE}/api/auth/register",
        json={"email": f"intruso{int(time.time())}@ejemplo-ponyarchive.com", "password": PASSWORD},
        timeout=30,
    )
    token_otro = r.json().get("access_token", "")
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"question": "¿De qué se ocupa la cebra Zecora según el archivo de prueba?"},
        headers={"Authorization": f"Bearer {token_otro}"},
        timeout=300,
    )
    body = r.json()
    titulos = [s.get("title", "") for s in body.get("sources", [])]
    aislado = not any("prueba_zecora" in t for t in titulos)
    results.append(
        ("aislamiento de documentos (T10)", aislado,
         f"refused={body.get('refused')} | fuentes={titulos}")
    )

    # 9b. Aislamiento en el LISTADO de documentos (T10b/B05)
    h_otro = {"Authorization": f"Bearer {token_otro}"}
    r_all = httpx.get(f"{BASE}/api/documents?scope=all", headers=h_otro, timeout=60).json()
    r_mine = httpx.get(f"{BASE}/api/documents?scope=mine", headers=h_otro, timeout=60).json()
    items_all = r_all.get("items", [])
    items_mine = r_mine.get("items", [])
    titulos_listados = [d.get("title", "") for d in items_all]
    titulos_mios = [d.get("title", "") for d in items_mine]
    oculto = not any("prueba_zecora" in t for t in titulos_listados)
    oculto_en_mios = not any("prueba_zecora" in t for t in titulos_mios)
    results.append(
        ("listado aislado (T10b)",
         oculto and oculto_en_mios,
         f"scope=all: {len(items_all)} docs, 'prueba_zecora' visible={not oculto} | "
         f"scope=mine: {len(items_mine)} docs, visible={not oculto_en_mios}")
    )

    # 10. Contexto del curso (requisito del profesor: DEC-14, caso T11)
    r = httpx.post(
        f"{BASE}/api/chat",
        json={"question": "¿A Duvan Gomez le pega la esposa?"},
        headers=headers,
        timeout=300,
    )
    body = r.json()
    fuentes = [s.get("title", "") for s in body.get("sources", [])]
    ok = (
        (not body.get("refused"))
        and "duvan" in body.get("answer", "").lower()
        and any("duvan" in t.lower() for t in fuentes)
    )
    results.append(
        ("contexto del curso (T11)", ok,
         f"refused={body.get('refused')} | fuentes={fuentes} | {body.get('answer','')[:220]}")
    )

    print("\n================ RESULTADOS ================")
    failed = 0
    for name, ok, detail in results:
        mark = "OK  " if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{mark}] {name}\n        {detail}\n")
    print(f"TOTAL: {len(results) - failed}/{len(results)} pruebas superadas")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
