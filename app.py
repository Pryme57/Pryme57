"""
FAIR Risk Assessment Application
Factor Analysis of Information Risk (FAIR) - Quantitative Risk Calculator
Uses Monte Carlo simulation with PERT distributions to model uncertainty.
"""

import os
from datetime import date

import numpy as np
from flask import Flask, render_template, request

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.template_filter("format_number")
def format_number(value):
    return f"{int(value):,}"

N_SIMULATIONS = 10_000


# ---------------------------------------------------------------------------
# FAIR Simulation Engine
# ---------------------------------------------------------------------------

def pert_sample(minimum: float, most_likely: float, maximum: float, n: int = N_SIMULATIONS) -> np.ndarray:
    """
    Sample from a PERT (Program Evaluation and Review Technique) distribution,
    which approximates real-world uncertainty better than a uniform distribution.
    Internally maps to a Beta distribution.
    """
    minimum = float(minimum)
    most_likely = float(most_likely)
    maximum = float(maximum)

    if minimum > maximum:
        minimum, maximum = maximum, minimum
    most_likely = float(np.clip(most_likely, minimum, maximum))

    if maximum == minimum:
        return np.full(n, minimum)

    # PERT mean and variance
    mu = (minimum + 4.0 * most_likely + maximum) / 6.0
    sigma_sq = ((maximum - minimum) ** 2) / 36.0

    if sigma_sq == 0:
        return np.full(n, mu)

    # Convert to Beta distribution parameters
    alpha = ((mu - minimum) / (maximum - minimum)) * (
        (mu - minimum) * (maximum - mu) / sigma_sq - 1.0
    )
    beta = alpha * (maximum - mu) / (mu - minimum) if (mu - minimum) > 0 else 1.0

    if alpha <= 0 or beta <= 0 or not (np.isfinite(alpha) and np.isfinite(beta)):
        return np.random.uniform(minimum, maximum, n)

    return minimum + (maximum - minimum) * np.random.beta(alpha, beta, n)


def vulnerability_from_scales(threat_capability: float, control_strength: float) -> float:
    """
    Estimate the base Vulnerability probability.
    FAIR defines Vulnerability as P(Threat Capability > Resistance Strength).
    We model this using a sigmoid centred on the difference of the two 1-10 scales,
    yielding intuitive outputs:
      TCap == CS  →  50%
      TCap >> CS  →  ~95%+
      TCap << CS  →  ~5%-
    """
    diff = threat_capability - control_strength
    return float(1.0 / (1.0 + np.exp(-diff)))


def build_histogram(samples: np.ndarray, bins: int = 20) -> dict:
    """Return histogram data suitable for Chart.js."""
    counts, edges = np.histogram(samples, bins=bins)
    labels = [f"${int(edges[i]):,}" for i in range(len(edges) - 1)]
    return {"labels": labels, "values": counts.tolist()}


def risk_level_from_ale(ale_median: float) -> dict:
    """Classify risk based on the median Annual Loss Exposure."""
    if ale_median < 10_000:
        return {
            "level": "Low",
            "color": "success",
            "badge": "bg-success",
            "description": (
                "Risk is within acceptable tolerance for most organisations. "
                "Continue monitoring and maintain current controls."
            ),
            "recommendations": [
                "Document current controls and ensure they remain effective.",
                "Schedule periodic reviews (annually) of threat landscape.",
                "Maintain security awareness training.",
            ],
        }
    elif ale_median < 100_000:
        return {
            "level": "Medium",
            "color": "warning",
            "badge": "bg-warning text-dark",
            "description": (
                "Risk warrants attention. Mitigation options should be evaluated "
                "against their cost of implementation."
            ),
            "recommendations": [
                "Conduct a cost-benefit analysis on additional controls.",
                "Prioritise improving the weakest control layers.",
                "Increase monitoring frequency for the identified threat communities.",
                "Review and update incident response plans.",
            ],
        }
    elif ale_median < 1_000_000:
        return {
            "level": "High",
            "color": "danger",
            "badge": "bg-danger",
            "description": (
                "Risk is significant and requires a formal treatment plan with "
                "executive sponsorship and near-term milestones."
            ),
            "recommendations": [
                "Escalate to executive/board level immediately.",
                "Initiate a formal risk treatment project.",
                "Consider risk transfer via cyber insurance.",
                "Strengthen resistance strength — close the gap vs. threat capability.",
                "Implement continuous monitoring and threat intelligence feeds.",
            ],
        }
    else:
        return {
            "level": "Critical",
            "color": "dark",
            "badge": "bg-dark",
            "description": (
                "Risk is at a critical level demanding immediate executive action, "
                "significant investment, and possibly risk transfer strategies."
            ),
            "recommendations": [
                "Convene an emergency response team immediately.",
                "Engage external security expertise for an independent assessment.",
                "Implement emergency controls while a permanent solution is designed.",
                "Evaluate risk transfer (cyber insurance, contractual liability limits).",
                "Consider whether the initiative should proceed without major redesign.",
                "Communicate risk posture transparently to stakeholders.",
            ],
        }


