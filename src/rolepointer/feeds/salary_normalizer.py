"""
RolePointer — Compensation & Multi-Currency Normalizer
Parses and standardizes compensation structures across global currencies:
- USD: $140k–$180k, $140,000 - $180,000, $75/hr
- EUR: €80k–€100k, 80,000 - 100,000 EUR
- GBP: £90k, £75,000 - £95,000
- INR: ₹30LPA, 25-35 LPA, 40 Lakhs INR
- Hourly: $60-$80/hr (standardized to 2080 annual hours)
- Equity-only caveats & Base vs. OTE distinctions
Normalizes all ranges to USD Annual Equivalent for unified ranking and filtering.
"""
from __future__ import annotations

import re
from typing import Optional
from rolepointer.models.schemas import NormalizedSalary


# ── FX Conversion Rates to USD (Annualized Standard) ──────────────────────────
FX_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.28,
    "CAD": 0.74,
    "AUD": 0.65,
    "INR": 0.012,  # 1 INR = $0.012 USD
}

HOURLY_ANNUAL_MULTIPLIER = 2080  # 40 hours/week * 52 weeks


def _clean_number(val_str: str) -> float:
    """Converts strings like '140k', '1.5M', '30LPA', '140,000', '140' to float."""
    s = val_str.lower().replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("₹", "").strip()
    if "k" in s:
        s = s.replace("k", "").strip()
        return float(s) * 1000.0
    if "m" in s:
        s = s.replace("m", "").strip()
        return float(s) * 1000000.0
    if "lpa" in s:
        s = s.replace("lpa", "").strip()
        return float(s) * 100000.0
    if "lakh" in s or "lac" in s:
        s = re.sub(r"[a-z]", "", s).strip()
        return float(s) * 100000.0
    return float(s)


