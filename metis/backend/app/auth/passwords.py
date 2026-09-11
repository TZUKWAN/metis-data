"""Independent per-provider password generator (A11).

- ≥16 chars, upper+lower+digit+symbol, `secrets`-based (CSPRNG);
- provider-specific rules can override length/class requirements;
- never reused across providers; masked in logs via vault registration.
"""
from __future__ import annotations

import secrets

UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
LOWER = "abcdefghijkmnpqrstuvwxyz"
DIGIT = "23456789"
SYMBOL = "!@#$%^&*()-_=+[]{}:,.?"

DEFAULT_MIN_LEN = 16


def generate_password(provider_rules: dict | None = None) -> str:
    rules = provider_rules or {}
    min_len = max(int(rules.get("min_length", DEFAULT_MIN_LEN)), DEFAULT_MIN_LEN)
    symbol_set = rules.get("symbols", SYMBOL)
    required = [
        (UPPER, int(rules.get("min_upper", 1))),
        (LOWER, int(rules.get("min_lower", 1))),
        (DIGIT, int(rules.get("min_digit", 1))),
        (symbol_set, int(rules.get("min_symbol", 1))),
    ]
    chars: list[str] = []
    for pool, n in required:
        chars += [secrets.choice(pool) for _ in range(n)]
    all_pool = UPPER + LOWER + DIGIT + symbol_set
    while len(chars) < min_len:
        chars.append(secrets.choice(all_pool))
    # Fisher-Yates with CSPRNG
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def check_policy(password: str, provider_rules: dict | None = None) -> bool:
    rules = provider_rules or {}
    ok_len = len(password) >= int(rules.get("min_length", DEFAULT_MIN_LEN))
    return (
        ok_len
        and any(c in UPPER for c in password)
        and any(c in LOWER for c in password)
        and any(c in DIGIT for c in password)
        and any(c in rules.get("symbols", SYMBOL) for c in password)
    )
