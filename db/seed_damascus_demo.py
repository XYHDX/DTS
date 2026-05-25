#!/usr/bin/env python3
"""
Damascus Transit System — Demo Seed Script
Seeds the Supabase database with realistic Damascus transit data via PostgREST API.

Usage:
    python db/seed_damascus_demo.py              # uses .env for credentials
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python db/seed_damascus_demo.py

Requirements: httpx, python-dotenv (both already in requirements.txt)
"""

import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

# Lazy-initialized at runtime (not on import)
HEADERS: dict = {}
BASE: str = ""
CLIENT: httpx.Client | None = None


def _init_client():
    global HEADERS, BASE, CLIENT
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        print("  export SUPABASE_URL=https://your-project.supabase.co")
        print("  export SUPABASE_SERVICE_KEY=your-service-role-key")
        sys.exit(1)
    HEADERS = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }
    BASE = f"{url}/rest/v1"
    CLIENT = httpx.Client(timeout=30.0, headers=HEADERS)


def upsert(table: str, rows: list[dict], on_conflict: str | None = None) -> list:
    """Insert rows; merge on conflict for idempotency."""
    headers = dict(HEADERS)
    if on_conflict:
        headers["Prefer"] = f"return=representation,resolution=merge-duplicates"
    resp = CLIENT.post(f"{BASE}/{table}", json=rows, headers=headers)
    if resp.status_code >= 400:
        print(f"  ERROR inserting into {table}: {resp.status_code} {resp.text[:300]}")
        return []
    return resp.json() if resp.content else []


def rpc(func_name: str, params: dict):
    resp = CLIENT.post(f"{SUPABASE_URL}/rest/v1/rpc/{func_name}", json=params)
    if resp.status_code >= 400:
        print(f"  ERROR calling {func_name}: {resp.status_code} {resp.text[:300]}")
        return None
    return resp.json() if resp.content else None


def get(table: str, params: str = "") -> list:
    resp = CLIENT.get(f"{BASE}/{table}?{params}")
    if resp.status_code >= 400:
        return []
    data = resp.json()
    return data if isinstance(data, list) else [data] if data else []


def patch(table: str, filter_params: str, data: dict) -> list:
    resp = CLIENT.patch(f"{BASE}/{table}?{filter_params}", json=data)
    if resp.status_code >= 400:
        print(f"  ERROR patching {table}: {resp.status_code} {resp.text[:300]}")
        return []
    result = resp.json() if resp.content else []
    return result if isinstance(result, list) else [result] if result else []


# ============================================================
# STOPS — 54 real Damascus locations
# ============================================================