def run_fair_simulation(fd: dict) -> dict:
    """
    Execute the FAIR Monte Carlo simulation.

    FAIR ontology summary
    ---------------------
    Risk = Loss Event Frequency (LEF) × Probable Loss Magnitude (PLM)
    LEF  = Threat Event Frequency (TEF) × Vulnerability (V)
    PLM  = Primary Losses + Secondary Losses
    """
    n = N_SIMULATIONS

    # --- Threat Event Frequency (TEF) ---
    tef = pert_sample(fd["tef_min"], fd["tef_likely"], fd["tef_max"], n)

    # --- Vulnerability ---
    tcap = float(fd["threat_capability"])
    cs = float(fd["control_strength"])
    v_base = vulnerability_from_scales(tcap, cs)

    # Add calibrated uncertainty around the base estimate (±0.25 bounded)
    v_min = max(0.01, v_base - 0.25)
    v_max = min(0.99, v_base + 0.25)
    v_samples = pert_sample(v_min, v_base, v_max, n)

    # --- Loss Event Frequency ---
    lef = tef * v_samples

    # --- Primary Loss Magnitude ---
    prod  = pert_sample(fd["prod_min"],  fd["prod_likely"],  fd["prod_max"],  n)
    resp  = pert_sample(fd["resp_min"],  fd["resp_likely"],  fd["resp_max"],  n)
    repl  = pert_sample(fd["repl_min"],  fd["repl_likely"],  fd["repl_max"],  n)

    # --- Secondary Loss Magnitude ---
    fines = pert_sample(fd["fines_min"], fd["fines_likely"], fd["fines_max"], n)
    comp  = pert_sample(fd["comp_min"],  fd["comp_likely"],  fd["comp_max"],  n)
    rep   = pert_sample(fd["rep_min"],   fd["rep_likely"],   fd["rep_max"],   n)

    plm = prod + resp + repl + fines + comp + rep

    # --- Annual Loss Exposure ---
    ale = lef * plm

    ale_median = float(np.percentile(ale, 50))
    risk_meta  = risk_level_from_ale(ale_median)

    # Loss breakdown medians for charting
    loss_breakdown = {
        "Productivity Loss":  float(np.median(prod)),
        "Response Cost":      float(np.median(resp)),
        "Replacement Cost":   float(np.median(repl)),
        "Fines & Legal":      float(np.median(fines)),
        "Competitive Loss":   float(np.median(comp)),
        "Reputation Damage":  float(np.median(rep)),
    }

    return {
        # ALE percentiles
        "ale_10":  float(np.percentile(ale, 10)),
        "ale_25":  float(np.percentile(ale, 25)),
        "ale_50":  ale_median,
        "ale_75":  float(np.percentile(ale, 75)),
        "ale_90":  float(np.percentile(ale, 90)),
        "ale_mean": float(np.mean(ale)),
        # LEF percentiles
        "lef_10":  float(np.percentile(lef, 10)),
        "lef_50":  float(np.percentile(lef, 50)),
        "lef_90":  float(np.percentile(lef, 90)),
        # PLM percentiles
        "plm_10":  float(np.percentile(plm, 10)),
        "plm_50":  float(np.percentile(plm, 50)),
        "plm_90":  float(np.percentile(plm, 90)),
        # Inputs echoed back
        "vulnerability": v_base,
        "tcap": tcap,
        "cs": cs,
        # Chart data
        "ale_histogram": build_histogram(ale),
        "loss_breakdown": loss_breakdown,
        # Risk classification
        **risk_meta,
        # Meta
        "assessment_date": date.today().strftime("%B %d, %Y"),
        "simulations": N_SIMULATIONS,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _float(fd: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(fd.get(key, default))
    except (ValueError, TypeError):
        return default


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/assess", methods=["POST"])
def assess():
    fd_raw = request.form.to_dict()

    # Normalise all numeric fields
    numeric_keys = [
        "tef_min", "tef_likely", "tef_max",
        "threat_capability", "control_strength",
        "prod_min",  "prod_likely",  "prod_max",
        "resp_min",  "resp_likely",  "resp_max",
        "repl_min",  "repl_likely",  "repl_max",
        "fines_min", "fines_likely", "fines_max",
        "comp_min",  "comp_likely",  "comp_max",
        "rep_min",   "rep_likely",   "rep_max",
    ]
    fd = {k: _float(fd_raw, k) for k in numeric_keys}
    fd["project_name"]    = fd_raw.get("project_name", "Unnamed Project")
    fd["asset_type"]      = fd_raw.get("asset_type", "")
    fd["industry"]        = fd_raw.get("industry", "")
    fd["threat_community"]= fd_raw.get("threat_community", "")
    fd["asset_description"] = fd_raw.get("asset_description", "")

    try:
        results = run_fair_simulation(fd)
        return render_template("results.html", results=results, form=fd)
    except Exception as exc:  # noqa: BLE001
        return render_template("index.html", error=str(exc))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
