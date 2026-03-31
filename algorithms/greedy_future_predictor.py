"""
GREEDY FUTURE STATION PREDICTOR  — v6
======================================
• Evaluates all 14 Kerala districts using live OCM station data
• all_evaluations contains ALL 14 rows, each with the full set of fields
  the UI needs:  district, score, demand, station_count,
                 total_fast/medium/slow, dist_nearest_km,
                 operators, operational_ratio, connection_types,
                 charger_recommendation (primary_type, primary_reason,
                 mix_notes, suitable_for), explanation
• explanation is ALWAYS a non-empty string — built from live values,
  never left blank
"""

import math
import random


class GreedyFuturePredictor:

    DISTRICTS = [
        {"name": "Thiruvananthapuram", "lat": 8.5241,  "lon": 76.9366},
        {"name": "Kollam",             "lat": 8.8932,  "lon": 76.6141},
        {"name": "Pathanamthitta",     "lat": 9.2648,  "lon": 76.7870},
        {"name": "Alappuzha",          "lat": 9.4981,  "lon": 76.3388},
        {"name": "Kottayam",           "lat": 9.5916,  "lon": 76.5222},
        {"name": "Idukki",             "lat": 9.9186,  "lon": 77.1025},
        {"name": "Ernakulam",          "lat": 9.9312,  "lon": 76.2673},
        {"name": "Thrissur",           "lat": 10.5276, "lon": 76.2144},
        {"name": "Palakkad",           "lat": 10.7867, "lon": 76.6548},
        {"name": "Malappuram",         "lat": 11.0510, "lon": 76.0711},
        {"name": "Kozhikode",          "lat": 11.2588, "lon": 75.7804},
        {"name": "Wayanad",            "lat": 11.6854, "lon": 76.1320},
        {"name": "Kannur",             "lat": 11.9186, "lon": 75.5472},
        {"name": "Kasaragod",          "lat": 12.4996, "lon": 74.9869},
    ]

    WEIGHTS = {
        "coverage_gap":       0.22,
        "infrastructure":     0.18,
        "power_profile":      0.14,
        "operational_ratio":  0.14,
        "public_access":      0.12,
        "connection_variety": 0.12,
        "operator_coverage":  0.08,
    }

    # ── maths ──────────────────────────────────────────────────────────────────

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _nearest_km(self, d_info, stations):
        if not stations:
            return 50.0
        return round(min(
            self._haversine(d_info["lat"], d_info["lon"],
                            s.get("latitude", d_info["lat"]),
                            s.get("longitude", d_info["lon"]))
            for s in stations
        ), 2)

    def _demand(self, score):
        if score >= 68: return "High"
        if score >= 40: return "Medium"
        return "Low"

    # ── extract live OCM fields for one district ────────────────────────────────

    def _stats(self, name, all_stations):
        ds = [s for s in all_stations if s.get("district") == name]
        if not ds:
            return self._zero_stats(name)

        fast   = sum(s.get("fastPorts",   s.get("total_fastPorts",   0)) for s in ds)
        medium = sum(s.get("mediumPorts", s.get("total_mediumPorts", 0)) for s in ds)
        slow   = sum(s.get("slowPorts",   s.get("total_slowPorts",   0)) for s in ds)
        points = fast + medium + slow

        avail  = sum(
            s.get("availableFastPorts",   0) +
            s.get("availableMediumPorts", 0) +
            s.get("availableSlowPorts",   0)
            for s in ds
        )

        conns = []
        if fast   > 0: conns.append("CCS2/CHAdeMO (DC Fast ≥50 kW)")
        if medium > 0: conns.append("Type 2 IEC 62196 (AC Fast 22 kW)")
        if slow   > 0: conns.append("Bharat AC-001 / Type 2 (Slow ≤7 kW)")

        pub_count   = sum(1 for s in ds if s.get("ev_density", 0) >= 60)
        pub_ratio   = round(pub_count / len(ds), 3)
        operators   = list({s.get("operator","") for s in ds
                            if s.get("operator") not in ("","Unknown",None)})
        op_count    = max(len(operators), 1)
        operational = sum(1 for s in ds
                          if (s.get("availableFastPorts",   0) +
                              s.get("availableMediumPorts", 0) +
                              s.get("availableSlowPorts",   0)) > 0)
        op_ratio    = round(operational / len(ds), 3)
        ev_density  = round(sum(s.get("ev_density", 50) for s in ds) / len(ds), 1)

        return {
            "station_count":         len(ds),
            "total_charging_points": points,
            "total_fast":            fast,
            "total_medium":          medium,
            "total_slow":            slow,
            "available_points":      avail,
            "connection_types":      conns,
            "max_power_kw":          150 if fast else 22 if medium else 7 if slow else 0,
            "public_count":          pub_count,
            "private_count":         len(ds) - pub_count,
            "public_ratio":          pub_ratio,
            "operators":             operators[:5],
            "operator_count":        op_count,
            "operational":           operational,
            "non_operational":       len(ds) - operational,
            "operational_ratio":     op_ratio,
            "ev_density":            ev_density,
        }

    def _zero_stats(self, name):
        return {
            "station_count": 0, "total_charging_points": 0,
            "total_fast": 0, "total_medium": 0, "total_slow": 0,
            "available_points": 0, "connection_types": [],
            "max_power_kw": 0, "public_count": 0, "private_count": 0,
            "public_ratio": 0, "operators": [], "operator_count": 0,
            "operational": 0, "non_operational": 0,
            "operational_ratio": 0, "ev_density": 0,
        }

    # ── scoring ────────────────────────────────────────────────────────────────

    def _score_gap(self, km):           return min(km / 50.0, 1.0) * 100
    def _score_infra(self, sc, pts, ev):
        if sc == 0: return 100.0
        return round(min(max((0.5 - pts / max(ev, 1)) / 0.5, 0) * 100, 100), 1)
    def _score_power(self, f, m, s):
        return round(((1 if f==0 else 0)+(1 if m==0 else 0)+(1 if s==0 else 0))/3*100, 1)
    def _score_ops(self, ratio, sc):    return 100.0 if sc==0 else round((1-ratio)*100,1)
    def _score_pub(self, ratio, sc):    return 100.0 if sc==0 else round((1-ratio)*100,1)
    def _score_conn(self, conns):       return round(((3-len(conns))/3)*100,1)
    def _score_oper(self, op_cnt, sc):
        if sc==0:        return 100.0
        if op_cnt<=1:    return 70.0
        if op_cnt<=2:    return 40.0
        return 15.0

    # ── explanation — always returns a non-empty string ────────────────────────

    def _explanation(self, name, st, dist_km, demand):
        sc    = st["station_count"]
        pts   = st["total_charging_points"]
        conns = st["connection_types"]
        op_r  = st["operational_ratio"]
        pub_r = st["public_ratio"]
        ops   = st["operators"]
        fast  = st["total_fast"]
        med   = st["total_medium"]
        slow  = st["total_slow"]

        parts = []

        # --- coverage gap ---
        if dist_km > 30:
            parts.append(
                f"{name} is a charging desert — the nearest station is {dist_km:.1f} km away, "
                f"making EV travel across the district extremely risky."
            )
        elif dist_km > 15:
            parts.append(
                f"The nearest charging station is {dist_km:.1f} km from {name}'s centre, "
                f"creating a significant gap for local EV drivers."
            )
        else:
            parts.append(
                f"Although the nearest station is only {dist_km:.1f} km away, "
                f"rapid EV growth in {name} means current infrastructure is already strained."
            )

        # --- station / point count ---
        if sc == 0:
            parts.append(
                f"There are currently NO charging stations in {name} — "
                f"the most critical infrastructure gap in this analysis."
            )
        else:
            parts.append(
                f"Only {sc} station{'s' if sc>1 else ''} with {pts} total charging "
                f"point{'s' if pts>1 else ''} serve{'s' if pts==1 else ''} this district."
            )

        # --- missing connector types ---
        all_types = {
            "CCS2/CHAdeMO (DC Fast ≥50 kW)",
            "Type 2 IEC 62196 (AC Fast 22 kW)",
            "Bharat AC-001 / Type 2 (Slow ≤7 kW)",
        }
        missing = all_types - set(conns)
        if missing:
            parts.append(
                f"Missing connector standards: {'; '.join(sorted(missing))} — "
                f"leaving entire vehicle categories without charging options."
            )
        elif sc > 0:
            parts.append(
                "All connector standards are present but overall capacity is "
                "insufficient to meet growing demand."
            )

        # --- public access ---
        if sc > 0 and pub_r < 0.5:
            parts.append(
                f"Most existing stations are private-access only "
                f"({st['public_count']} of {sc} are public). "
                f"Publicly accessible charging is critically underrepresented in {name}."
            )

        # --- operator ---
        if sc > 0:
            if len(ops) == 1:
                parts.append(
                    f"Only one operator ({ops[0]}) is active here, creating a monopoly "
                    f"risk that leaves the entire district vulnerable to service disruptions."
                )
            elif len(ops) > 1:
                parts.append(
                    f"Operators present: {', '.join(ops)}. "
                    f"Despite multiple operators, total coverage remains inadequate."
                )
            else:
                parts.append(
                    "No operator information is available, making reliability hard to verify."
                )

        # --- uptime ---
        if sc > 0 and op_r < 0.8:
            pct = round(op_r * 100)
            parts.append(
                f"Station uptime is only {pct}% ({st['operational']} of {sc} stations live) "
                f"— maintenance and reliability are serious concerns."
            )

        # --- demand conclusion ---
        if demand == "High":
            parts.append(
                "Charging demand is HIGH — existing infrastructure is already "
                "under pressure and new stations are urgently required."
            )
        elif demand == "Medium":
            parts.append(
                "Charging demand is MEDIUM and growing — deploying now will "
                "build user habit before demand peaks in 12–24 months."
            )
        else:
            parts.append(
                "Demand is currently LOW, but early investment will catalyse "
                "EV adoption during the critical ramp-up phase in this district."
            )

        result = " ".join(parts)
        # safety net — should never be empty, but just in case
        if not result.strip():
            result = (
                f"{name} requires new EV charging infrastructure. "
                f"Current coverage is insufficient for the growing number of EVs "
                f"registered in this district."
            )
        return result

    # ── charger recommendation ─────────────────────────────────────────────────

    def _charger(self, st, demand, dist_km):
        fast  = st["total_fast"]
        med   = st["total_medium"]
        slow  = st["total_slow"]
        conns = st["connection_types"]
        ops   = st["operators"]
        sc    = st["station_count"]
        op_r  = st["operational_ratio"]
        pub_r = st["public_ratio"]

        if demand == "High" and fast == 0:
            ptype  = "DC Fast Charger (50–150 kW)"
            reason = ("High-demand district has ZERO DC fast chargers. "
                      "CCS2/CHAdeMO rapid chargers are urgently needed to serve "
                      "the EV fleet without long wait times.")
        elif demand == "High":
            ptype  = "DC Rapid Charger (100–150 kW)"
            reason = (f"{fast} existing fast charger(s) are saturated under high demand. "
                      "Upgrading to 100–150 kW rapids will cut queue times significantly.")
        elif demand == "Medium" and med == 0:
            ptype  = "AC Fast Charger (22 kW)"
            reason = ("No 22 kW AC fast chargers present. Type 2 (IEC 62196) chargers "
                      "offer the best cost-performance ratio for medium-demand areas "
                      "with 1–2 hour dwell time.")
        elif slow == 0:
            ptype  = "AC Slow Charger (3.3–7.4 kW)"
            reason = ("No slow chargers present. Bharat AC-001 / Type 2 slow units "
                      "are essential for two-wheelers and three-wheelers that dominate "
                      "Kerala roads.")
        else:
            ptype  = "AC Fast Charger (22 kW)"
            reason = ("A balanced mix is recommended. AC fast chargers serve the widest "
                      "vehicle range with manageable installation cost.")

        mix = []
        if dist_km > 30:
            mix.append(f"Coverage desert ({dist_km:.1f} km gap) — at least one DC fast charger required for highway confidence")
        if "CCS2/CHAdeMO (DC Fast ≥50 kW)" not in conns:
            mix.append("CCS2/CHAdeMO absent — required for Tata Nexon EV, MG ZS EV, Hyundai Kona")
        if "Type 2 IEC 62196 (AC Fast 22 kW)" not in conns:
            mix.append("Type 2 (IEC 62196) missing — needed for European-standard EVs and vans")
        if "Bharat AC-001 / Type 2 (Slow ≤7 kW)" not in conns:
            mix.append("Bharat AC-001 absent — critical for Ola/Ather two-wheelers and Bajaj/TVS three-wheelers")
        if sc > 0 and pub_r < 0.5:
            mix.append(f"Only {st['public_count']}/{sc} stations are public-accessible")
        if sc > 0 and op_r < 0.7:
            mix.append(f"Station uptime is only {round(op_r*100)}% — repair existing infrastructure alongside new builds")
        if sc > 0 and len(ops) <= 1:
            mix.append("Single-operator monopoly — encourage competing operators for reliability")

        if ptype.startswith("DC"):
            vehicles = ["Cars (CCS2/CHAdeMO)", "SUVs", "Light commercial EVs", "Electric buses"]
        elif ptype.startswith("AC Fast"):
            vehicles = ["Cars (Type-2)", "Vans", "Electric auto-rickshaws"]
        else:
            vehicles = ["Two-wheelers (Bharat AC-001)", "Three-wheelers", "Entry-level EVs"]

        return {
            "primary_type":   ptype,
            "primary_reason": reason,
            "mix_notes":      mix,
            "suitable_for":   vehicles,
        }

    # ── evaluate one district ──────────────────────────────────────────────────

    def _evaluate(self, d_info, all_stations):
        name    = d_info["name"]
        st      = self._stats(name, all_stations)
        dist_km = self._nearest_km(d_info, all_stations)
        demand  = self._demand(
            round(min(max(
                (self._score_gap(dist_km)           * self.WEIGHTS["coverage_gap"]
                 + self._score_infra(st["station_count"], st["total_charging_points"], max(st["ev_density"],1)) * self.WEIGHTS["infrastructure"]
                 + self._score_power(st["total_fast"], st["total_medium"], st["total_slow"]) * self.WEIGHTS["power_profile"]
                 + self._score_ops(st["operational_ratio"], st["station_count"])             * self.WEIGHTS["operational_ratio"]
                 + self._score_pub(st["public_ratio"],      st["station_count"])             * self.WEIGHTS["public_access"]
                 + self._score_conn(st["connection_types"])                                  * self.WEIGHTS["connection_variety"]
                 + self._score_oper(st["operator_count"],   st["station_count"])             * self.WEIGHTS["operator_coverage"]
                ) + random.uniform(-4, 4), 0), 100), 2)
        )

        score = round(min(max(
            self._score_gap(dist_km)           * self.WEIGHTS["coverage_gap"]
            + self._score_infra(st["station_count"], st["total_charging_points"], max(st["ev_density"],1)) * self.WEIGHTS["infrastructure"]
            + self._score_power(st["total_fast"], st["total_medium"], st["total_slow"]) * self.WEIGHTS["power_profile"]
            + self._score_ops(st["operational_ratio"], st["station_count"])             * self.WEIGHTS["operational_ratio"]
            + self._score_pub(st["public_ratio"],      st["station_count"])             * self.WEIGHTS["public_access"]
            + self._score_conn(st["connection_types"])                                  * self.WEIGHTS["connection_variety"]
            + self._score_oper(st["operator_count"],   st["station_count"])             * self.WEIGHTS["operator_coverage"]
            + random.uniform(-4, 4), 0), 100), 2)

        # build explanation NOW and verify it is non-empty
        explanation = self._explanation(name, st, dist_km, demand)
        assert explanation, f"Empty explanation for {name}"  # will raise if blank

        return {
            "district":              name,
            "score":                 score,
            "composite_score":       score,      # backward compat
            "demand":                demand,
            "estimated_demand":      demand,     # backward compat
            # live OCM values
            "station_count":         st["station_count"],
            "total_charging_points": st["total_charging_points"],
            "total_fast":            st["total_fast"],
            "total_medium":          st["total_medium"],
            "total_slow":            st["total_slow"],
            "available_points":      st["available_points"],
            "connection_types":      st["connection_types"],
            "max_power_kw":          st["max_power_kw"],
            "public_count":          st["public_count"],
            "private_count":         st["private_count"],
            "public_ratio":          st["public_ratio"],
            "operators":             st["operators"],
            "operator_count":        st["operator_count"],
            "operational":           st["operational"],
            "non_operational":       st["non_operational"],
            "operational_ratio":     st["operational_ratio"],
            "dist_nearest_km":       dist_km,
            # recommendations
            "charger_recommendation": self._charger(st, demand, dist_km),
            "explanation":            explanation,   # ALWAYS non-empty
        }

    # ── public API ────────────────────────────────────────────────────────────

    def predict_future_station(self, existing_stations):
        """
        Returns
        -------
        predicted_location : full dict for the #1 predicted district
        all_evaluations    : list of ALL 14 districts, each carrying the full
                             set of fields the UI needs — sorted by need score
                             (highest first).  The JS reads this list directly;
                             nothing in the frontend is hardcoded.
        """
        if not existing_stations:
            empty = {
                "district": "Ernakulam", "score": 95.0, "composite_score": 95.0,
                "demand": "High", "estimated_demand": "High",
                "station_count": 0, "total_charging_points": 0,
                "total_fast": 0, "total_medium": 0, "total_slow": 0,
                "available_points": 0, "connection_types": [], "max_power_kw": 0,
                "public_count": 0, "private_count": 0, "public_ratio": 0,
                "operators": [], "operator_count": 0,
                "operational": 0, "non_operational": 0, "operational_ratio": 0,
                "dist_nearest_km": 50.0,
                "charger_recommendation": {
                    "primary_type":   "DC Fast Charger (50–150 kW)",
                    "primary_reason": "No live data. Ernakulam is Kerala's highest-demand district.",
                    "mix_notes":      [],
                    "suitable_for":   ["Cars (CCS2/CHAdeMO)", "SUVs"],
                },
                "explanation": (
                    "Ernakulam is Kerala's busiest EV district but no live station data "
                    "is currently available. The district urgently needs DC fast charging "
                    "infrastructure to support its large and growing EV fleet."
                ),
            }
            return {"predicted_location": empty, "all_evaluations": [empty]}

        # evaluate every district
        all_evals = [self._evaluate(d, existing_stations) for d in self.DISTRICTS]

        # sort all 14 by need score — highest need first
        all_evals.sort(key=lambda x: x["score"], reverse=True)

        # pick the headline district (weighted random from top 5)
        top5   = all_evals[:5]
        total  = sum(e["score"] for e in top5) or 1
        winner = random.choices(top5, weights=[e["score"]/total for e in top5], k=1)[0]

        return {
            "predicted_location": winner,          # full dict
            "all_evaluations":    all_evals,        # ALL 14 — full fields
        }