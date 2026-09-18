#!/usr/bin/env python3
"""trips.py — detect individual trips from PocketSmith exports.

Input: list of monthly PS JSON exports.
Output: ordered list of trip dicts with location, dates, totals, breakdown.

Algorithm:
    1. Collect txns selected by configured category IDs or generic trip category titles
    2. Anchor detection: payee matches a generic travel keyword or optional configured amount
  3. Anchor clustering: each anchor grabs nearby trip txns within [-2, +10] days
  4. Orphan clustering: remaining txns grouped by 6-day gaps (keep >= 2)
  5. Location detection: scan payee for ~60 city/country keywords
  6. Merge: same-location clusters with <= 4 day gap merged
"""

import json
import os
from collections import Counter
from datetime import date as D

DEFAULT_TRIP_KEYWORDS = ("AIRLINE", "HOTEL", "RAIL", "CAR RENTAL")


def detect_location(payee: str, location_keywords=None) -> str:
    p = payee.upper()
    # Longest configured match wins over a shorter configured match.
    best = None
    best_len = 0
    for k, loc in (location_keywords or {}).items():
        if k in p and len(k) > best_len:
            best = loc
            best_len = len(k)
    return best or "Unknown"


def is_trip_anchor(
    payee: str, amount: float, trip_keywords=None, anchor_amount=None
) -> bool:
    p = payee.upper()
    for kw in trip_keywords or DEFAULT_TRIP_KEYWORDS:
        if kw in p:
            return True
    return anchor_amount is not None and abs(amount) >= anchor_amount


def _load_trip_txns(export_paths, trip_category_ids=None):
    """Load all trip-categorized txns across the given export files."""
    trip_txns = []
    for fp in export_paths:
        with open(fp) as f:
            d = json.load(f)
        month = d.get("month", os.path.basename(fp).replace(".json", ""))
        for t in d.get("transactions", []):
            c = t.get("category") or {}
            category_id = str(c.get("id", ""))
            category_title = c.get("title", "")
            if (trip_category_ids and category_id in trip_category_ids) or (
                not trip_category_ids and "trip" in category_title.lower()
            ):
                trip_txns.append(
                    {
                        "month": month,
                        "date": t["date"],
                        "amount": float(t["amount"]),
                        "payee": (t.get("payee") or "").upper(),
                        "cat": c.get("title", ""),
                        "account": (t.get("account") or {}).get("name", ""),
                    }
                )
    trip_txns.sort(key=lambda x: x["date"])
    return trip_txns