STOPS = [
    # Core city
    {
        "stop_id": "S001",
        "name": "Marjeh Square",
        "name_ar": "ساحة المرجة",
        "lon": 36.3025,
        "lat": 33.5105,
        "shelter": True,
    },
    {
        "stop_id": "S002",
        "name": "Hamidiyeh Souq",
        "name_ar": "سوق الحميدية",
        "lon": 36.3065,
        "lat": 33.5115,
        "shelter": True,
    },
    {
        "stop_id": "S003",
        "name": "Umayyad Square",
        "name_ar": "ساحة الأمويين",
        "lon": 36.2920,
        "lat": 33.5130,
        "shelter": True,
    },
    {
        "stop_id": "S004",
        "name": "Baramkeh",
        "name_ar": "البرامكة",
        "lon": 36.2940,
        "lat": 33.5060,
        "shelter": True,
    },
    {
        "stop_id": "S005",
        "name": "Mezzeh Highway",
        "name_ar": "أوتوستراد المزة",
        "lon": 36.2600,
        "lat": 33.5050,
        "shelter": True,
    },
    {
        "stop_id": "S006",
        "name": "Mezzeh 86",
        "name_ar": "مزة 86",
        "lon": 36.2450,
        "lat": 33.5010,
        "shelter": False,
    },
    {
        "stop_id": "S007",
        "name": "Kafar Souseh",
        "name_ar": "كفرسوسة",
        "lon": 36.2750,
        "lat": 33.5020,
        "shelter": True,
    },
    {
        "stop_id": "S008",
        "name": "Malki",
        "name_ar": "المالكي",
        "lon": 36.2800,
        "lat": 33.5170,
        "shelter": False,
    },
    {
        "stop_id": "S009",
        "name": "Abu Rummaneh",
        "name_ar": "أبو رمانة",
        "lon": 36.2850,
        "lat": 33.5160,
        "shelter": True,
    },
    {
        "stop_id": "S010",
        "name": "Muhajirin",
        "name_ar": "المهاجرين",
        "lon": 36.2880,
        "lat": 33.5210,
        "shelter": False,
    },
    {
        "stop_id": "S011",
        "name": "Saroujah",
        "name_ar": "الصالحية",
        "lon": 36.3050,
        "lat": 33.5180,
        "shelter": True,
    },
    {
        "stop_id": "S012",
        "name": "Jisr al-Abyad",
        "name_ar": "جسر الأبيض",
        "lon": 36.3080,
        "lat": 33.5200,
        "shelter": False,
    },
    {
        "stop_id": "S013",
        "name": "Abbasiyyin Square",
        "name_ar": "ساحة العباسيين",
        "lon": 36.3200,
        "lat": 33.5175,
        "shelter": True,
    },
    {
        "stop_id": "S014",
        "name": "Jobar",
        "name_ar": "جوبر",
        "lon": 36.3350,
        "lat": 33.5220,
        "shelter": False,
    },
    {
        "stop_id": "S015",
        "name": "Qaboun",
        "name_ar": "القابون",
        "lon": 36.3400,
        "lat": 33.5350,
        "shelter": False,
    },
    {
        "stop_id": "S016",
        "name": "Barzeh",
        "name_ar": "برزة",
        "lon": 36.3180,
        "lat": 33.5450,
        "shelter": True,
    },
    {
        "stop_id": "S017",
        "name": "Tishreen Park",
        "name_ar": "حديقة تشرين",
        "lon": 36.3100,
        "lat": 33.5250,
        "shelter": True,
    },
    {
        "stop_id": "S018",
        "name": "Damascus University",
        "name_ar": "جامعة دمشق",
        "lon": 36.2880,
        "lat": 33.5130,
        "shelter": True,
    },
    {
        "stop_id": "S019",
        "name": "Rawda",
        "name_ar": "الروضة",
        "lon": 36.2960,
        "lat": 33.5140,
        "shelter": False,
    },
    {
        "stop_id": "S020",
        "name": "Sha'lan",
        "name_ar": "الشعلان",
        "lon": 36.2900,
        "lat": 33.5155,
        "shelter": True,
    },
    {
        "stop_id": "S021",
        "name": "Mazraa",
        "name_ar": "المزرعة",
        "lon": 36.2830,
        "lat": 33.5030,
        "shelter": False,
    },
    {
        "stop_id": "S022",
        "name": "Western Bus Station",
        "name_ar": "المحطة الغربية (السومرية)",
        "lon": 36.2350,
        "lat": 33.5000,
        "shelter": True,
    },
    {
        "stop_id": "S023",
        "name": "Daraya Junction",
        "name_ar": "مفرق داريا",
        "lon": 36.2400,
        "lat": 33.4950,
        "shelter": False,
    },
    {
        "stop_id": "S024",
        "name": "Moadamiyeh",
        "name_ar": "المعضمية",
        "lon": 36.2200,
        "lat": 33.4800,
        "shelter": True,
    },
    {
        "stop_id": "S025",
        "name": "Harasta",
        "name_ar": "حرستا",
        "lon": 36.3550,
        "lat": 33.5500,
        "shelter": True,
    },
    {
        "stop_id": "S026",
        "name": "Douma Entrance",
        "name_ar": "مدخل دوما",
        "lon": 36.3800,
        "lat": 33.5600,
        "shelter": True,
    },
    {
        "stop_id": "S027",
        "name": "Jaramana",
        "name_ar": "جرمانا",
        "lon": 36.3300,
        "lat": 33.4900,
        "shelter": True,
    },
    {
        "stop_id": "S028",
        "name": "Sayyidah Zaynab",
        "name_ar": "السيدة زينب",
        "lon": 36.3400,
        "lat": 33.4500,
        "shelter": True,
    },
    {
        "stop_id": "S029",
        "name": "Airport Road",
        "name_ar": "طريق المطار",
        "lon": 36.3500,
        "lat": 33.4700,
        "shelter": False,
    },
    {
        "stop_id": "S030",
        "name": "Dwel'a",
        "name_ar": "الدويلعة",
        "lon": 36.3250,
        "lat": 33.4850,
        "shelter": False,
    },
    {
        "stop_id": "S031",
        "name": "Midan",
        "name_ar": "الميدان",
        "lon": 36.3000,
        "lat": 33.4950,
        "shelter": True,
    },
    {
        "stop_id": "S032",
        "name": "Zahira",
        "name_ar": "الظاهرة",
        "lon": 36.2970,
        "lat": 33.4970,
        "shelter": False,
    },
    {
        "stop_id": "S033",
        "name": "Bab Touma",
        "name_ar": "باب توما",
        "lon": 36.3150,
        "lat": 33.5130,
        "shelter": True,
    },
    {
        "stop_id": "S034",
        "name": "Bab Sharqi",
        "name_ar": "باب شرقي",
        "lon": 36.3200,
        "lat": 33.5120,
        "shelter": True,
    },
    {
        "stop_id": "S035",
        "name": "Old City Center",
        "name_ar": "وسط المدينة القديمة",
        "lon": 36.3100,
        "lat": 33.5110,
        "shelter": True,
    },
    {
        "stop_id": "S036",
        "name": "Kassaa",
        "name_ar": "القصاع",
        "lon": 36.3180,
        "lat": 33.5160,
        "shelter": False,
    },
    {
        "stop_id": "S037",
        "name": "Tijara Center",
        "name_ar": "مركز التجارة",
        "lon": 36.2950,
        "lat": 33.5100,
        "shelter": True,
    },
    {
        "stop_id": "S038",
        "name": "Mezze Autostrad West",
        "name_ar": "المزة أوتوستراد غرب",
        "lon": 36.2500,
        "lat": 33.5030,
        "shelter": False,
    },
    {
        "stop_id": "S039",
        "name": "Dummar",
        "name_ar": "دمر",
        "lon": 36.2300,
        "lat": 33.5150,
        "shelter": True,
    },
    {
        "stop_id": "S040",
        "name": "Qudsaya Entrance",
        "name_ar": "مدخل قدسيا",
        "lon": 36.2150,
        "lat": 33.5200,
        "shelter": False,
    },
    {
        "stop_id": "S041",
        "name": "Rabweh",
        "name_ar": "الربوة",
        "lon": 36.2700,
        "lat": 33.5180,
        "shelter": True,
    },
    {
        "stop_id": "S042",
        "name": "Muhajireen Heights",
        "name_ar": "أعالي المهاجرين",
        "lon": 36.2860,
        "lat": 33.5250,
        "shelter": False,
    },
    # Additional stops (S043-S054) — reaching 54 total
    {
        "stop_id": "S043",
        "name": "Tabbaleh",
        "name_ar": "الطبالة",
        "lon": 36.3050,
        "lat": 33.4980,
        "shelter": False,
    },
    {
        "stop_id": "S044",
        "name": "Shaghour",
        "name_ar": "الشاغور",
        "lon": 36.3120,
        "lat": 33.5050,
        "shelter": True,
    },
    {
        "stop_id": "S045",
        "name": "Bab Mousalla",
        "name_ar": "باب مصلى",
        "lon": 36.3080,
        "lat": 33.4920,
        "shelter": True,
    },
    {
        "stop_id": "S046",
        "name": "Qadam",
        "name_ar": "القدم",
        "lon": 36.3050,
        "lat": 33.4870,
        "shelter": False,
    },
    {
        "stop_id": "S047",
        "name": "Salhiyeh",
        "name_ar": "الصالحية",
        "lon": 36.2920,
        "lat": 33.5190,
        "shelter": True,
    },
    {
        "stop_id": "S048",
        "name": "Mezzeh Villas",
        "name_ar": "فيلات المزة",
        "lon": 36.2550,
        "lat": 33.5080,
        "shelter": False,
    },
    {
        "stop_id": "S049",
        "name": "Barada Bridge",
        "name_ar": "جسر بردى",
        "lon": 36.2980,
        "lat": 33.5120,
        "shelter": True,
    },
    {
        "stop_id": "S050",
        "name": "Arnous Square",
        "name_ar": "ساحة الأرنؤوس",
        "lon": 36.2930,
        "lat": 33.5110,
        "shelter": True,
    },
    {
        "stop_id": "S051",
        "name": "Yusuf al-Azmeh Square",
        "name_ar": "ساحة يوسف العظمة",
        "lon": 36.2870,
        "lat": 33.5140,
        "shelter": True,
    },
    {
        "stop_id": "S052",
        "name": "Jisr al-Raees",
        "name_ar": "جسر الرئيس",
        "lon": 36.2810,
        "lat": 33.5100,
        "shelter": False,
    },
    {
        "stop_id": "S053",
        "name": "Mazze Military Hospital",
        "name_ar": "مشفى المزة العسكري",
        "lon": 36.2650,
        "lat": 33.5060,
        "shelter": True,
    },
    {
        "stop_id": "S054",
        "name": "Kafar Souseh Flyover",
        "name_ar": "جسر كفرسوسة",
        "lon": 36.2780,
        "lat": 33.5040,
        "shelter": False,
    },
]

