"""Send three sample leads (Hot, Warm, Cold) to the /leads endpoint, plus one
request with a wrong secret to show that authentication works.

Usage:
    python scripts/send_test_leads.py                                  # local server
    python scripts/send_test_leads.py https://your-service.onrender.com # deployed

Reads WEBHOOK_SECRET from .env. The conversation IDs are fixed, so running the
script twice updates the same three Notion pages instead of creating duplicates.
"""
import os
import sys

import httpx
from dotenv import load_dotenv

SAMPLE_LEADS = {
    "Hot (decision maker + budget + moving in <= 3 months)": {
        "full_name": "Mariana Gómez Treviño",
        "phone": "7221234567",
        "email": "mariana@cafetal.mx",
        "company": "Café El Tal",
        "business_type": "restaurant",
        "property_type": "retail_unit",
        "operation": "lease",
        "space_m2": 120,
        "zone": "Metepec, cerca del centro o Av. Tecnológico",
        "budget_min_mxn": 25000,
        "budget_max_mxn": 40000,
        "timeframe": "1_3_months",
        "decision_role": "decision_maker",
        "notes": "Segunda sucursal. Necesita salida de humo para cocina y visibilidad a la calle.",
        "conversation_id": "test-hot-001",
    },
    "Warm (decision maker + budget, but 3-6 months out)": {
        "full_name": "Ricardo Salinas Ortiz",
        "phone": "7229876543",
        "company": "Distribuidora RSO",
        "business_type": "industrial_logistics",
        "property_type": "warehouse",
        "operation": "lease",
        "space_m2": 800,
        "zone": "Corredor Toluca-Lerma",
        "budget_min_mxn": 60000,
        "budget_max_mxn": 90000,
        "timeframe": "3_6_months",
        "decision_role": "decision_maker",
        "notes": "Requiere acceso para tráiler y andén de carga.",
        "conversation_id": "test-warm-001",
    },
    "Cold (researching for someone else, no budget, no date)": {
        "full_name": "Daniela Ruiz",
        "email": "daniela.ruiz@correo.com",
        "business_type": "clinic",
        "property_type": "office",
        "operation": "purchase",
        "zone": "Toluca",
        "timeframe": "undefined",
        "decision_role": "researching_for_other",
        "notes": "Investiga opciones para un familiar médico; aún sin presupuesto definido.",
        "conversation_id": "test-cold-001",
    },
}


def main() -> None:
    load_dotenv()
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    secret = os.environ.get("WEBHOOK_SECRET")
    if not secret:
        sys.exit("WEBHOOK_SECRET is not set. Add it to .env first.")

    with httpx.Client(base_url=base_url, timeout=60) as client:
        # 60 s timeout: the first call to a sleeping free-tier server can take a while.
        for label, payload in SAMPLE_LEADS.items():
            r = client.post("/leads", json=payload, headers={"X-Webhook-Secret": secret})
            print(f"\n=== {label}\nHTTP {r.status_code}")
            print(r.json())

        r = client.post("/leads", json=SAMPLE_LEADS[next(iter(SAMPLE_LEADS))],
                        headers={"X-Webhook-Secret": "wrong-secret"})
        print(f"\n=== Wrong secret (expect 401)\nHTTP {r.status_code} {r.json()}")


if __name__ == "__main__":
    main()
