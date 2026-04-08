"""
SiteGuard Monitor — Offline License Validator
Валидация ключа происходит локально по HMAC-подписи.
Сеть не нужна. Работает за любым прокси.

Формат ключа: SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM
  - префикс SG
  - 4 группы по 5 символов [A-Z0-9] = тело ключа
  - 5-символьная HMAC-контрольная сумма

Данные плана закодированы в первой группе (первый символ = план):
  S = starter, P = professional, B = business, E = enterprise, T = trial
"""
from __future__ import annotations

import hashlib
import hmac
import string
import random
import datetime
from typing import Tuple

# Этот секрет должен быть одинаковым в admin_server и в десктоп-приложении.
# Менять его можно только одновременно в обоих местах.
LICENSE_HMAC_SECRET = b"RossiSiteGuard_2024_PROD_SECRET_KEY_v1"

PLAN_CHARS = {
    "T": "trial",
    "S": "starter",
    "P": "professional",
    "B": "business",
    "E": "enterprise",
}

PLAN_CONFIG = {
    "trial":        {"max_sites": 3,      "days": 14,  "label": "Trial"},
    "starter":      {"max_sites": 5,      "days": 365, "label": "Starter"},
    "professional": {"max_sites": 25,     "days": 365, "label": "Professional"},
    "business":     {"max_sites": 100,    "days": 365, "label": "Business"},
    "enterprise":   {"max_sites": 999999, "days": 365, "label": "Enterprise"},
}

_CHARS = string.ascii_uppercase + string.digits


def _hmac_checksum(body: str) -> str:
    """5-символьная HMAC-SHA256 контрольная сумма от тела ключа."""
    return hmac.new(
        LICENSE_HMAC_SECRET,
        body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest().upper()[:5]


def generate_key(plan: str, expires_days: int | None = None) -> str:
    """
    Генерирует лицензионный ключ для указанного плана.
    Первый символ первой группы = код плана.
    """
    plan = plan.lower()
    if plan not in PLAN_CONFIG:
        raise ValueError(f"Unknown plan: {plan}")

    plan_char = next(k for k, v in PLAN_CHARS.items() if v == plan)

    # Первый символ первой группы = план, остальные — случайные
    def rand_group(length=5):
        return "".join(random.choices(_CHARS, k=length))

    g1 = plan_char + "".join(random.choices(_CHARS, k=4))
    g2 = rand_group()
    g3 = rand_group()
    g4 = rand_group()
    body = f"SG-{g1}-{g2}-{g3}-{g4}"
    checksum = _hmac_checksum(body)
    return f"{body}-{checksum}"


def validate_key(key: str) -> Tuple[bool, str, dict]:
    """
    Полностью офлайн-валидация ключа.

    Returns:
        (is_valid, error_message, info_dict)
        info_dict содержит: plan, label, max_sites
    """
    key = key.strip().upper()

    # Формат
    parts = key.split("-")
    if len(parts) != 6 or parts[0] != "SG":
        return False, "Неверный формат ключа (ожидается SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM)", {}

    for i, p in enumerate(parts[1:], 1):
        if len(p) != 5 or not all(c in _CHARS for c in p):
            return False, f"Неверный формат группы {i}", {}

    # Контрольная сумма
    body = "-".join(parts[:5])
    expected = _hmac_checksum(body)
    if parts[5] != expected:
        return False, "Недействительный ключ — контрольная сумма не совпадает", {}

    # Определяем план из первого символа первой группы
    plan_char = parts[1][0]
    plan = PLAN_CHARS.get(plan_char)
    if not plan:
        return False, "Неизвестный тип плана в ключе", {}

    cfg = PLAN_CONFIG[plan]
    return True, "", {
        "plan": plan,
        "label": cfg["label"],
        "max_sites": cfg["max_sites"],
    }