# ============================================================
# ROUTES — 8 Damascus corridors with polylines
# ============================================================

ROUTES = [
    {
        "route_id": "R001",
        "name": "Marjeh → Mezzeh Highway",
        "name_ar": "المرجة → أوتوستراد المزة",
        "route_type": "bus",
        "color": "#428177",
        "distance_km": 8.5,
        "avg_duration_min": 35,
        "fare_syp": 2000,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.3025, 33.5105],  # Marjeh
                [36.2990, 33.5100],
                [36.2950, 33.5100],  # Tijara Center
                [36.2940, 33.5060],  # Baramkeh
                [36.2900, 33.5040],
                [36.2830, 33.5030],
                [36.2750, 33.5020],  # Kafar Souseh
                [36.2650, 33.5060],
                [36.2600, 33.5050],  # Mezzeh Highway
                [36.2500, 33.5030],  # Mezze Autostrad West
                [36.2450, 33.5010],  # Mezzeh 86
            ],
        },
    },
    {
        "route_id": "R002",
        "name": "Baramkeh → Barzeh",
        "name_ar": "البرامكة → برزة",
        "route_type": "bus",
        "color": "#054239",
        "distance_km": 12.0,
        "avg_duration_min": 45,
        "fare_syp": 2500,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.2940, 33.5060],  # Baramkeh
                [36.2930, 33.5090],
                [36.2920, 33.5130],  # Umayyad Square
                [36.2950, 33.5160],
                [36.3050, 33.5180],  # Saroujah
                [36.3080, 33.5200],
                [36.3100, 33.5250],  # Tishreen Park
                [36.3150, 33.5220],
                [36.3200, 33.5175],  # Abbasiyyin
                [36.3190, 33.5300],
                [36.3180, 33.5450],  # Barzeh
                [36.3350, 33.5480],
                [36.3550, 33.5500],  # Harasta
            ],
        },
    },
    {
        "route_id": "R003",
        "name": "Umayyad → Qaboun",
        "name_ar": "الأمويين → القابون",
        "route_type": "bus",
        "color": "#002623",
        "distance_km": 10.5,
        "avg_duration_min": 40,
        "fare_syp": 2000,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.2920, 33.5130],  # Umayyad Square
                [36.2960, 33.5140],  # Rawda
                [36.3000, 33.5160],
                [36.3050, 33.5180],  # Saroujah
                [36.3100, 33.5180],
                [36.3200, 33.5175],  # Abbasiyyin
                [36.3280, 33.5200],
                [36.3350, 33.5220],  # Jobar
                [36.3380, 33.5280],
                [36.3400, 33.5350],  # Qaboun
                [36.3480, 33.5420],
                [36.3550, 33.5500],  # Harasta
            ],
        },
    },
    {
        "route_id": "R004",
        "name": "Old City → Jaramana",
        "name_ar": "المدينة القديمة → جرمانا",
        "route_type": "microbus",
        "color": "#b9a779",
        "distance_km": 9.0,
        "avg_duration_min": 35,
        "fare_syp": 3000,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.3100, 33.5110],  # Old City Center
                [36.3150, 33.5115],
                [36.3200, 33.5120],  # Bab Sharqi
                [36.3150, 33.5130],  # Bab Touma
                [36.3180, 33.5160],  # Kassaa
                [36.3220, 33.5100],
                [36.3250, 33.4980],
                [36.3250, 33.4850],  # Dwel'a
                [36.3280, 33.4880],
                [36.3300, 33.4900],  # Jaramana
                [36.3350, 33.4700],
                [36.3400, 33.4500],  # Sayyidah Zaynab
            ],
        },
    },
    {
        "route_id": "R005",
        "name": "Marjeh → Sayyidah Zaynab",
        "name_ar": "المرجة → السيدة زينب",
        "route_type": "bus",
        "color": "#988561",
        "distance_km": 18.0,
        "avg_duration_min": 55,
        "fare_syp": 3500,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.3025, 33.5105],  # Marjeh
                [36.3020, 33.5050],
                [36.3010, 33.5000],
                [36.3000, 33.4950],  # Midan
                [36.2970, 33.4970],  # Zahira
                [36.3050, 33.4920],
                [36.3100, 33.4880],
                [36.3250, 33.4850],  # Dwel'a
                [36.3300, 33.4900],  # Jaramana
                [36.3400, 33.4800],
                [36.3500, 33.4700],  # Airport Road
                [36.3450, 33.4600],
                [36.3400, 33.4500],  # Sayyidah Zaynab
            ],
        },
    },
    {
        "route_id": "R006",
        "name": "Muhajirin → Kafar Souseh",
        "name_ar": "المهاجرين → كفرسوسة",
        "route_type": "microbus",
        "color": "#6b1f2a",
        "distance_km": 6.5,
        "avg_duration_min": 25,
        "fare_syp": 2500,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.2880, 33.5210],  # Muhajirin
                [36.2860, 33.5190],
                [36.2850, 33.5160],  # Abu Rummaneh
                [36.2820, 33.5170],
                [36.2800, 33.5170],  # Malki
                [36.2850, 33.5155],
                [36.2900, 33.5155],  # Sha'lan
                [36.2880, 33.5130],  # Damascus University
                [36.2850, 33.5080],
                [36.2830, 33.5030],  # Mazraa
                [36.2780, 33.5020],
                [36.2750, 33.5020],  # Kafar Souseh
            ],
        },
    },
    {
        "route_id": "R007",
        "name": "Abbasiyyin → Harasta",
        "name_ar": "العباسيين → حرستا",
        "route_type": "bus",
        "color": "#4a151e",
        "distance_km": 8.0,
        "avg_duration_min": 30,
        "fare_syp": 2000,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.3200, 33.5175],  # Abbasiyyin
                [36.3280, 33.5200],
                [36.3350, 33.5220],  # Jobar
                [36.3380, 33.5290],
                [36.3400, 33.5350],  # Qaboun
                [36.3350, 33.5400],
                [36.3180, 33.5450],  # Barzeh
                [36.3300, 33.5470],
                [36.3550, 33.5500],  # Harasta
                [36.3680, 33.5550],
                [36.3800, 33.5600],  # Douma Entrance
            ],
        },
    },
    {
        "route_id": "R008",
        "name": "Mezzeh → Dummar",
        "name_ar": "المزة → دمر",
        "route_type": "microbus",
        "color": "#3d3a3b",
        "distance_km": 11.0,
        "avg_duration_min": 40,
        "fare_syp": 3000,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [36.2600, 33.5050],  # Mezzeh Highway
                [36.2550, 33.5040],
                [36.2500, 33.5030],  # Mezze Autostrad West
                [36.2550, 33.5080],
                [36.2600, 33.5120],
                [36.2700, 33.5180],  # Rabweh
                [36.2550, 33.5160],
                [36.2400, 33.5150],
                [36.2300, 33.5150],  # Dummar
                [36.2200, 33.5180],
                [36.2150, 33.5200],  # Qudsaya Entrance
                [36.2350, 33.5000],  # Western Bus Station
            ],
        },
    },
]

