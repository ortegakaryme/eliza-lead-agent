"""Send six sample leads (two each of Hot, Warm, Cold) to the /leads endpoint, plus one
request with a wrong secret to show that authentication works.

Usage:
    python scripts/send_test_leads.py                                  # local server
    python scripts/send_test_leads.py https://your-service.onrender.com # deployed

Reads WEBHOOK_SECRET from .env. The conversation IDs are fixed, so running the
script twice updates the same six Notion pages instead of creating duplicates.
"""
import os
import sys

import httpx
from dotenv import load_dotenv

SAMPLE_LEADS = {
    "Hot (decision maker + budget + moving in <= 3 months)": {
        "full_name": "Mariana Gómez Treviño",
        "phone": "5512345678",
        "email": "mariana@cafetal.mx",
        "company": "Café El Tal",
        "business_type": "restaurant",
        "property_type": "retail_unit",
        "operation": "lease",
        "space_m2": 120,
        "zone": "Roma Norte o Condesa, a pie de calle",
        "budget_min_mxn": 25000,
        "budget_max_mxn": 40000,
        "timeframe": "1_3_months",
        "decision_role": "decision_maker",
        "notes": "Segunda sucursal. Necesita salida de humo para cocina y visibilidad a la calle.",
        "conversation_id": "test-hot-001",
    },
    "Warm (decision maker + budget, but 3-6 months out)": {
        "full_name": "Ricardo Salinas Ortiz",
        "phone": "5598765432",
        "company": "Distribuidora RSO",
        "business_type": "industrial_logistics",
        "property_type": "warehouse",
        "operation": "lease",
        "space_m2": 800,
        "zone": "Zona industrial de Tlalnepantla o Cuautitlán",
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
        "zone": "Del Valle o Narvarte",
        "timeframe": "undefined",
        "decision_role": "researching_for_other",
        "notes": "Investiga opciones para un familiar médico; aún sin presupuesto definido.",
        "conversation_id": "test-cold-001",
    },
    "Hot by phone (caller ID only, immediate purchase, max budget only)": {
        "full_name": "Fernando Castañeda Rivas",
        "company": "Grupo Castañeda Agro",
        "business_type": "other",
        "property_type": "land",
        "operation": "purchase",
        "space_m2": 5000,
        "zone": "Tepotzotlán, cerca de la autopista México-Querétaro",
        "budget_max_mxn": 8500000,
        "timeframe": "immediate",
        "decision_role": "decision_maker",
        "notes": "Quiere cerrar compra este mes; pagaría de contado. Solo dio el número desde el que llamó.",
        "conversation_id": "test-hot-002",
        "caller_id": "+525555551234",
    },
    "Warm (influencer, spoken email with spaces, budget given backwards)": {
        "full_name": "Luis Pérez Mondragón",
        "phone": "55 5555 8890",
        "email": "Luis . Perez @ Gmail .com",
        "company": "Óptica Visión Clara",
        "business_type": "retail_store",
        "property_type": "retail_unit",
        "operation": "lease",
        "space_m2": 60,
        "zone": "Plaza comercial en Coyoacán o Insurgentes Sur",
        "budget_min_mxn": 30000,
        "budget_max_mxn": 18000,
        "timeframe": "1_3_months",
        "decision_role": "influencer",
        "notes": "Es gerente de sucursal; la dueña aprueba el contrato.",
        "conversation_id": "test-warm-002",
    },
    "Cold (decision maker, budget said as 0, unparseable email, 6+ months)": {
        "full_name": "Jorge Hernández Lara",
        "phone": "5511112233",
        "email": "jorge arroba hotmail",
        "company": "Despacho Hernández Lara",
        "business_type": "office",
        "property_type": "office",
        "operation": "lease",
        "space_m2": 90,
        "zone": "Polanco",
        "budget_min_mxn": 0,
        "timeframe": "6_plus_months",
        "decision_role": "decision_maker",
        "notes": "Su contrato actual vence el próximo año; solo está explorando precios.",
        "conversation_id": "test-cold-002",
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
