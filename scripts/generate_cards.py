#!/usr/bin/env python3
"""Genera las cards SVG del perfil (stats, racha, actividad, lenguajes y pins de
repos). Corre local o en el Action diario (cards.yml).

Sin dependencias: solo stdlib. Requiere GITHUB_TOKEN en el entorno (repos,
estrellas y lenguajes salen de GraphQL).

Las contribuciones salen del calendario público del perfil
(github.com/users/<login>/contributions), que es exactamente lo que ve cualquier
visitante bajo el README: el GITHUB_TOKEN del Action no ve las contribuciones
privadas y se queda corto. Si ese HTML cambia de formato, el script avisa por
stderr y cae al contributionCalendar de GraphQL para que el Action no se rompa.

Las fechas son UTC, igual que el calendario que GitHub sirve a un visitante
anónimo."""

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from xml.sax.saxutils import escape

LOGIN = "AleBrito124356"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
CALENDAR_URL = f"https://github.com/users/{LOGIN}/contributions"
USER_AGENT = f"{LOGIN}-profile-cards (+https://github.com/{LOGIN}/{LOGIN})"
# Tope para bajar los calendarios de años anteriores (el job tiene 5 min; peor
# caso con todo agotando timeouts ≈ 4 min, una corrida normal tarda ~10 s).
HISTORY_BUDGET_S = 60
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
# Naranja Claude: único acento naranja del dashboard (anillo y llama de la racha).
ORANGE = "#D97757"
MAX_LANGS = 6
# El azul de linguist para TypeScript (#3178c6) es casi el de Python (#3572A5).
LANG_COLOR_OVERRIDES = {"TypeScript": "#38BDF8"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        description
        stargazerCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


# --------------------------------------------------------------------------- red


def http_get(url, data=None, headers=None, attempts=2, timeout=20):
    """GET/POST con reintento corto ante 429/5xx o cortes de red."""
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                raise
        except OSError:  # URLError, timeout, conexión reseteada
            if attempt == attempts:
                raise
        time.sleep(2 * attempt)


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN no definido")
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    raw = http_get(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        attempts=3,
        timeout=30,
    )
    data = json.loads(raw)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def count_pages_sites():
    """Repos públicos con sitio en GitHub Pages (demos en vivo); None si la API falla."""
    token = os.environ.get("GITHUB_TOKEN")
    try:
        raw = http_get(
            f"https://api.github.com/users/{LOGIN}/repos?per_page=100&type=owner",
            headers={"Authorization": f"bearer {token}", "Accept": "application/vnd.github+json"},
        )
        return sum(1 for r in json.loads(raw) if r.get("has_pages"))
    except (OSError, ValueError) as exc:
        warn(f"no se pudo contar los sitios de GitHub Pages: {exc}")
        return None


def warn(msg):
    msg = " ".join(str(msg).split())
    print(f"WARNING: {msg}", file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=generate_cards::{msg}")


# ------------------------------------------------------- calendario público


class _CalendarParser(HTMLParser):
    """Recoge las celdas <td data-date id> del calendario, los <tool-tip for=id>
    con el texto "N contributions on …" y el encabezado con el total."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = {}  # id de la celda -> "YYYY-MM-DD"
        self.tips = {}  # id de la celda -> texto del tooltip
        self.heading = []
        self._tip_for = None
        self._tip_buf = []
        self._in_heading = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and a.get("data-date") and a.get("id"):
            self.cells[a["id"]] = a["data-date"]
        elif tag == "tool-tip" and a.get("for"):
            self._tip_for, self._tip_buf = a["for"], []
        elif tag == "h2" and a.get("id") == "js-contribution-activity-description":
            self._in_heading = True

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self._tip_for is not None:
            self.tips[self._tip_for] = " ".join("".join(self._tip_buf).split())
            self._tip_for = None
        elif tag == "h2":
            self._in_heading = False

    def handle_data(self, data):
        if self._tip_for is not None:
            self._tip_buf.append(data)
        if self._in_heading:
            self.heading.append(data)


_TIP = re.compile(r"^(No|[\d,]+) contributions? on\b", re.IGNORECASE)
_HEADING = re.compile(r"([\d,]+)\s+contributions?\b", re.IGNORECASE)


def parse_calendar(html):
    """{date: contribuciones}. Lanza ValueError si el formato no es el esperado,
    para que quien llama caiga al plan B en vez de publicar cifras falsas."""
    p = _CalendarParser()
    p.feed(html)
    p.close()
    if not p.cells:
        raise ValueError("el HTML no trae días (¿cambió el formato?)")
    days = {}
    for cell_id, iso in p.cells.items():
        text = p.tips.get(cell_id)
        m = _TIP.match(text or "")
        if not m:
            raise ValueError(f"tooltip inesperado para {iso}: {text!r}")
        n = m.group(1)
        days[date.fromisoformat(iso)] = 0 if n.lower() == "no" else int(n.replace(",", ""))
    heading = _HEADING.search(" ".join(p.heading))
    if heading and int(heading.group(1).replace(",", "")) != sum(days.values()):
        raise ValueError(
            f"la suma de los días ({sum(days.values())}) no cuadra con el encabezado ({heading.group(1)})"
        )
    return days


def public_calendar(start=None, end=None):
    url = CALENDAR_URL if start is None else f"{CALENDAR_URL}?from={start}&to={end}"
    raw = http_get(url, headers={"Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
    return parse_calendar(raw.decode("utf-8"))


def graphql_calendar(user):
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {
        date.fromisoformat(d["date"]): d["contributionCount"]
        for w in weeks
        for d in w["contributionDays"]
    }


def contributions(user):
    """(último_año, historial, fuente). 'último_año' es la ventana que enseña el
    perfil; 'historial' le suma los años anteriores para la racha más larga."""
    try:
        last_year = public_calendar()
    except Exception as exc:  # cualquier fallo del scraping cae a GraphQL
        warn(
            f"no pude leer el calendario público ({exc}); uso el contributionCalendar "
            "de GraphQL, que con el GITHUB_TOKEN del Action puede quedarse corto"
        )
        last_year = graphql_calendar(user)
        return last_year, dict(last_year), "GraphQL (plan B)"
    history = dict(last_year)
    first = min(last_year)
    created = int(user["createdAt"][:4])
    t0 = time.monotonic()
    for year in range(first.year, created - 1, -1):  # del más reciente al más viejo
        if time.monotonic() - t0 > HISTORY_BUDGET_S:
            warn(f"sin tiempo para {year} y anteriores; la racha más larga puede quedarse corta")
            break
        try:
            days = public_calendar(f"{year}-01-01", f"{year}-12-31")
        except Exception as exc:
            warn(f"no pude leer el calendario de {year} ({exc}); la racha más larga puede quedarse corta")
            continue
        for d, n in days.items():
            if d < first:  # lo que cae en la ventana manda el calendario del último año
                history[d] = n
    return last_year, history, "calendario público"


def summarize(last_year, history, today):
    active = sorted(d for d, n in history.items() if n > 0 and d <= today)
    one = timedelta(days=1)

    longest = (0, None, None)  # en empate gana la más reciente
    start = prev = None
    for d in active:
        if prev is None or d - prev != one:
            start = d
        if (d - start).days + 1 >= longest[0]:
            longest = ((d - start).days + 1, start, d)
        prev = d

    # Si hoy aún no hay contribuciones pero ayer sí, la racha sigue viva.
    active_set = set(active)
    end = today if today in active_set else today - one
    d = end
    while d in active_set:
        d -= one
    length = (end - d).days
    current = (length, d + one, end) if length else (0, None, None)

    window = [today - timedelta(days=i) for i in range(29, -1, -1)]
    return {
        "today": today,
        "total": sum(last_year.values()),
        "active_days": sum(1 for n in last_year.values() if n > 0),
        "current": current,
        "longest": longest,
        "last30": [(d, history.get(d, 0)) for d in window],
    }


# ------------------------------------------------------------------ helpers


def card_shell(width, height, inner, label):
    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(label)}">
  <rect width="{width}" height="{height}" rx="14" fill="{BG}"/>
{inner}
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="13.5" stroke="{BORDER}"/>
</svg>
"""


def card_title(text):
    return f'  <text x="25" y="36" font-family="{SANS}" font-size="17" font-weight="700" fill="{TITLE}">{escape(text)}</text>'


def card_footer(updated):
    return f'  <text x="470" y="188" text-anchor="end" font-family="{MONO}" font-size="10" fill="{FAINT}">actualizado {updated}</text>'


def fmt(n):
    return f"{n:,}".replace(",", " ")


def short_date(d, today):
    s = f"{d.day} {MESES[d.month - 1]}"
    return s if d.year == today.year else f"{s} {d.year}"


def date_range(a, b, today):
    if a == b:
        return short_date(a, today)
    return f"{short_date(a, today)} – {short_date(b, today)}"


def plural(n, one, many):
    return one if n == 1 else many


# ------------------------------------------------------------------- cards


def stats_card(user, c, updated, pages_sites):
    total = c["total"]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    # "Días activos" ya está en la card de racha: aquí solo como plan B si falla la API.
    third = (("Sitios en vivo (GitHub Pages)", pages_sites) if pages_sites is not None
             else ("Días activos — último año", c["active_days"]))
    rows = [
        ("Estrellas totales", stars),
        ("Contribuciones — último año", total),
        third,
        ("Repos públicos", user["repositories"]["totalCount"]),
        ("Repos open source (IA + diseño)", 57),
        ("Productos en producción", 2),
    ]
    ring_pct = min(1.0, total / 500)
    circ = 2 * 3.14159 * 48
    dash = circ * ring_pct
    ring_label = fmt(total)
    ring_size = 26 if len(ring_label) <= 5 else 21
    parts = [card_title("Estadísticas de GitHub")]
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
  <text x="407" y="103" text-anchor="middle" font-family="{SANS}" font-size="{ring_size}" font-weight="700" fill="{BRIGHT}">{ring_label}</text>
  <text x="407" y="122" text-anchor="middle" font-family="{SANS}" font-size="10" fill="{MUTED}">contribuciones</text>
{card_footer(updated)}''')
    return card_shell(495, 200, "\n".join(parts), "Estadísticas de GitHub de Alejandro Brito")


# Llama centrada en (0, 0), ~14 × 21 px (se dibuja a 1.2×). El recorte interior va en color fondo.
FLAME_OUTER = (
    "M0.6,-10.5 C1.6,-6.8 7,-4.6 7,1.8 C7,6.6 3.9,10 0,10 C-3.9,10 -7,6.8 -7,2.4 "
    "C-7,-0.9 -5.3,-3.4 -3.4,-5.2 C-3.4,-2.6 -2.3,-1 -0.7,-0.6 C-1.5,-4.4 -0.8,-7.8 0.6,-10.5 Z"
)
FLAME_INNER = (
    "M0.3,0.8 C1.4,2.4 2.9,3.6 2.9,5.2 C2.9,6.6 1.6,7.6 0,7.6 C-1.6,7.6 -2.9,6.6 -2.9,5.2 "
    "C-2.9,4 -2.1,3.1 -1.3,2.3 C-1.1,3.2 -0.6,3.7 0,3.8 C-0.4,2.9 -0.3,1.8 0.3,0.8 Z"
)


def streak_card(c, updated):
    today = c["today"]
    cur_len, cur_a, cur_b = c["current"]
    best_len, best_a, best_b = c["longest"]
    cx, cy, r = 247.5, 100, 34
    circ = 2 * math.pi * r
    flame_y = cy - r
    cur_label = fmt(cur_len)
    cur_size = 28 if len(cur_label) <= 3 else 22
    sides = [
        (100, c["active_days"], "Días activos", "último año"),
        (395, best_len, "Racha más larga", date_range(best_a, best_b, today) if best_len else "sin actividad"),
    ]
    parts = [card_title("Racha de contribuciones")]
    for x in (174, 321):
        parts.append(f'  <line x1="{x}" y1="72" x2="{x}" y2="160" stroke="{BORDER}"/>')
    for i, (x, value, label, sub) in enumerate(sides):
        parts.append(f'''  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{0.2 + 0.25 * i:.2f}s" fill="freeze"/>
    <text x="{x}" y="106" text-anchor="middle" font-family="{SANS}" font-size="28" font-weight="700" fill="{BRIGHT}">{fmt(value)}</text>
    <text x="{x}" y="132" text-anchor="middle" font-family="{SANS}" font-size="13" fill="{TEXT}">{escape(label)}</text>
    <text x="{x}" y="150" text-anchor="middle" font-family="{SANS}" font-size="11" fill="{MUTED}">{escape(sub)}</text>
  </g>''')
    cur_sub = date_range(cur_a, cur_b, today) if cur_len else "sin actividad reciente"
    parts.append(f'''  <g transform="rotate(-90 {cx} {cy})">
    <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{BORDER}" stroke-width="7"/>
    <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{ORANGE}" stroke-width="7" stroke-linecap="round"
            stroke-dasharray="{circ:.1f} {circ:.1f}" stroke-dashoffset="{circ:.1f}">
      <animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="0" dur="1.2s" fill="freeze"/>
    </circle>
  </g>
  <circle cx="{cx}" cy="{flame_y}" r="14" fill="{BG}"/>
  <g transform="translate({cx} {flame_y}) scale(1.2)">
    <g transform="scale(0)">
      <animateTransform attributeName="transform" type="scale" values="0;1.15;1" keyTimes="0;0.7;1" begin="1s" dur="0.45s" fill="freeze"/>
      <path d="{FLAME_OUTER}" fill="{ORANGE}"/>
      <path d="{FLAME_INNER}" fill="{BG}"/>
    </g>
  </g>
  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="0.35s" fill="freeze"/>
    <text x="{cx}" y="{cy + 6}" text-anchor="middle" font-family="{SANS}" font-size="{cur_size}" font-weight="700" fill="{BRIGHT}">{cur_label}</text>
    <text x="{cx}" y="{cy + 21}" text-anchor="middle" font-family="{SANS}" font-size="10" fill="{MUTED}">{plural(cur_len, "día", "días")}</text>
    <text x="{cx}" y="158" text-anchor="middle" font-family="{SANS}" font-size="13" fill="{TEXT}">Racha actual</text>
    <text x="{cx}" y="174" text-anchor="middle" font-family="{SANS}" font-size="11" fill="{MUTED}">{escape(cur_sub)}</text>
  </g>
{card_footer(updated)}''')
    return card_shell(495, 200, "\n".join(parts), "Racha de contribuciones de Alejandro Brito")


def _bezier_length(p0, p1, p2, p3, steps=24):
    length, prev = 0.0, p0
    for k in range(1, steps + 1):
        t = k / steps
        u = 1 - t
        pt = tuple(
            u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c_ + t * t * t * d
            for a, b, c_, d in zip(p0, p1, p2, p3)
        )
        length += math.hypot(pt[0] - prev[0], pt[1] - prev[1])
        prev = pt
    return length


def smooth_path(pts, y_min, y_max):
    """Catmull-Rom → Bézier cúbica. Los puntos de control se acotan a
    [y_min, y_max]: una Bézier nunca sale de la envolvente convexa de sus puntos
    de control, así que la curva no baja de 0 ni se sale del gráfico.
    Devuelve el atributo d y la longitud acumulada hasta cada punto."""

    def clamp(y):
        return min(max(y, y_min), y_max)

    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    cum = [0.0]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, clamp(p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, clamp(p2[1] - (p3[1] - p1[1]) / 6))
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
        cum.append(cum[-1] + _bezier_length(p1, c1, c2, p2))
    return " ".join(d), cum


def activity_card(c, updated):
    today = c["today"]
    series = c["last30"]
    counts = [n for _, n in series]
    total = sum(counts)
    vmax = max(counts)
    x0, x1, y_top, y_base = 50.0, 470.0, 62.0, 150.0
    step = (x1 - x0) / (len(series) - 1)
    scale = (y_base - y_top) / (vmax or 1)
    pts = [(x0 + i * step, y_base - n * scale) for i, n in enumerate(counts)]
    line_d, cum = smooth_path(pts, y_top, y_base)
    dash = cum[-1] * 1.02 + 2  # con margen: si la raya es más larga que el trazo no pasa nada
    draw_s = 1.8
    area_d = f"{line_d} L{x1:.1f},{y_base:.1f} L{x0:.1f},{y_base:.1f} Z"
    mid = len(series) // 2

    parts = [
        card_title("Actividad — últimos 30 días"),
        f'  <text x="470" y="36" text-anchor="end" font-family="{SANS}" font-size="13" fill="{TEXT}">'
        f'<tspan font-family="{MONO}" font-weight="700" fill="{BRIGHT}">{fmt(total)}</tspan> '
        f'{plural(total, "contribución", "contribuciones")}</text>',
        f'''  <defs>
    <linearGradient id="activity-fill" x1="0" y1="{y_top}" x2="0" y2="{y_base}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#2563EB" stop-opacity="0.45"/>
      <stop offset="1" stop-color="#2563EB" stop-opacity="0"/>
    </linearGradient>
  </defs>''',
    ]
    if vmax:
        parts.append(f'''  <line x1="{x0:.0f}" y1="{y_top:.0f}" x2="{x1:.0f}" y2="{y_top:.0f}" stroke="{BORDER}" stroke-dasharray="3 4"/>
  <text x="42" y="{y_top + 3.5:.1f}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{MUTED}">{fmt(vmax)}</text>''')
    parts.append(f'''  <line x1="{x0:.0f}" y1="{y_base:.0f}" x2="{x1:.0f}" y2="{y_base:.0f}" stroke="{BORDER}"/>
  <text x="42" y="{y_base + 3.5:.1f}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{MUTED}">0</text>''')
    for i, anchor in ((0, "start"), (mid, "middle"), (len(series) - 1, "end")):
        x = pts[i][0]
        parts.append(f'''  <line x1="{x:.1f}" y1="{y_base:.0f}" x2="{x:.1f}" y2="{y_base + 4:.0f}" stroke="{BORDER}"/>
  <text x="{x:.1f}" y="168" text-anchor="{anchor}" font-family="{SANS}" font-size="11" fill="{MUTED}">{short_date(series[i][0], today)}</text>''')
    parts.append(f'''  <path d="{area_d}" fill="url(#activity-fill)" opacity="0">
    <animate attributeName="opacity" from="0" to="1" begin="0.5s" dur="1.2s" fill="freeze"/>
  </path>
  <path d="{line_d}" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        stroke-dasharray="{dash:.1f} {dash:.1f}" stroke-dashoffset="{dash:.1f}">
    <animate attributeName="stroke-dashoffset" from="{dash:.1f}" to="0" dur="{draw_s}s" fill="freeze"/>
  </path>''')
    for i, n in enumerate(counts):
        if not n:
            continue
        big = n == vmax
        begin = draw_s * cum[i] / dash  # aparece justo cuando la línea llega al punto
        parts.append(f'''  <circle cx="{pts[i][0]:.1f}" cy="{pts[i][1]:.1f}" r="{3.4 if big else 2.4}" fill="{"#60A5FA" if big else "#93C5FD"}" stroke="{BG}" stroke-width="1.2" opacity="0">
    <animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="0.25s" fill="freeze"/>
  </circle>''')
    parts.append(card_footer(updated))
    return card_shell(495, 200, "\n".join(parts), "Actividad de los últimos 30 días de Alejandro Brito")


def langs_card(user, updated):
    totals = {}
    colors = {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = LANG_COLOR_OVERRIDES.get(name) or edge["node"]["color"] or "#3B82F6"
    top = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_LANGS]
    per_col = (MAX_LANGS + 1) // 2
    total_size = sum(totals.values()) or 1
    parts = [card_title("Lenguajes más usados")]
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
        col = 25 if i < per_col else 260
        y = 100 + (i % per_col) * 26
        parts.append(f'''  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{0.12 * i:.2f}s" fill="freeze"/>
    <circle cx="{col + 5}" cy="{y - 5}" r="5" fill="{colors[name]}"/>
    <text x="{col + 20}" y="{y}" font-family="{SANS}" font-size="13.5" fill="#CBD5E1">{escape(name)}</text>
    <text x="{col + 175}" y="{y}" text-anchor="end" font-family="{MONO}" font-size="12.5" fill="{MUTED}">{pct:.1f}%</text>
  </g>''')
    parts.append(card_footer(updated))
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
    for stream in (sys.stdout, sys.stderr):  # consola cp1252 en Windows: nunca romper por un print
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    user = fetch()
    now = datetime.now(timezone.utc)
    updated = now.strftime("%Y-%m-%d")
    last_year, history, source = contributions(user)
    today = max(last_year) if last_year else now.date()
    c = summarize(last_year, history, today)
    cur, best = c["current"], c["longest"]
    print(
        f"contribuciones [{source}] hasta {today}: ultimo ano {c['total']} | "
        f"dias activos {c['active_days']} | racha actual {cur[0]} ({cur[1]} a {cur[2]}) | "
        f"racha mas larga {best[0]} ({best[1]} a {best[2]}) | "
        f"30 dias {sum(n for _, n in c['last30'])} ({c['last30'][0][0]} a {c['last30'][-1][0]})"
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    outputs = {
        "stats-card.svg": stats_card(user, c, updated, count_pages_sites()),
        "streak-card.svg": streak_card(c, updated),
        "activity-card.svg": activity_card(c, updated),
        "langs-card.svg": langs_card(user, updated),
    }
    by_name = {r["name"]: r for r in user["repositories"]["nodes"]}
    for name in FEATURED:
        if name in by_name:
            outputs[f"pin-{name}.svg"] = pin_card(by_name[name], updated)
        else:
            print(f"aviso: repo destacado no encontrado: {name}")
    for filename, svg in outputs.items():
        path = os.path.join(OUT_DIR, filename)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
        print(f"ok: {filename}")


if __name__ == "__main__":
    main()