# ============================================================
# ROUTE-STOP ASSIGNMENTS
# ============================================================

ROUTE_STOPS = {
    "R001": [
        ("S001", 1, 0.0, 0),
        ("S037", 2, 1.2, 5),
        ("S004", 3, 2.5, 10),
        ("S054", 4, 3.8, 14),
        ("S007", 5, 4.8, 18),
        ("S053", 6, 5.8, 22),
        ("S005", 7, 6.8, 28),
        ("S038", 8, 7.5, 30),
        ("S006", 9, 8.5, 35),
    ],
    "R002": [
        ("S004", 1, 0.0, 0),
        ("S003", 2, 1.8, 8),
        ("S011", 3, 3.5, 15),
        ("S017", 4, 5.0, 22),
        ("S013", 5, 7.0, 30),
        ("S016", 6, 9.5, 40),
        ("S025", 7, 12.0, 45),
    ],
    "R003": [
        ("S003", 1, 0.0, 0),
        ("S019", 2, 1.0, 6),
        ("S011", 3, 2.5, 12),
        ("S013", 4, 4.5, 20),
        ("S014", 5, 6.5, 28),
        ("S015", 6, 8.5, 36),
        ("S025", 7, 10.5, 40),
    ],
    "R004": [
        ("S035", 1, 0.0, 0),
        ("S034", 2, 0.8, 5),
        ("S033", 3, 1.5, 10),
        ("S036", 4, 2.5, 15),
        ("S044", 5, 3.8, 19),
        ("S030", 6, 5.0, 22),
        ("S027", 7, 7.0, 30),
        ("S028", 8, 9.0, 35),
    ],
    "R005": [
        ("S001", 1, 0.0, 0),
        ("S043", 2, 2.0, 8),
        ("S031", 3, 3.5, 12),
        ("S032", 4, 4.0, 15),
        ("S045", 5, 5.5, 20),
        ("S030", 6, 8.0, 28),
        ("S027", 7, 10.0, 35),
        ("S029", 8, 14.0, 45),
        ("S028", 9, 18.0, 55),
    ],
    "R006": [
        ("S010", 1, 0.0, 0),
        ("S009", 2, 0.8, 4),
        ("S008", 3, 1.5, 8),
        ("S020", 4, 2.5, 12),
        ("S018", 5, 3.5, 16),
        ("S021", 6, 4.8, 20),
        ("S054", 7, 5.5, 22),
        ("S007", 8, 6.5, 25),
    ],
    "R007": [
        ("S013", 1, 0.0, 0),
        ("S014", 2, 1.5, 8),
        ("S015", 3, 3.5, 16),
        ("S016", 4, 5.0, 22),
        ("S025", 5, 6.5, 28),
        ("S026", 6, 8.0, 30),
    ],
    "R008": [
        ("S005", 1, 0.0, 0),
        ("S038", 2, 1.5, 6),
        ("S048", 3, 2.5, 10),
        ("S041", 4, 4.0, 14),
        ("S039", 5, 7.0, 28),
        ("S040", 6, 9.0, 36),
        ("S022", 7, 11.0, 40),
    ],
}