def detect_trips(
    export_paths,
    gap_days: int = 6,
    merge_gap: int = 6,
    trip_category_ids=None,
    location_keywords=None,
    trip_keywords=None,
    anchor_amount=None,
    split_gap_days=None,
):
    """Return ordered list of detected trips."""
    txns = _load_trip_txns(export_paths, trip_category_ids)
    if not txns:
        return []

    # 1) anchors
    anchors = [
        t
        for t in txns
        if is_trip_anchor(t["payee"], t["amount"], trip_keywords, anchor_amount)
    ]
    used = set()
    clusters = []
    for a in anchors:
        if a["date"] in used:
            continue
        ad = D.fromisoformat(a["date"])
        members = []
        for t in txns:
            if t["date"] in used:
                continue
            td = D.fromisoformat(t["date"])
            if -2 <= (td - ad).days <= 10:
                members.append(t)
        for m in members:
            used.add(m["date"])
        members.sort(key=lambda x: x["date"])
        if members:
            clusters.append(members)

    # 2) orphan cluster
    leftover = [t for t in txns if t["date"] not in used]
    if leftover:
        cur = [leftover[0]]
        prev = D.fromisoformat(leftover[0]["date"])
        for t in leftover[1:]:
            td = D.fromisoformat(t["date"])
            if (td - prev).days <= gap_days:
                cur.append(t)
            else:
                if len(cur) >= 2:
                    clusters.append(cur)
                cur = [t]
            prev = td
        if len(cur) >= 2:
            clusters.append(cur)
    clusters.sort(key=lambda c: c[0]["date"])

    # 2b) Split sparse clusters before merging nearby same-country clusters.
    split_gap = gap_days if split_gap_days is None else split_gap_days
    split_clusters = []
    for c in clusters:
        sub = []
        prev_d = None
        for t in sorted(c, key=lambda x: x["date"]):
            from datetime import date as DD

            td = DD.fromisoformat(t["date"])
            if prev_d is None:
                sub = [t]
            else:
                if (td - prev_d).days > split_gap:
                    if sub:
                        split_clusters.append(sub)
                    sub = [t]
                else:
                    sub.append(t)
            prev_d = td
        if sub:
            split_clusters.append(sub)
    clusters = split_clusters
    clusters.sort(key=lambda c: c[0]["date"])

    # 3) detect location per cluster. Group by COUNTRY (second part of
    # "City, Country" loc string) so 'Tokyo, Japan' + 'Yokohama, Japan' +
    # 'Japan' all collapse to Japan. Then within country, prefer the most
    # specific city.
    annotated = []
    for c in clusters:
        from collections import defaultdict as DD

        country_locs = DD(Counter)  # country → Counter of city
        for t in c:
            l = detect_location(t["payee"], location_keywords)
            if l and l != "Unknown":
                # LOCATIONS dict uses "City, Country" format; country is last
                if "," in l:
                    city, country = l.rsplit(", ", 1)
                else:
                    country, city = l, l
                country_locs[country][city] += 1
        if not country_locs:
            annotated.append((c, "Unknown"))
            continue
        # Pick country with most votes
        best_country = max(
            country_locs.keys(), key=lambda k: sum(country_locs[k].values())
        )
        cities = country_locs[best_country]
        best_city = cities.most_common(1)[0][0]
        # Format: "Country: City" — country first, split(':', 1)[0] is country
        if best_city == best_country:
            loc = best_country
        else:
            loc = f"{best_country}: {best_city}"
        annotated.append((c, loc))

    # 4) merge same-COUNTRY clusters (ignore city difference if same country)
    def loc_country(loc):
        # Loc format: "Country: City" or just "Country" — country is the prefix
        if loc == "Unknown":
            return "Unknown"
        return loc.split(":", 1)[0]

    merged = []
    for c, loc in annotated:
        cur_country = loc_country(loc)
        if (
            merged
            and cur_country != "Unknown"
            and loc_country(merged[-1][1]) == cur_country
        ):
            prev_c = merged[-1][0]
            pd_ = D.fromisoformat(prev_c[-1]["date"])
            cd = D.fromisoformat(c[0]["date"])
            if (cd - pd_).days <= merge_gap:
                # Keep the more specific (with city) one
                new_loc = loc if ":" in loc else merged[-1][1]
                merged[-1] = (prev_c + c, new_loc)
                continue
        merged.append((c, loc))

    # 4b) inheritance pass: if an 'Unknown' cluster is sandwiched between
    # two same-country clusters within merge_gap*2, inherit the country.
    if len(merged) >= 3:
        for i in range(1, len(merged) - 1):
            cur_c, cur_loc = merged[i]
            prev_c, prev_loc = merged[i - 1]
            next_c, next_loc = merged[i + 1]
            if (
                cur_loc == "Unknown"
                and loc_country(prev_loc) == loc_country(next_loc)
                and loc_country(prev_loc) != "Unknown"
            ):
                pd_ = D.fromisoformat(prev_c[-1]["date"])
                nd = D.fromisoformat(next_c[0]["date"])
                if (nd - pd_).days <= merge_gap * 2 + 14:
                    merged[i] = (cur_c, prev_loc)
        # Re-merge after inheritance
        re_merged = []
        for c, loc in merged:
            cur_country = loc_country(loc)
            if (
                re_merged
                and cur_country != "Unknown"
                and loc_country(re_merged[-1][1]) == cur_country
            ):
                prev_c = re_merged[-1][0]
                pd_ = D.fromisoformat(prev_c[-1]["date"])
                cd = D.fromisoformat(c[0]["date"])
                if (cd - pd_).days <= merge_gap:
                    new_loc = loc if ":" in loc else re_merged[-1][1]
                    re_merged[-1] = (prev_c + c, new_loc)
                    continue
            re_merged.append((c, loc))
        merged = re_merged

    # 5) build trip dicts
    trips = []
    for i, (members, loc) in enumerate(merged):
        sd = members[0]["date"]
        ed = members[-1]["date"]
        days = (D.fromisoformat(ed) - D.fromisoformat(sd)).days + 1
        tot = sum(x["amount"] for x in members)
        per_day = tot / max(days, 1)
        months = sorted(set(x["month"] for x in members))
        by_type = {}
        for x in members:
            by_type.setdefault(x["cat"], {"count": 0, "amount": 0.0})
            by_type[x["cat"]]["count"] += 1
            by_type[x["cat"]]["amount"] += x["amount"]
        by_account = {}
        for x in members:
            by_account.setdefault(x["account"], 0.0)
            by_account[x["account"]] += x["amount"]
        trips.append(
            {
                "idx": i + 1,
                "location": loc,
                "start": sd,
                "end": ed,
                "days": days,
                "months": months,
                "txn_count": len(members),
                "total": round(tot, 2),
                "per_day": round(per_day, 2),
                "by_type": by_type,
                "by_account": by_account,
                "txns": members,
            }
        )
    return trips


def trips_summary(trips):
    """Top-line summary numbers for the trips section."""
    if not trips:
        return {
            "n": 0,
            "total": 0,
            "avg_per_day": 0,
            "longest": None,
            "costliest_per_day": None,
        }
    total = sum(abs(t["total"]) for t in trips)
    avg_pd = total / sum(max(t["days"], 1) for t in trips)
    longest = max(trips, key=lambda t: t["days"])
    costliest_pd = min(
        trips, key=lambda t: t["per_day"]
    )  # most negative = most expensive/day
    return {
        "n": len(trips),
        "total": round(total, 2),
        "avg_per_day": round(avg_pd, 2),
        "longest": longest,
        "costliest_per_day": costliest_pd,
    }


if __name__ == "__main__":
    raise SystemExit(
        "Unsupported: legacy trips.py CLI accepts arbitrary export paths. "
        "Use a current report CLI with --input-kind and strict month inputs."
    )
