from __future__ import annotations

from openai import OpenAI

SYSTEM = (
    "Du bist ein analytischer Assistent. "
    "Schreibe kurze, klare, deutschsprachige Stichpunkte zu betriebswirtschaftlichen Auffälligkeiten."
)


def write_notes(api_key: str, model: str, date_str: str, anomalies: list[dict]) -> str:
    if not anomalies:
        return ""
    client = OpenAI(api_key=api_key)
    bullet_points = []
    for a in anomalies:
        metric = a.get("metric")
        value = a.get("value")
        direction = "deutlich höher" if a.get("flag") == "green" else "deutlich niedriger"
        norm = a.get("norm")
        bullet_points.append(
            f"- {metric}: {direction} als üblich "
            f"(Wert {value:.2f} €, Norm {norm:.2f} €)."
        )
    user = (
        f"Datum: {date_str}\n"
        "Formuliere 1–3 prägnante Stichpunkte zu folgenden Auffälligkeiten "
        "(kein Smalltalk, kein Disclaimer):\n"
        + "\n".join(bullet_points)
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=150,
    )
    return resp.choices[0].message.content.strip()