# ============================================================
# VEHICLES — 24 across fleet
# ============================================================

VEHICLES = [
    # Buses (12)
    {
        "vehicle_id": "BUS-001",
        "name": "Bus Damascus 001",
        "name_ar": "باص دمشق 001",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R001",
    },
    {
        "vehicle_id": "BUS-002",
        "name": "Bus Damascus 002",
        "name_ar": "باص دمشق 002",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R001",
    },
    {
        "vehicle_id": "BUS-003",
        "name": "Bus Damascus 003",
        "name_ar": "باص دمشق 003",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R002",
    },
    {
        "vehicle_id": "BUS-004",
        "name": "Bus Damascus 004",
        "name_ar": "باص دمشق 004",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R002",
    },
    {
        "vehicle_id": "BUS-005",
        "name": "Bus Damascus 005",
        "name_ar": "باص دمشق 005",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R003",
    },
    {
        "vehicle_id": "BUS-006",
        "name": "Bus Damascus 006",
        "name_ar": "باص دمشق 006",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R003",
    },
    {
        "vehicle_id": "BUS-007",
        "name": "Bus Damascus 007",
        "name_ar": "باص دمشق 007",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R005",
    },
    {
        "vehicle_id": "BUS-008",
        "name": "Bus Damascus 008",
        "name_ar": "باص دمشق 008",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R005",
    },
    {
        "vehicle_id": "BUS-009",
        "name": "Bus Damascus 009",
        "name_ar": "باص دمشق 009",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "active",
        "route": "R007",
    },
    {
        "vehicle_id": "BUS-010",
        "name": "Bus Damascus 010",
        "name_ar": "باص دمشق 010",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "idle",
        "route": None,
    },
    {
        "vehicle_id": "BUS-011",
        "name": "Bus Damascus 011",
        "name_ar": "باص دمشق 011",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "maintenance",
        "route": None,
    },
    {
        "vehicle_id": "BUS-012",
        "name": "Bus Damascus 012",
        "name_ar": "باص دمشق 012",
        "vehicle_type": "bus",
        "capacity": 45,
        "status": "idle",
        "route": None,
    },
    # Microbuses (8)
    {
        "vehicle_id": "MIC-001",
        "name": "Microbus 001",
        "name_ar": "ميكروباص 001",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "active",
        "route": "R004",
    },
    {
        "vehicle_id": "MIC-002",
        "name": "Microbus 002",
        "name_ar": "ميكروباص 002",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "active",
        "route": "R004",
    },
    {
        "vehicle_id": "MIC-003",
        "name": "Microbus 003",
        "name_ar": "ميكروباص 003",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "active",
        "route": "R006",
    },
    {
        "vehicle_id": "MIC-004",
        "name": "Microbus 004",
        "name_ar": "ميكروباص 004",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "active",
        "route": "R006",
    },
    {
        "vehicle_id": "MIC-005",
        "name": "Microbus 005",
        "name_ar": "ميكروباص 005",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "active",
        "route": "R008",
    },
    {
        "vehicle_id": "MIC-006",
        "name": "Microbus 006",
        "name_ar": "ميكروباص 006",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "active",
        "route": "R008",
    },
    {
        "vehicle_id": "MIC-007",
        "name": "Microbus 007",
        "name_ar": "ميكروباص 007",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "idle",
        "route": None,
    },
    {
        "vehicle_id": "MIC-008",
        "name": "Microbus 008",
        "name_ar": "ميكروباص 008",
        "vehicle_type": "microbus",
        "capacity": 14,
        "status": "idle",
        "route": None,
    },
    # Taxis (4)
    {
        "vehicle_id": "TAX-001",
        "name": "Taxi 001",
        "name_ar": "تاكسي 001",
        "vehicle_type": "taxi",
        "capacity": 4,
        "status": "active",
        "route": None,
    },
    {
        "vehicle_id": "TAX-002",
        "name": "Taxi 002",
        "name_ar": "تاكسي 002",
        "vehicle_type": "taxi",
        "capacity": 4,
        "status": "active",
        "route": None,
    },
    {
        "vehicle_id": "TAX-003",
        "name": "Taxi 003",
        "name_ar": "تاكسي 003",
        "vehicle_type": "taxi",
        "capacity": 4,
        "status": "active",
        "route": None,
    },
    {
        "vehicle_id": "TAX-004",
        "name": "Taxi 004",
        "name_ar": "تاكسي 004",
        "vehicle_type": "taxi",
        "capacity": 4,
        "status": "idle",
        "route": None,
    },
]

