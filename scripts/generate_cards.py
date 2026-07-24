#!/usr/bin/env python3
"""Genera las cards SVG del perfil (stats, lenguajes y pins de repos) con datos
reales de la API de GitHub. Corre local o en el Action diario (cards.yml).

Sin dependencias: solo stdlib. Requiere GITHUB_TOKEN en el entorno."""

import json
import os
import sys
import urllib.request
from datetime import date, timezone, datetime
from xml.sax.saxutils import escape

LOGIN = "AleBrito124356"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
FEATURED = [
    "nim-agent-lab",
    "rag-blueprints",
    "langgraph-agent-flows",
    "mcp-server-cookbook",
    "llm-eval-toolkit",
    "recetas-ia",
]

BG = "#0A0D14"
BORDER = "#1E293B"
TITLE = "#60A5FA"
TEXT = "#94A3B8"
BRIGHT = "#F1F5F9"
MUTED = "#64748B"
FAINT = "#31415C"
SANS = "'Segoe UI', -apple-system, Ubuntu, Roboto, sans-serif"
MONO = "'Cascadia Code', Consolas, Menlo, monospace"
BLUES = ["#60A5FA", "#3B82F6", "#2563EB", "#38BDF8", "#93C5FD", "#1D4ED8"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        description
        stargazerCount
        updatedAt
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN no definido")
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def card_shell(width, height, inner, label):
    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(label)}">
  <rect width="{width}" height="{height}" rx="14" fill="{BG}"/>
{inner}
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="13.5" stroke="{BORDER}"/>
</svg>
"""


def fmt(n):
    return f"{n:,}".replace(",", " ")


def stats_card(user, today):
    c = user["contributionsCollection"]
    total = c["contributionCalendar"]["totalContributions"]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    rows = [
        ("Estrellas totales", stars),
        ("Contribuciones — último año", total),
        ("Commits — último año", c["totalCommitContributions"]),
        ("Repos públicos", user["repositories"]["totalCount"]),
        ("Repos de IA open source", 47),
        ("Productos en producción", 2),
    ]
    ring_pct = min(1.0, total / 500)
    circ = 2 * 3.14159 * 48
    dash = circ * ring_pct
    parts = [
        f'  <text x="25" y="36" font-family="{SANS}" font-size="17" font-weight="700" fill="{TITLE}">Estadísticas de GitHub</text>'
    ]
    y = 68
    for i, (label, value) in enumerate(rows):
        parts.append(f'''  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{0.15 * i:.2f}s" fill="freeze"/>
    <circle cx="31" cy="{y - 5}" r="4" fill="{BLUES[i % len(BLUES)]}"/>
    <text x="46" y="{y}" font-family="{SANS}" font-size="14" fill="{TEXT}">{escape(label)}</text>
    <text x="322" y="{y}" text-anchor="end" font-family="{MONO}" font-size="14" font-weight="700" fill="{BRIGHT}">{fmt(value)}</text>
  </g>''')
        y += 24
    parts.append(f'''  <g transform="rotate(-90 407 105)">
    <circle cx="407" cy="105" r="48" stroke="{BORDER}" stroke-width="9"/>
    <circle cx="407" cy="105" r="48" stroke="#3B82F6" stroke-width="9" stroke-linecap="round"
            stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-dashoffset="{dash:.1f}">
      <animate attributeName="stroke-dashoffset" from="{dash:.1f}" to="0" dur="1.4s" fill="freeze"/>
    </circle>
  </g>
  <text x="407" y="103" text-anchor="middle" font-family="{SANS}" font-size="26" font-weight="700" fill="{BRIGHT}">{fmt(total)}</text>
  <text x="407" y="122" text-anchor="middle" font-family="{SANS}" font-size="10" fill="{MUTED}">contribuciones</text>
  <text x="470" y="188" text-anchor="end" font-family="{MONO}" font-size="10" fill="{FAINT}">actualizado {today}</text>''')
    return card_shell(495, 200, "\n".join(parts), "Estadísticas de GitHub de Alejandro Brito")


def langs_card(user, today):
    totals = {}
    colors = {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#3B82F6"
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:8]
    total_size = sum(totals.values()) or 1
    parts = [
        f'  <text x="25" y="36" font-family="{SANS}" font-size="17" font-weight="700" fill="{TITLE}">Lenguajes más usados</text>'
    ]
    x = 25.0
    bar_w = 445.0
    parts.append(f'  <clipPath id="bar"><rect x="25" y="54" width="{bar_w}" height="10" rx="5"/></clipPath>')
    parts.append('  <g clip-path="url(#bar)">')
    for name, size in top:
        w = bar_w * size / total_size
        parts.append(f'    <rect x="{x:.1f}" y="54" width="{w + 1:.1f}" height="10" fill="{colors[name]}"/>')
        x += w
    parts.append(f'    <rect x="{x:.1f}" y="54" width="{bar_w:.1f}" height="10" fill="{BORDER}"/>')
    parts.append("  </g>")
    for i, (name, size) in enumerate(top):
        pct = 100.0 * size / total_size
        col = 25 if i < 4 else 260
        y = 96 + (i % 4) * 24
        parts.append(f'''  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{0.12 * i:.2f}s" fill="freeze"/>
    <circle cx="{col + 5}" cy="{y - 5}" r="5" fill="{colors[name]}"/>
    <text x="{col + 20}" y="{y}" font-family="{SANS}" font-size="13.5" fill="#CBD5E1">{escape(name)}</text>
    <text x="{col + 175}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="12.5" fill="{MUTED}">{pct:.1f}%</text>
  </g>''')
    parts.append(f'  <text x="470" y="188" text-anchor="end" font-family="{MONO}" font-size="10" fill="{FAINT}">actualizado {today}</text>')
    return card_shell(495, 200, "\n".join(parts), "Lenguajes más usados por Alejandro Brito")


def wrap(text, width=76, lines=2):
    words = (text or "").split()
    out, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 > width and line:
            out.append(line)
            line = w
            if len(out) == lines:
                break
        else:
            line = f"{line} {w}".strip()
    if len(out) < lines and line:
        out.append(line)
    if len(out) == lines and " ".join(out) != (text or "").strip():
        out[-1] = out[-1][: width - 2].rstrip() + "…"
    return out


def pin_card(repo, today):
    name = repo["name"]
    desc = wrap(repo["description"])
    lang = repo["primaryLanguage"] or {"name": "Markdown", "color": "#3B82F6"}
    parts = [
        f'  <text x="25" y="38" font-family="{SANS}" font-size="17" font-weight="700" fill="{TITLE}">{escape(name)}</text>',
        f'''  <g font-family="{SANS}">
    <text x="527" y="38" text-anchor="end" font-size="14" fill="#FBBF24">★</text>
    <text x="560" y="38" text-anchor="end" font-size="14" font-weight="700" fill="{TEXT}">{repo["stargazerCount"]}</text>
  </g>''',
    ]
    for i, line in enumerate(desc):
        parts.append(
            f'  <text x="25" y="{68 + i * 21}" font-family="{SANS}" font-size="13.5" fill="{TEXT}">{escape(line)}</text>'
        )
    parts.append(f'''  <circle cx="31" cy="121" r="5" fill="{lang["color"] or "#3B82F6"}"/>
  <text x="44" y="126" font-family="{SANS}" font-size="12.5" fill="{MUTED}">{escape(lang["name"])}</text>
  <text x="560" y="126" text-anchor="end" font-family="{MONO}" font-size="10" fill="{FAINT}">actualizado {today}</text>''')
    return card_shell(585, 150, "\n".join(parts), f"Repositorio {name}")


def main():
    user = fetch()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(OUT_DIR, exist_ok=True)
    outputs = {
        "stats-card.svg": stats_card(user, today),
        "langs-card.svg": langs_card(user, today),
    }
    by_name = {r["name"]: r for r in user["repositories"]["nodes"]}
    for name in FEATURED:
        if name in by_name:
            outputs[f"pin-{name}.svg"] = pin_card(by_name[name], today)
        else:
            print(f"aviso: repo destacado no encontrado: {name}")
    for filename, svg in outputs.items():
        path = os.path.join(OUT_DIR, filename)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"ok: {filename}")


if __name__ == "__main__":
    main()