def normalize_compensation(raw_text: Optional[str]) -> NormalizedSalary:
    """
    Parses and normalizes salary text into USD annual figures.
    Handles USD, EUR, GBP, INR LPA, Hourly, Equity-Only, and OTE ranges.
    """
    if not raw_text or not raw_text.strip():
        return NormalizedSalary(raw_text="", formatted_usd_equiv="Not Disclosed", confidence="NONE")

    text = raw_text.strip()
    lower_text = text.lower()
    is_equity_only = False

    # 1. Equity-Only Detection
    if any(k in lower_text for k in ["equity only", "0 salary", "unpaid", "equity grant only", "no cash compensation"]):
        return NormalizedSalary(
            raw_text=text,
            currency="USD",
            min_amount=0.0,
            max_amount=0.0,
            is_equity_only=True,
            annual_min_usd=0.0,
            annual_max_usd=0.0,
            formatted_usd_equiv="Equity Only (0 Base)",
            confidence="HIGH"
        )

    # 2. Identify Currency
    currency = "USD"
    fx_rate = 1.0
    if "€" in text or "eur" in lower_text:
        currency = "EUR"
        fx_rate = FX_RATES_TO_USD["EUR"]
    elif "£" in text or "gbp" in lower_text:
        currency = "GBP"
        fx_rate = FX_RATES_TO_USD["GBP"]
    elif "₹" in text or "inr" in lower_text or "lpa" in lower_text or "lakh" in lower_text:
        currency = "INR"
        fx_rate = FX_RATES_TO_USD["INR"]
    elif "cad" in lower_text:
        currency = "CAD"
        fx_rate = FX_RATES_TO_USD["CAD"]
    elif "aud" in lower_text:
        currency = "AUD"
        fx_rate = FX_RATES_TO_USD["AUD"]

    # 3. Hourly vs Annual Detection
    is_hourly = bool(re.search(r"/(?:hr|hour|h)\b|\bper\s+hour\b|\bhourly\b", lower_text))
    is_ote = bool(re.search(r"\bote\b|\bon[- ]target\s+earnings\b", lower_text))

    # 4. Extract Numbers & Ranges
    min_val: Optional[float] = None
    max_val: Optional[float] = None

    # Try Indian LPA pattern first if INR or 'lpa'/'lakh' present
    lpa_range_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lacs?)?", lower_text)
    if ("lpa" in lower_text or "lakh" in lower_text or currency == "INR") and lpa_range_match:
        try:
            v1 = float(lpa_range_match.group(1))
            v2 = float(lpa_range_match.group(2))
            if v1 < 1000 and v2 < 1000:  # e.g. 25 - 35 LPA
                min_val = v1 * 100000.0
                max_val = v2 * 100000.0
            else:
                min_val = v1
                max_val = v2
        except (ValueError, TypeError):
            pass

    # Generic Range Pattern: e.g. $140k - $180k, 140,000 - 180,000, 60-80/hr
    if min_val is None:
        range_match = re.search(
            r"[$€£₹]?\s*(\d+(?:,\d{3})*(?:\.\d+)?\s*[km]?)\s*(?:-|to|–|/)\s*[$€£₹]?\s*(\d+(?:,\d{3})*(?:\.\d+)?\s*[km]?)",
            lower_text
        )
        if range_match:
            try:
                g1 = range_match.group(1).strip()
                g2 = range_match.group(2).strip()
                if "k" in g2 and "k" not in g1 and "m" not in g1:
                    v1_raw = float(g1.replace(",", "")) * 1000.0
                else:
                    v1_raw = _clean_number(g1)
                v2_raw = _clean_number(g2)
                min_val = min(v1_raw, v2_raw)
                max_val = max(v1_raw, v2_raw)
            except (ValueError, TypeError):
                pass

    # Single value pattern: e.g. $150k, €90k, $75/hr, 30 LPA
    if min_val is None:
        single_match = re.search(r"[$€£₹]?\s*(\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|m|lpa|lakhs?|lacs?)?)", lower_text)
        if single_match:
            try:
                val = _clean_number(single_match.group(1))
                min_val = val
                max_val = val
            except (ValueError, TypeError):
                pass

    if min_val is None:
        return NormalizedSalary(
            raw_text=text,
            currency=currency,
            formatted_usd_equiv="Undetermined Format",
            confidence="LOW"
        )

    # If INR and raw parsed value was small (<1000, e.g. 25 or 30), scale to LPA
    if currency == "INR" and min_val < 1000:
        min_val = min_val * 100000.0
        max_val = (max_val or min_val)
        if max_val < 1000:
            max_val = max_val * 100000.0

    # 5. Convert to USD Annual Equivalent
    multiplier = HOURLY_ANNUAL_MULTIPLIER if is_hourly else 1.0
    annual_min_local = min_val * multiplier
    annual_max_local = (max_val or min_val) * multiplier

    annual_min_usd = round(annual_min_local * fx_rate, 2)
    annual_max_usd = round(annual_max_local * fx_rate, 2)

    # 6. Format Friendly String
    if is_equity_only:
        formatted = "Equity Only"
    elif annual_min_usd == annual_max_usd:
        if currency == "USD" and not is_hourly:
            formatted = f"${annual_min_usd/1000:,.0f}k/yr USD"
        else:
            formatted = f"${annual_min_usd/1000:,.0f}k/yr USD (from {text})"
    else:
        if currency == "USD" and not is_hourly:
            formatted = f"${annual_min_usd/1000:,.0f}k - ${annual_max_usd/1000:,.0f}k/yr USD"
        else:
            formatted = f"${annual_min_usd/1000:,.0f}k - ${annual_max_usd/1000:,.0f}k/yr USD (from {text})"

    if is_ote:
        formatted += " [OTE]"

    return NormalizedSalary(
        raw_text=text,
        currency=currency,
        min_amount=min_val,
        max_amount=max_val,
        is_hourly=is_hourly,
        is_annual=not is_hourly,
        is_equity_only=is_equity_only,
        is_ote=is_ote,
        base_min_usd=annual_min_usd if not is_ote else annual_min_usd * 0.75,
        base_max_usd=annual_max_usd if not is_ote else annual_max_usd * 0.75,
        annual_min_usd=annual_min_usd,
        annual_max_usd=annual_max_usd,
        formatted_usd_equiv=formatted,
        confidence="HIGH"
    )