# ============================================================
# USERS — admin, dispatcher, 18 drivers
# ============================================================

USERS = [
    {
        "email": "admin@damascustransit.sy",
        "full_name": "System Admin",
        "full_name_ar": "مدير النظام",
        "role": "admin",
        "phone": "+963000000001",
    },
    {
        "email": "dispatcher@damascustransit.sy",
        "full_name": "Operations Center",
        "full_name_ar": "مركز العمليات",
        "role": "dispatcher",
        "phone": "+963000000002",
    },
    {
        "email": "driver01@damascustransit.sy",
        "full_name": "Ahmad Khalil",
        "full_name_ar": "أحمد خليل",
        "role": "driver",
        "phone": "+963110000001",
    },
    {
        "email": "driver02@damascustransit.sy",
        "full_name": "Omar Sayed",
        "full_name_ar": "عمر سيد",
        "role": "driver",
        "phone": "+963110000002",
    },
    {
        "email": "driver03@damascustransit.sy",
        "full_name": "Hassan Nouri",
        "full_name_ar": "حسن نوري",
        "role": "driver",
        "phone": "+963110000003",
    },
    {
        "email": "driver04@damascustransit.sy",
        "full_name": "Sami Darwish",
        "full_name_ar": "سامي درويش",
        "role": "driver",
        "phone": "+963110000004",
    },
    {
        "email": "driver05@damascustransit.sy",
        "full_name": "Fadi Haddad",
        "full_name_ar": "فادي حداد",
        "role": "driver",
        "phone": "+963110000005",
    },
    {
        "email": "driver06@damascustransit.sy",
        "full_name": "Khaled Mansour",
        "full_name_ar": "خالد منصور",
        "role": "driver",
        "phone": "+963110000006",
    },
    {
        "email": "driver07@damascustransit.sy",
        "full_name": "Youssef Amin",
        "full_name_ar": "يوسف أمين",
        "role": "driver",
        "phone": "+963110000007",
    },
    {
        "email": "driver08@damascustransit.sy",
        "full_name": "Rami Jabr",
        "full_name_ar": "رامي جبر",
        "role": "driver",
        "phone": "+963110000008",
    },
    {
        "email": "driver09@damascustransit.sy",
        "full_name": "Nizar Shami",
        "full_name_ar": "نزار شامي",
        "role": "driver",
        "phone": "+963110000009",
    },
    {
        "email": "driver10@damascustransit.sy",
        "full_name": "Tariq Bazzi",
        "full_name_ar": "طارق بزي",
        "role": "driver",
        "phone": "+963110000010",
    },
    {
        "email": "driver11@damascustransit.sy",
        "full_name": "Bilal Hamdi",
        "full_name_ar": "بلال حمدي",
        "role": "driver",
        "phone": "+963110000011",
    },
    {
        "email": "driver12@damascustransit.sy",
        "full_name": "Wael Khoury",
        "full_name_ar": "وائل خوري",
        "role": "driver",
        "phone": "+963110000012",
    },
    {
        "email": "driver13@damascustransit.sy",
        "full_name": "Mazen Rida",
        "full_name_ar": "مازن رضا",
        "role": "driver",
        "phone": "+963110000013",
    },
    {
        "email": "driver14@damascustransit.sy",
        "full_name": "Adel Fayad",
        "full_name_ar": "عادل فياض",
        "role": "driver",
        "phone": "+963110000014",
    },
    {
        "email": "driver15@damascustransit.sy",
        "full_name": "Samir Qasim",
        "full_name_ar": "سمير قاسم",
        "role": "driver",
        "phone": "+963110000015",
    },
    {
        "email": "driver16@damascustransit.sy",
        "full_name": "Jamil Sabbagh",
        "full_name_ar": "جميل صباغ",
        "role": "driver",
        "phone": "+963110000016",
    },
    {
        "email": "driver17@damascustransit.sy",
        "full_name": "Hani Tlass",
        "full_name_ar": "هاني طلاس",
        "role": "driver",
        "phone": "+963110000017",
    },
    {
        "email": "driver18@damascustransit.sy",
        "full_name": "Ziad Farah",
        "full_name_ar": "زياد فرح",
        "role": "driver",
        "phone": "+963110000018",
    },
]

# Driver → vehicle assignments (by email suffix → vehicle_id)
DRIVER_ASSIGNMENTS = {
    "driver01": "BUS-001",
    "driver02": "BUS-002",
    "driver03": "BUS-003",
    "driver04": "BUS-004",
    "driver05": "BUS-005",
    "driver06": "BUS-006",
    "driver07": "BUS-007",
    "driver08": "BUS-008",
    "driver09": "BUS-009",
    "driver10": "MIC-001",
    "driver11": "MIC-002",
    "driver12": "MIC-003",
    "driver13": "MIC-004",
    "driver14": "MIC-005",
    "driver15": "MIC-006",
    "driver16": "TAX-001",
    "driver17": "TAX-002",
    "driver18": "TAX-003",
}

