"""
Синтетический генератор тестовых датасетов.

⚠️ Этот модуль — закрытая реализация. Команде доступна только публичная
функция `generate_events(...)`. Содержимое приватных функций (с префиксом
`_`) не предназначено для изучения и копирования: точные параметры закладок
и фрод-паттернов — часть учебной задачи, которую команда решает,
анализируя данные.

Использование:

    from dq_monitor.src.synthetic_data import generate_events

    df_dirty, df_clean, fraud_labels = generate_events(
        seed=42,
        n_transactions=50_000,
        fraud_intensity="medium",
        dq_severity="medium",
    )

Подробнее — в `dq_monitor/docs/SYNTHETIC_DATA.md` и в примере
`scripts/generate_test_dataset.py`.
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd


__all__ = ["generate_events"]


# ============================================================================
# Публичный API
# ============================================================================

def generate_events(
    *,
    seed: int = 42,
    n_transactions: int = 50_000,
    n_clients: int = 10_000,
    fraud_intensity: Literal["low", "medium", "high"] = "medium",
    dq_severity: Literal["low", "medium", "high", "none"] = "medium",
    output_dir: Path | str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Сгенерировать синтетический банковский датасет событий.

    Сгенерированные данные подходят для тестирования DQ Monitor:
    содержат искусственно заложенные DQ-проблемы и фрод-паттерны,
    которые система должна находить и чинить.

    Args:
        seed: зерно генератора. Один и тот же seed даёт один и тот же
            датасет — это важно для воспроизводимости результатов
            на защите.
        n_transactions: сколько нормальных событий сгенерировать. По
            умолчанию 50 000 — быстро (5-10 секунд) и достаточно для
            демонстрации.
        n_clients: сколько уникальных клиентов будет в датасете.
            Рекомендация: примерно n_transactions / 5.
        fraud_intensity: интенсивность фрод-паттернов.
            'low'    — мало фрода, лёгкий случай
            'medium' — реалистичная интенсивность (~1.6% строк)
            'high'   — много фрода, нагрузочный режим
        dq_severity: интенсивность DQ-проблем.
            'none'   — чистые данные без закладок (baseline)
            'low'    — небольшие искажения
            'medium' — реалистичный уровень мусора
            'high'   — сильно зашумлённые данные
        output_dir: если задан — сохранит CSV-файлы:
            {output_dir}/raw/events_dirty.csv
            {output_dir}/ground_truth/events_clean.csv
            {output_dir}/ground_truth/fraud_labels.csv

    Returns:
        Кортеж из трёх DataFrame:
            df_dirty       — грязный датасет, без is_fraud_real
            df_clean       — эталон с разметкой фрода
            fraud_labels   — event_id -> is_fraud_real

    Examples:
        Стандартный medium-датасет с дефолтным сидом:

            df_d, df_c, labels = generate_events()

        Большой high-severity датасет с другим сидом для защиты:

            df_d, df_c, labels = generate_events(
                seed=2026,
                n_transactions=100_000,
                fraud_intensity="high",
                dq_severity="high",
                output_dir="data/test_dataset_3",
            )

        Чистый baseline (без закладок) — для проверки, что система
        ничего не находит, когда нечего находить:

            df_d, df_c, labels = generate_events(dq_severity="none")
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    fraud_mul = _FRAUD_PRESETS[fraud_intensity]
    dq_mul = _DQ_PRESETS[dq_severity]

    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 6, 30)

    clients = _generate_clients(n_clients, rng)
    df = _generate_normal_events(
        clients, n_transactions, rng, np_rng, start_date, end_date)

    # Фрод-паттерны масштабируются под объём n_transactions
    base_scale = n_transactions / 150_000
    df = _inject_carousels(df, clients,
                            int(80 * base_scale * fraud_mul), rng, np_rng)
    df = _inject_night_withdrawals(df,
                                    int(400 * base_scale * fraud_mul), rng, np_rng)
    df = _inject_risky_categories(df,
                                   int(600 * base_scale * fraud_mul), rng, np_rng)
    df = _inject_geo_impossibility(df, clients,
                                    int(120 * base_scale * fraud_mul), rng, np_rng)
    df = _inject_failed_logins_fraud(df, clients,
                                      int(80 * base_scale * fraud_mul), rng, np_rng)

    df = _add_legitimate_flags(df, rng)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    df["card_last4"] = df["card_last4"].apply(_normalize_card_last4)

    df_clean = df.copy()
    fraud_labels = df_clean[["event_id", "is_fraud_real"]].copy()

    if dq_severity == "none":
        df_dirty = df_clean.drop(columns=["is_fraud_real"]).copy()
    else:
        df_dirty = _corrupt_with_dq_issues(df_clean, rng, dq_mul)
        df_dirty = df_dirty.drop(columns=["is_fraud_real"])

    if output_dir is not None:
        output_dir = Path(output_dir)
        (output_dir / "raw").mkdir(parents=True, exist_ok=True)
        (output_dir / "ground_truth").mkdir(parents=True, exist_ok=True)
        df_dirty.to_csv(output_dir / "raw" / "events_dirty.csv", index=False)
        df_clean.to_csv(output_dir / "ground_truth" / "events_clean.csv", index=False)
        fraud_labels.to_csv(output_dir / "ground_truth" / "fraud_labels.csv", index=False)

    return df_dirty, df_clean, fraud_labels


# ============================================================================
# Пресеты
# ============================================================================

_FRAUD_PRESETS = {"low": 0.5, "medium": 1.0, "high": 1.5}
_DQ_PRESETS = {"none": 0.0, "low": 0.3, "medium": 1.0, "high": 2.0}


# ============================================================================
# Приватные константы — не предназначены для изучения
# ============================================================================

_ALLOWED_TRIPLES = [
    ("mobile", "app", "grocery", 1.0),
    ("mobile", "app", "restaurant", 1.0),
    ("mobile", "app", "transport", 1.0),
    ("mobile", "app", "gas_station", 1.0),
    ("mobile", "app", "online_shopping", 1.0),
    ("mobile", "app", "entertainment", 1.0),
    ("mobile", "app", "healthcare", 1.0),
    ("mobile", "app", "education", 1.0),
    ("mobile", "app", "utilities", 1.0),
    ("mobile", "app", "clothing", 1.0),
    ("mobile", "app", "electronics", 0.5),
    ("desktop", "web", "online_shopping", 1.0),
    ("desktop", "web", "electronics", 1.0),
    ("desktop", "web", "education", 0.8),
    ("desktop", "web", "utilities", 0.6),
    ("desktop", "web", "crypto_exchange", 1.0),
    ("desktop", "web", "wire_transfer_abroad", 0.5),
    ("desktop", "web", "gambling", 0.7),
    ("atm", "atm", "atm_withdrawal", 1.0),
    ("mobile", "branch", "wire_transfer_abroad", 0.5),
    ("desktop", "branch", "wire_transfer_abroad", 0.5),
    ("mobile", "branch", "utilities", 0.2),
]

_AMOUNT_PROFILES = {
    "grocery": (6.5, 0.6), "restaurant": (7.3, 0.7), "transport": (5.0, 0.5),
    "gas_station": (7.8, 0.4), "online_shopping": (8.0, 1.0),
    "entertainment": (6.8, 0.8), "healthcare": (7.5, 1.1),
    "education": (9.5, 0.5), "utilities": (7.5, 0.4), "clothing": (7.8, 1.0),
    "electronics": (9.0, 1.2), "atm_withdrawal": (8.5, 0.5),
    "crypto_exchange": (10.5, 1.0), "wire_transfer_abroad": (11.0, 0.8),
    "gambling": (9.0, 1.3),
}

_SEGMENT_BIAS = {
    "mass": {
        "grocery": 2.0, "restaurant": 1.0, "transport": 2.0,
        "gas_station": 1.5, "utilities": 2.0, "atm_withdrawal": 2.0,
        "healthcare": 0.8, "education": 0.5, "clothing": 0.8,
        "online_shopping": 1.0, "entertainment": 0.7, "electronics": 0.4,
        "crypto_exchange": 0.02, "wire_transfer_abroad": 0.02, "gambling": 0.05,
    },
    "premium": {
        "grocery": 1.0, "restaurant": 1.8, "transport": 1.0,
        "gas_station": 1.5, "utilities": 1.0, "atm_withdrawal": 1.0,
        "healthcare": 1.3, "education": 1.2, "clothing": 1.5,
        "online_shopping": 1.5, "entertainment": 1.5, "electronics": 1.3,
        "crypto_exchange": 0.1, "wire_transfer_abroad": 0.1, "gambling": 0.1,
    },
    "vip": {
        "grocery": 0.5, "restaurant": 2.0, "transport": 0.3,
        "gas_station": 1.0, "utilities": 0.5, "atm_withdrawal": 0.5,
        "healthcare": 1.5, "education": 1.5, "clothing": 2.0,
        "online_shopping": 1.5, "entertainment": 2.0, "electronics": 1.8,
        "crypto_exchange": 0.3, "wire_transfer_abroad": 0.4, "gambling": 0.15,
    },
}

_SEGMENT_AMOUNT_MUL = {"mass": 1.0, "premium": 1.8, "vip": 3.5}
_SEGMENT_DIST = {"mass": 0.75, "premium": 0.20, "vip": 0.05}

_MCC_ISO = {
    "grocery": "5411", "restaurant": "5812", "transport": "4111",
    "electronics": "5732", "clothing": "5651", "entertainment": "7832",
    "healthcare": "8011", "education": "8220", "utilities": "4900",
    "online_shopping": "5969", "gas_station": "5541", "atm_withdrawal": "6011",
    "crypto_exchange": "6051", "gambling": "7995", "wire_transfer_abroad": "4829",
}

_RU_CITIES = [
    ("Moscow", "Russia"), ("Saint Petersburg", "Russia"), ("Novosibirsk", "Russia"),
    ("Yekaterinburg", "Russia"), ("Kazan", "Russia"), ("Nizhny Novgorod", "Russia"),
    ("Krasnodar", "Russia"), ("Sochi", "Russia"), ("Samara", "Russia"), ("Ufa", "Russia"),
]
_FOREIGN_CITIES = [
    ("Limassol", "Cyprus"), ("Dubai", "UAE"), ("Yerevan", "Armenia"),
    ("Astana", "Kazakhstan"), ("Tbilisi", "Georgia"), ("Istanbul", "Turkey"),
]

_AUTH_METHODS = ["password", "biometric", "sms_otp"]
_FLAG_REASONS = [
    "high_amount", "unusual_location", "velocity_check",
    "blacklist_match", "device_change", "night_activity",
]
_RISKY = ["crypto_exchange", "gambling", "wire_transfer_abroad"]
_NORMAL_CATS = [c for c in _MCC_ISO if c not in _RISKY]


# ============================================================================
# Утилиты
# ============================================================================

def _rand_ip(rng): return ".".join(str(rng.randint(1, 254)) for _ in range(4))
def _rand_card(rng): return f"{rng.randint(0, 9999):04d}"
def _rand_eid(rng): return "".join(rng.choices(string.hexdigits.lower()[:16], k=16))


def _normalize_card_last4(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(4) if s else None


def _realistic_amount(category, segment, np_rng):
    mean_log, sigma = _AMOUNT_PROFILES[category]
    raw = float(np_rng.lognormal(mean=mean_log, sigma=sigma))
    raw *= _SEGMENT_AMOUNT_MUL[segment]
    if category == "atm_withdrawal":
        raw = max(500, round(raw / 500) * 500)
    return float(np.round(raw, 2))


# ============================================================================
# Этапы генерации
# ============================================================================

def _generate_clients(n, rng):
    rows = []
    segs = list(_SEGMENT_DIST.keys())
    w = list(_SEGMENT_DIST.values())
    for i in range(n):
        city, country = rng.choices(_RU_CITIES, weights=[20, 15] + [5] * 8, k=1)[0]
        seg = rng.choices(segs, weights=w, k=1)[0]
        if seg == "vip":
            pref = rng.choices(["mobile", "desktop"], weights=[0.5, 0.5], k=1)[0]
        elif seg == "premium":
            pref = rng.choices(["mobile", "desktop"], weights=[0.7, 0.3], k=1)[0]
        else:
            pref = rng.choices(["mobile", "desktop"], weights=[0.92, 0.08], k=1)[0]
        rows.append({
            "client_id": f"C{i:06d}", "home_city": city, "home_country": country,
            "registered_at": datetime(2023, 1, 1) + timedelta(days=rng.randint(0, 600)),
            "segment": seg, "device_pref": pref,
        })
    return pd.DataFrame(rows)


def _build_pool(segment, device_pref):
    bias = _SEGMENT_BIAS[segment]
    triples, weights = [], []
    for device, channel, category, base_w in _ALLOWED_TRIPLES:
        w = base_w * bias.get(category, 1.0)
        if device == device_pref:
            w *= 1.5
        elif device == "atm":
            w *= 0.3
        triples.append((device, channel, category))
        weights.append(w)
    arr = np.array(weights, dtype=float)
    arr /= arr.sum()
    return triples, arr


def _generate_normal_events(clients, n, rng, np_rng, start_date, end_date):
    is_txn = np_rng.random(n) < 0.7
    cw = np_rng.power(0.3, size=len(clients))
    cw /= cw.sum()
    client_idx = np_rng.choice(len(clients), size=n, p=cw)

    pools = {c["client_id"]: _build_pool(c["segment"], c["device_pref"])
             for _, c in clients.iterrows()}

    period = int((end_date - start_date).total_seconds())
    days = np_rng.integers(0, period // 86400, size=n)
    hour_dist = np.array(
        [1,1,1,1,1,2,4,8,15,20,25,28,28,28,28,28,28,28,28,25,22,18,12,5],
        dtype=float)
    hour_dist /= hour_dist.sum()
    hours = np_rng.choice(24, size=n, p=hour_dist)
    mins = np_rng.integers(0, 60, size=n)
    secs = np_rng.integers(0, 60, size=n)

    rows = []
    for i in range(n):
        c = clients.iloc[client_idx[i]]
        cid = c["client_id"]
        ts = start_date + timedelta(days=int(days[i]), hours=int(hours[i]),
                                    minutes=int(mins[i]), seconds=int(secs[i]))
        roll = rng.random()
        if roll < 0.80:
            geo_city, geo_country = c["home_city"], c["home_country"]
        elif roll < 0.95:
            geo_city, geo_country = rng.choice(_RU_CITIES)
        else:
            geo_city, geo_country = rng.choice(_RU_CITIES + _FOREIGN_CITIES)

        if is_txn[i]:
            triples, weights = pools[cid]
            idx = np_rng.choice(len(triples), p=weights)
            device, channel, mcc = triples[idx]
            amount = _realistic_amount(mcc, c["segment"], np_rng)
            if mcc == "wire_transfer_abroad":
                merchant_country = rng.choice([fc[1] for fc in _FOREIGN_CITIES])
            elif mcc == "crypto_exchange" and rng.random() < 0.7:
                merchant_country = rng.choice([fc[1] for fc in _FOREIGN_CITIES])
            elif mcc == "gambling" and rng.random() < 0.4:
                merchant_country = rng.choice([fc[1] for fc in _FOREIGN_CITIES])
            else:
                merchant_country = "Russia"
            ss = se = ls = am = None
            card = _rand_card(rng)
            curr = "RUB"
        else:
            device = c["device_pref"]
            channel = "app" if device == "mobile" else "web"
            amount = curr = mcc = merchant_country = card = None
            ss = ts
            se = ts + timedelta(minutes=rng.randint(1, 45))
            ls = rng.random() > 0.05
            am = rng.choice(_AUTH_METHODS)

        rows.append({
            "event_id": _rand_eid(rng), "client_id": cid,
            "event_type": "transaction" if is_txn[i] else "session",
            "event_ts": ts, "device_type": device, "ip_address": _rand_ip(rng),
            "geo_country": geo_country, "geo_city": geo_city, "channel": channel,
            "amount_rub": amount, "currency": curr, "merchant_category": mcc,
            "merchant_country": merchant_country, "card_last4": card,
            "is_flagged": False, "flag_reason": None,
            "session_start_ts": ss, "session_end_ts": se,
            "login_success": ls, "auth_method": am, "is_fraud_real": False,
        })
    return pd.DataFrame(rows)


# ============================================================================
# Фрод-инжекторы
# ============================================================================

def _inject_carousels(df, clients, n, rng, np_rng):
    if n <= 0:
        return df
    new = []
    chosen = rng.sample(range(len(clients)), min(n, len(clients)))
    for idx in chosen:
        c = clients.iloc[idx]
        bsize = rng.randint(6, 12)
        bstart = datetime(2025, 1, 1) + timedelta(
            days=rng.randint(0, 150), hours=rng.randint(8, 22),
            minutes=rng.randint(0, 50))
        for k in range(bsize):
            ts = bstart + timedelta(seconds=k * rng.randint(30, 90))
            mcc = rng.choice(["online_shopping", "transport", "restaurant"])
            new.append({
                "event_id": _rand_eid(rng), "client_id": c["client_id"],
                "event_type": "transaction", "event_ts": ts,
                "device_type": "mobile", "ip_address": _rand_ip(rng),
                "geo_country": c["home_country"], "geo_city": c["home_city"],
                "channel": "app",
                "amount_rub": _realistic_amount(mcc, c["segment"], np_rng),
                "currency": "RUB", "merchant_category": mcc,
                "merchant_country": "Russia", "card_last4": _rand_card(rng),
                "is_flagged": False, "flag_reason": None,
                "session_start_ts": None, "session_end_ts": None,
                "login_success": None, "auth_method": None,
                "is_fraud_real": True,
            })
    return pd.concat([df, pd.DataFrame(new)], ignore_index=True)


def _inject_night_withdrawals(df, n, rng, np_rng):
    if n <= 0:
        return df
    new = []
    candidates = df[df["event_type"] == "transaction"].sample(
        min(n, (df["event_type"] == "transaction").sum()),
        random_state=rng.randint(0, 10**6))
    for _, row in candidates.iterrows():
        new_ts = row["event_ts"].replace(
            hour=rng.randint(1, 3), minute=rng.randint(0, 59))
        amt = float(np.round(np_rng.uniform(55_000, 350_000), 2))
        new_mcc = rng.choice(["atm_withdrawal", "online_shopping"])
        new_device = "atm" if new_mcc == "atm_withdrawal" else "mobile"
        new_channel = "atm" if new_device == "atm" else "app"
        new.append({**row.to_dict(), "event_id": _rand_eid(rng),
                    "event_ts": new_ts, "amount_rub": amt,
                    "merchant_category": new_mcc,
                    "device_type": new_device, "channel": new_channel,
                    "is_fraud_real": True})
    return pd.concat([df, pd.DataFrame(new)], ignore_index=True)


def _inject_risky_categories(df, n, rng, np_rng):
    if n <= 0:
        return df
    new = []
    candidates = df[df["event_type"] == "transaction"].sample(
        min(n, (df["event_type"] == "transaction").sum()),
        random_state=rng.randint(0, 10**6))
    for _, row in candidates.iterrows():
        mcc = rng.choice(_RISKY)
        mc = rng.choice(["Cyprus", "UAE", "Armenia", "Kazakhstan", "Georgia"])
        if mcc == "wire_transfer_abroad":
            device, channel = rng.choice([("desktop", "web"), ("mobile", "branch")])
        else:
            device, channel = "desktop", "web"
        new.append({**row.to_dict(), "event_id": _rand_eid(rng),
                    "amount_rub": float(np.round(np_rng.uniform(80_000, 500_000), 2)),
                    "merchant_category": mcc, "merchant_country": mc,
                    "device_type": device, "channel": channel,
                    "is_fraud_real": True})
    return pd.concat([df, pd.DataFrame(new)], ignore_index=True)


def _inject_geo_impossibility(df, clients, n, rng, np_rng):
    if n <= 0:
        return df
    new = []
    chosen = rng.sample(range(len(clients)), min(n, len(clients)))
    for idx in chosen:
        c = clients.iloc[idx]
        t1 = datetime(2025, 1, 1) + timedelta(
            days=rng.randint(0, 150), hours=rng.randint(8, 22))
        t2 = t1 + timedelta(minutes=rng.randint(5, 25))
        fc, fco = rng.choice(_FOREIGN_CITIES)
        for ts, city, country in [(t1, c["home_city"], c["home_country"]),
                                  (t2, fc, fco)]:
            mcc = rng.choice(["online_shopping", "restaurant", "atm_withdrawal"])
            if mcc == "atm_withdrawal":
                device, channel = "atm", "atm"
            else:
                device, channel = "mobile", "app"
            new.append({
                "event_id": _rand_eid(rng), "client_id": c["client_id"],
                "event_type": "transaction", "event_ts": ts,
                "device_type": device, "ip_address": _rand_ip(rng),
                "geo_country": country, "geo_city": city, "channel": channel,
                "amount_rub": _realistic_amount(mcc, c["segment"], np_rng),
                "currency": "RUB", "merchant_category": mcc,
                "merchant_country": country, "card_last4": _rand_card(rng),
                "is_flagged": False, "flag_reason": None,
                "session_start_ts": None, "session_end_ts": None,
                "login_success": None, "auth_method": None, "is_fraud_real": True,
            })
    return pd.concat([df, pd.DataFrame(new)], ignore_index=True)


def _inject_failed_logins_fraud(df, clients, n, rng, np_rng):
    if n <= 0:
        return df
    new = []
    chosen = rng.sample(range(len(clients)), min(n, len(clients)))
    for idx in chosen:
        c = clients.iloc[idx]
        bts = datetime(2025, 1, 1) + timedelta(
            days=rng.randint(0, 150), hours=rng.randint(0, 23))
        device = c["device_pref"]
        channel = "app" if device == "mobile" else "web"
        for k in range(rng.randint(3, 6)):
            sts = bts + timedelta(seconds=k * rng.randint(20, 60))
            new.append({
                "event_id": _rand_eid(rng), "client_id": c["client_id"],
                "event_type": "session", "event_ts": sts,
                "device_type": device, "ip_address": _rand_ip(rng),
                "geo_country": c["home_country"], "geo_city": c["home_city"],
                "channel": channel,
                "amount_rub": None, "currency": None,
                "merchant_category": None, "merchant_country": None,
                "card_last4": None, "is_flagged": False, "flag_reason": None,
                "session_start_ts": sts,
                "session_end_ts": sts + timedelta(seconds=rng.randint(10, 30)),
                "login_success": False,
                "auth_method": rng.choice(_AUTH_METHODS),
                "is_fraud_real": True,
            })
        tts = bts + timedelta(minutes=rng.randint(5, 15))
        mcc = rng.choice(["atm_withdrawal"] + _RISKY)
        if mcc == "atm_withdrawal":
            td, tc = "atm", "atm"
        elif mcc == "wire_transfer_abroad":
            td, tc = device, "branch"
        else:
            td, tc = "desktop", "web"
        new.append({
            "event_id": _rand_eid(rng), "client_id": c["client_id"],
            "event_type": "transaction", "event_ts": tts,
            "device_type": td, "ip_address": _rand_ip(rng),
            "geo_country": c["home_country"], "geo_city": c["home_city"],
            "channel": tc,
            "amount_rub": float(np.round(np_rng.uniform(70_000, 250_000), 2)),
            "currency": "RUB", "merchant_category": mcc,
            "merchant_country": rng.choice(["Russia", "Cyprus", "UAE"]),
            "card_last4": _rand_card(rng), "is_flagged": False, "flag_reason": None,
            "session_start_ts": None, "session_end_ts": None,
            "login_success": None, "auth_method": None, "is_fraud_real": True,
        })
    return pd.concat([df, pd.DataFrame(new)], ignore_index=True)


def _add_legitimate_flags(df, rng):
    fraud_idx = df.index[df["is_fraud_real"]].tolist()
    n_flag = int(len(fraud_idx) * 0.4)
    flagged = rng.sample(fraud_idx, n_flag) if fraud_idx else []
    df.loc[flagged, "is_flagged"] = True
    df.loc[flagged, "flag_reason"] = [rng.choice(_FLAG_REASONS) for _ in flagged]
    return df


# ============================================================================
# DQ-инжектор — все категории команды покрыты
# ============================================================================

def _corrupt_with_dq_issues(df, rng, mul):
    """Накладывает DQ-проблемы. mul — множитель интенсивности."""
    df = df.copy()
    n = len(df)
    txn_idx = df.index[df["event_type"] == "transaction"].tolist()
    sess_idx = df.index[df["event_type"] == "session"].tolist()

    def _pick(pool, frac):
        k = int(len(pool) * frac * mul)
        if k <= 0:
            return []
        return rng.sample(pool, min(k, len(pool)))

    # === UNIQUENESS ===
    # Полные дубликаты строк
    dup_idx = _pick(list(range(n)), 0.01)
    if dup_idx:
        df = pd.concat([df, df.iloc[dup_idx].copy()], ignore_index=True)

    # Дубликаты event_id (с разным содержимым)
    eid_dup = _pick(list(range(len(df))), 0.005)
    for i in eid_dup:
        target = rng.choice(range(len(df)))
        if target != i:
            df.at[i, "event_id"] = df.at[target, "event_id"]

    n_now = len(df)
    all_idx = list(range(n_now))
    txn_idx = df.index[df["event_type"] == "transaction"].tolist()
    sess_idx = df.index[df["event_type"] == "session"].tolist()

    # === COMPLETENESS (глобальные обязательные) ===
    for col, frac in [
        ("event_id", 0.003), ("client_id", 0.04), ("event_type", 0.005),
        ("device_type", 0.01), ("ip_address", 0.005),
        ("geo_country", 0.01), ("geo_city", 0.12), ("channel", 0.005),
    ]:
        idx = _pick(all_idx, frac)
        df.loc[idx, col] = None

    # device_type ещё и пустые строки
    empty_dev = _pick(all_idx, 0.01)
    df.loc[empty_dev, "device_type"] = ""

    # === COMPLETENESS — поля транзакций ===
    if txn_idx:
        for col, frac in [
            ("amount_rub", 0.01), ("merchant_category", 0.01),
            ("merchant_country", 0.01), ("card_last4", 0.01),
        ]:
            idx = _pick(txn_idx, frac)
            df.loc[idx, col] = None

    # === COMPLETENESS — поля сессий ===
    if sess_idx:
        for col, frac in [
            ("session_start_ts", 0.01), ("session_end_ts", 0.01),
            ("login_success", 0.01), ("auth_method", 0.01),
        ]:
            idx = _pick(sess_idx, frac)
            df.loc[idx, col] = None

    # === VALIDITY ===
    # Битые даты event_ts
    df["event_ts"] = df["event_ts"].astype("object")
    bad_dates = ["32/13/2025", "вчера", "2025-13-45", "yesterday",
                 "01.01.20255", "tomorrow"]
    idx = _pick(all_idx, 0.025)
    for i in idx:
        df.at[i, "event_ts"] = rng.choice(bad_dates)

    # Битые session timestamps
    if sess_idx:
        df["session_start_ts"] = df["session_start_ts"].astype("object")
        df["session_end_ts"] = df["session_end_ts"].astype("object")
        for col in ["session_start_ts", "session_end_ts"]:
            idx = _pick(sess_idx, 0.005)
            for i in idx:
                df.at[i, col] = rng.choice(bad_dates)

    # Невалидные IP
    bad_ips = ["999.999.999.999", "localhost", "127.0.0.1.5",
               "256.0.0.1", "0.0.0.0", "abc.def.ghi.jkl"]
    idx = _pick(all_idx, 0.01)
    for i in idx:
        df.at[i, "ip_address"] = rng.choice(bad_ips)

    # Аномальные суммы (отрицательные + выбросы)
    if txn_idx:
        idx = _pick(txn_idx, 0.03)
        half = len(idx) // 2
        df.loc[idx[:half], "amount_rub"] = (
            df.loc[idx[:half], "amount_rub"] * -1)
        for i in idx[half:]:
            df.at[i, "amount_rub"] = float(rng.randint(10_000_000, 50_000_000))

    # Опечатки в currency
    if txn_idx:
        bad_curr = ["USDD", "rub", "810", "$", "RUR", "руб", ""]
        idx = _pick(txn_idx, 0.04)
        for i in idx:
            df.at[i, "currency"] = rng.choice(bad_curr)

    # ISO-коды в merchant_category в феврале
    feb_mask = df["event_ts"].apply(
        lambda x: isinstance(x, datetime) and x.year == 2025 and x.month == 2)
    feb_txn = df.index[feb_mask & (df["event_type"] == "transaction")].tolist()
    n_iso = int(len(feb_txn) * 0.6 * mul)
    iso_idx = rng.sample(feb_txn, min(n_iso, len(feb_txn))) if feb_txn else []
    for i in iso_idx:
        cat = df.at[i, "merchant_category"]
        if cat in _MCC_ISO:
            df.at[i, "merchant_category"] = _MCC_ISO[cat]

    # Невалидные card_last4
    if txn_idx:
        bad_cards = ["12", "abcd", "12345", "0", "----"]
        idx = _pick(txn_idx, 0.005)
        for i in idx:
            df.at[i, "card_last4"] = rng.choice(bad_cards)

    # Невалидные device_type
    bad_dev = ["Mobile", "phone", "PC", "tablet", "unknown"]
    idx = _pick(all_idx, 0.005)
    for i in idx:
        df.at[i, "device_type"] = rng.choice(bad_dev)

    # Невалидные channel
    bad_ch = ["mobile-app", "browser", "ATM", "office", "unknown"]
    idx = _pick(all_idx, 0.005)
    for i in idx:
        df.at[i, "channel"] = rng.choice(bad_ch)

    # Невалидные geo_country (нарушение формата ISO alpha-2)
    bad_country = ["russia", "RUS", "Россия", "ru", "USA"]
    idx = _pick(all_idx, 0.005)
    for i in idx:
        df.at[i, "geo_country"] = rng.choice(bad_country)

    # Невалидные event_type
    bad_et = ["TRANSACTION", "tx", "sess", "event", ""]
    idx = _pick(all_idx, 0.003)
    for i in idx:
        df.at[i, "event_type"] = rng.choice(bad_et)

    # === CONSISTENCY ===
    # Рассогласование is_flagged / flag_reason
    n_flag = int(len(df) * 0.05 * mul)
    flag_idx = rng.sample(range(len(df)), min(n_flag, len(df)))
    half = len(flag_idx) // 2
    df.loc[flag_idx[:half], "is_flagged"] = True
    df.loc[flag_idx[:half], "flag_reason"] = None
    df.loc[flag_idx[half:], "is_flagged"] = False
    df.loc[flag_idx[half:], "flag_reason"] = [
        rng.choice(_FLAG_REASONS) for _ in flag_idx[half:]]

    # session-поля у transaction и наоборот
    n_swap = int(len(df) * 0.03 * mul)
    swap_idx = rng.sample(range(len(df)), min(n_swap, len(df)))
    for i in swap_idx:
        if df.at[i, "event_type"] == "transaction":
            ts = df.at[i, "event_ts"]
            if isinstance(ts, datetime):
                df.at[i, "session_start_ts"] = ts
                df.at[i, "session_end_ts"] = ts + timedelta(minutes=rng.randint(1, 30))
                df.at[i, "login_success"] = True
                df.at[i, "auth_method"] = rng.choice(_AUTH_METHODS)
        else:
            mcc = rng.choice(_NORMAL_CATS)
            df.at[i, "amount_rub"] = _realistic_amount(
                mcc, "mass", np.random.default_rng(rng.randint(0, 10**9)))
            df.at[i, "currency"] = "RUB"
            df.at[i, "merchant_category"] = mcc

    # session_end_ts раньше session_start_ts
    if sess_idx:
        idx = _pick(sess_idx, 0.005)
        for i in idx:
            ss = df.at[i, "session_start_ts"]
            if isinstance(ss, datetime):
                df.at[i, "session_end_ts"] = ss - timedelta(minutes=rng.randint(1, 30))

    return df