# ============================================================
# SCHEDULES — peak (15min) / off-peak (30min)
# ============================================================
# Peak hours: 06:00-09:00 and 16:00-19:00 → 15 min frequency
# Off-peak: 09:00-16:00 and 19:00-23:00 → 30 min frequency
# Weekend (Fri/Sat = 5,6): 07:00-22:00 flat 25 min

# The schedules table has a single frequency_min per row, so we create
# separate peak and off-peak schedule rows per route per day.

# ============================================================
# GEOFENCES
# ============================================================

GEOFENCES = [
    {
        "name": "Damascus City Center",
        "name_ar": "وسط مدينة دمشق",
        "geofence_type": "zone",
        "speed_limit_kmh": 30,
        "wkt": "POLYGON((36.295 33.505, 36.325 33.505, 36.325 33.525, 36.295 33.525, 36.295 33.505))",
    },
    {
        "name": "Western Bus Station",
        "name_ar": "محطة السومرية",
        "geofence_type": "terminal",
        "speed_limit_kmh": 20,
        "wkt": "POLYGON((36.230 33.496, 36.240 33.496, 36.240 33.504, 36.230 33.504, 36.230 33.496))",
    },
    {
        "name": "Old City Zone",
        "name_ar": "منطقة المدينة القديمة",
        "geofence_type": "zone",
        "speed_limit_kmh": 20,
        "wkt": "POLYGON((36.305 33.508, 36.322 33.508, 36.322 33.516, 36.305 33.516, 36.305 33.508))",
    },
]


# ============================================================
# SEED EXECUTION
# ============================================================


def seed_users():
    """Seed users. Uses a placeholder password hash (bcrypt of 'demo2025')."""
    import bcrypt

    demo_hash = bcrypt.hashpw(b"demo2025", bcrypt.gensalt()).decode()
    rows = []
    for u in USERS:
        rows.append(
            {
                "email": u["email"],
                "password_hash": demo_hash,
                "full_name": u["full_name"],
                "full_name_ar": u["full_name_ar"],
                "role": u["role"],
                "phone": u["phone"],
            }
        )
    result = upsert("users", rows)
    print(f"  Users: {len(result)} upserted")
    return result


def seed_stops():
    """Seed all 54 stops with PostGIS Point geometry via RPC."""
    # Supabase PostgREST can't handle geometry literals directly,
    # so we use raw SQL via the rpc endpoint if available, or insert
    # with the SRID format that PostgREST accepts.
    #
    # For Supabase, we need to use the special EWKT format for geometry
    # columns when going through PostgREST.

    rows = []
    for s in STOPS:
        rows.append(
            {
                "stop_id": s["stop_id"],
                "name": s["name"],
                "name_ar": s["name_ar"],
                "location": f"SRID=4326;POINT({s['lon']} {s['lat']})",
                "has_shelter": s["shelter"],
                "is_active": True,
            }
        )
    result = upsert("stops", rows)
    print(f"  Stops: {len(result)} upserted")
    return result


def seed_routes():
    """Seed 8 routes with LineString geometry."""
    rows = []
    for r in ROUTES:
        coords = r["geometry"]["coordinates"]
        wkt_coords = ", ".join(f"{lon} {lat}" for lon, lat in coords)
        rows.append(
            {
                "route_id": r["route_id"],
                "name": r["name"],
                "name_ar": r["name_ar"],
                "route_type": r["route_type"],
                "color": r["color"],
                "distance_km": r["distance_km"],
                "avg_duration_min": r["avg_duration_min"],
                "fare_syp": r["fare_syp"],
                "geometry": f"SRID=4326;LINESTRING({wkt_coords})",
                "is_active": True,
            }
        )
    result = upsert("routes", rows)
    print(f"  Routes: {len(result)} upserted")
    return result


def seed_route_stops(route_map: dict, stop_map: dict):
    """Seed route-stop relationships."""
    # First delete existing route_stops to avoid duplicates
    for route_id_str, stops_list in ROUTE_STOPS.items():
        route_uuid = route_map.get(route_id_str)
        if not route_uuid:
            print(f"  WARNING: Route {route_id_str} not found, skipping route_stops")
            continue

        # Delete existing entries for this route
        CLIENT.delete(
            f"{BASE}/route_stops?route_id=eq.{route_uuid}",
            headers=HEADERS,
        )

        rows = []
        for stop_id_str, seq, dist_km, offset_min in stops_list:
            stop_uuid = stop_map.get(stop_id_str)
            if not stop_uuid:
                print(f"  WARNING: Stop {stop_id_str} not found, skipping")
                continue
            rows.append(
                {
                    "route_id": route_uuid,
                    "stop_id": stop_uuid,
                    "stop_sequence": seq,
                    "distance_from_start_km": dist_km,
                    "typical_arrival_offset_min": offset_min,
                }
            )
        if rows:
            upsert("route_stops", rows)
    print(f"  Route-stops: seeded for {len(ROUTE_STOPS)} routes")


def seed_vehicles(route_map: dict):
    """Seed 24 vehicles, assigning active ones to routes."""
    rows = []
    for v in VEHICLES:
        row = {
            "vehicle_id": v["vehicle_id"],
            "name": v["name"],
            "name_ar": v["name_ar"],
            "vehicle_type": v["vehicle_type"],
            "capacity": v["capacity"],
            "status": v["status"],
        }
        if v["route"] and v["route"] in route_map:
            row["assigned_route_id"] = route_map[v["route"]]
        rows.append(row)
    result = upsert("vehicles", rows)
    print(f"  Vehicles: {len(result)} upserted")
    return result


def seed_driver_assignments(user_rows: list, vehicle_rows: list):
    """Assign drivers to vehicles."""
    user_map = {}
    for u in user_rows:
        email = u.get("email", "")
        for key in DRIVER_ASSIGNMENTS:
            if email.startswith(key + "@"):
                user_map[key] = u["id"]

    vehicle_map = {}
    for v in vehicle_rows:
        vehicle_map[v.get("vehicle_id", "")] = v["id"]

    count = 0
    for driver_key, vehicle_id_str in DRIVER_ASSIGNMENTS.items():
        user_uuid = user_map.get(driver_key)
        veh_uuid = vehicle_map.get(vehicle_id_str)
        if user_uuid and veh_uuid:
            patch(
                "vehicles",
                f"vehicle_id=eq.{vehicle_id_str}",
                {"assigned_driver_id": user_uuid},
            )
            count += 1
    print(f"  Driver assignments: {count} linked")


def seed_schedules(route_map: dict):
    """Seed schedules with peak (15min) and off-peak (30min) patterns."""
    # Delete existing schedules first
    for route_id_str, route_uuid in route_map.items():
        CLIENT.delete(f"{BASE}/schedules?route_id=eq.{route_uuid}", headers=HEADERS)

    rows = []
    for route_id_str, route_uuid in route_map.items():
        # Weekdays (Sun=0 to Thu=4 in Syria)
        for dow in range(5):
            # Morning peak: 06:00-09:00, 15 min
            rows.append(
                {
                    "route_id": route_uuid,
                    "day_of_week": dow,
                    "first_departure": "06:00",
                    "last_departure": "09:00",
                    "frequency_min": 15,
                    "is_active": True,
                }
            )
            # Midday off-peak: 09:00-16:00, 30 min
            rows.append(
                {
                    "route_id": route_uuid,
                    "day_of_week": dow,
                    "first_departure": "09:00",
                    "last_departure": "16:00",
                    "frequency_min": 30,
                    "is_active": True,
                }
            )
            # Evening peak: 16:00-19:00, 15 min
            rows.append(
                {
                    "route_id": route_uuid,
                    "day_of_week": dow,
                    "first_departure": "16:00",
                    "last_departure": "19:00",
                    "frequency_min": 15,
                    "is_active": True,
                }
            )
            # Night off-peak: 19:00-23:00, 30 min
            rows.append(
                {
                    "route_id": route_uuid,
                    "day_of_week": dow,
                    "first_departure": "19:00",
                    "last_departure": "23:00",
                    "frequency_min": 30,
                    "is_active": True,
                }
            )

        # Friday & Saturday (5,6): reduced service
        for dow in [5, 6]:
            rows.append(
                {
                    "route_id": route_uuid,
                    "day_of_week": dow,
                    "first_departure": "07:00",
                    "last_departure": "22:00",
                    "frequency_min": 25,
                    "is_active": True,
                }
            )

    result = upsert("schedules", rows)
    print(f"  Schedules: {len(result)} rows created")


def seed_geofences():
    """Seed geofence zones."""
    rows = []
    for g in GEOFENCES:
        rows.append(
            {
                "name": g["name"],
                "name_ar": g["name_ar"],
                "geofence_type": g["geofence_type"],
                "speed_limit_kmh": g["speed_limit_kmh"],
                "geometry": f"SRID=4326;{g['wkt']}",
                "is_active": True,
            }
        )
    result = upsert("geofences", rows)
    print(f"  Geofences: {len(result)} upserted")


def main():
    _init_client()
    supabase_url = os.getenv("SUPABASE_URL", "")
    print("=" * 60)
    print("Damascus Transit System — Demo Data Seed")
    print("=" * 60)
    print(f"Target: {supabase_url}")
    print()

    # 1. Users
    print("[1/7] Seeding users...")
    user_rows = seed_users()

    # 2. Stops
    print("[2/7] Seeding stops (54 locations)...")
    stop_rows = seed_stops()
    stop_map = {s["stop_id"]: s["id"] for s in stop_rows}

    # 3. Routes
    print("[3/7] Seeding routes (8 corridors with polylines)...")
    route_rows = seed_routes()
    route_map = {r["route_id"]: r["id"] for r in route_rows}

    # 4. Route-stop assignments
    print("[4/7] Linking stops to routes...")
    seed_route_stops(route_map, stop_map)

    # 5. Vehicles
    print("[5/7] Seeding vehicles (24 fleet)...")
    vehicle_rows = seed_vehicles(route_map)

    # 6. Driver assignments
    print("[6/7] Assigning drivers to vehicles...")
    seed_driver_assignments(user_rows, vehicle_rows)

    # 7. Schedules
    print("[7/7] Seeding schedules (peak/off-peak)...")
    seed_schedules(route_map)

    # Geofences (bonus)
    print("[+] Seeding geofences...")
    seed_geofences()

    print()
    print("=" * 60)
    print("DONE — Verify with:")
    print("  GET /api/routes   → expect 8 routes")
    print("  GET /api/stops    → expect 54 stops")
    print("  GET /api/vehicles → expect 24 vehicles")
    print("=" * 60)


if __name__ == "__main__":
    main()
