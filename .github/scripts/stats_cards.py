#!/usr/bin/env python3
"""Draw the commits and most-active-repos cards for the profile README.

Run by .github/workflows/stats-cards.yml. Pulls commit counts from the GitHub
GraphQL API and writes a light and a dark SVG of each card into an output
folder. Standard library only.

    GH_TOKEN=... python3 stats_cards.py <username> <out_dir>

With the workflow's built-in token, commits in private repos are not counted.
"""

import html
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com/graphql"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
W, H = 840, 196
WEEKS = 52
TOP_REPOS = 5

# Colors follow GitHub's own palette so the card sits naturally on the page.
# banner.py imports these too.
THEMES = {
    "dark": {
        "bg": "#0d1117", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e",
        "accent": "#3fb950",
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
    "light": {
        "bg": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#59636e",
        "accent": "#1a7f37",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    },
}

YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      commitContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner } }
    }
  }
}
"""


def gql(token, query, **variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats-cards"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


TOP_REPOS_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 10) {
        repository { name nameWithOwner primaryLanguage { name color } }
        contributions(first: 1, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          totalCount
          nodes { occurredAt }
        }
      }
    }
  }
}
"""


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(login, token):
    now = datetime.now(timezone.utc)
    info = gql(token, """query($login: String!) { user(login: $login) {
        createdAt contributionsCollection { contributionYears } } }""", login=login)["user"]

    # All-time totals: the API caps each query at one year, so add up year by year.
    commits, prs, repos = 0, 0, set()
    for year in info["contributionsCollection"]["contributionYears"]:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc), now)
        c = gql(token, YEAR_QUERY, login=login, **{"from": iso(start), "to": iso(end)})
        c = c["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"]
        prs += c["totalPullRequestContributions"]
        repos.update(r["repository"]["nameWithOwner"] for r in c["commitContributionsByRepository"])

    # Commits per week (Monday to Sunday, UTC) for the last year, in one query using aliases.
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    starts = [this_monday - timedelta(weeks=WEEKS - 1 - i) for i in range(WEEKS)]
    parts = [f'w{i}: contributionsCollection(from: "{iso(s)}", '
             f'to: "{iso(min(s + timedelta(weeks=1, seconds=-1), now))}") {{ totalCommitContributions }}'
             for i, s in enumerate(starts)]
    res = gql(token, "query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }",
              login=login)["user"]
    weekly = [(s.date(), res[f"w{i}"]["totalCommitContributions"]) for i, s in enumerate(starts)]

    # Repos with the most commits over the last 12 months, and the latest day with a commit in each.
    rows = gql(token, TOP_REPOS_QUERY, login=login)["user"]["contributionsCollection"]["commitContributionsByRepository"]
    rows = [r for r in rows if r["repository"]["nameWithOwner"].lower() != f"{login}/{login}".lower()]  # skip this profile repo
    top = sorted(rows, key=lambda r: -r["contributions"]["totalCount"])[:TOP_REPOS]
    top = [{"name": r["repository"]["name"],
            "lang": r["repository"]["primaryLanguage"],
            "commits": r["contributions"]["totalCount"],
            "last": datetime.fromisoformat(r["contributions"]["nodes"][0]["occurredAt"].replace("Z", "+00:00")).date()}
           for r in top if r["contributions"]["nodes"]]

    created = datetime.fromisoformat(info["createdAt"].replace("Z", "+00:00")).date()
    return {"commits": commits, "prs": prs, "repos": len(repos), "weekly": weekly, "created": created,
            "top": top, "today": now.date()}


def plural(n, word):
    return word if n == 1 else f"{word}s"


def label_text(t, x, y, text, anchor="start"):
    return (f'<text x="{x}" y="{y}" fill="{t["muted"]}" font-size="11" font-weight="600" '
            f'letter-spacing="1.2" text-anchor="{anchor}">{text}</text>')


def commits_card(t, data):
    weekly = data["weekly"]
    out = [
        label_text(t, 28, 40, "COMMITS"),
        f'<text x="28" y="98" fill="{t["accent"]}" font-size="56" font-weight="700" letter-spacing="-1.5">{data["commits"]:,}</text>',
        f'<text x="28" y="122" fill="{t["muted"]}" font-size="12.5">since {data["created"]:%b %Y}</text>',
        f'<text x="28" y="172" font-size="12.5"><tspan fill="{t["text"]}" font-weight="600">{data["repos"]}</tspan>'
        f'<tspan fill="{t["muted"]}"> {plural(data["repos"], "repo")}  ·  </tspan>'
        f'<tspan fill="{t["text"]}" font-weight="600">{data["prs"]}</tspan>'
        f'<tspan fill="{t["muted"]}"> {plural(data["prs"], "pull request")}</tspan></text>',
    ]

    # One bar per week for the last year, this week on the right.
    x0, x1, base, top = 280, 812, 148, 44
    step = (x1 - x0) / len(weekly)
    bar_w = step * 0.62
    peak = max((v for _, v in weekly), default=0)
    peak_i = max(range(len(weekly)), key=lambda i: weekly[i][1]) if peak else None
    for i, (_, v) in enumerate(weekly):
        x = x0 + step * i + (step - bar_w) / 2
        if v > 0:
            h = max(3, (base - top) * v / peak)
            out.append(f'<rect class="rise" style="animation-delay:{i * 14}ms" x="{x:.1f}" y="{base - h:.1f}" '
                       f'width="{bar_w:.1f}" height="{h:.1f}" rx="1.5" fill="{t["accent"]}"/>')
        else:
            out.append(f'<rect x="{x:.1f}" y="{base - 2}" width="{bar_w:.1f}" height="2" rx="1" '
                       f'fill="{t["levels"][0]}"/>')
        if i == peak_i:
            out.append(f'<text class="fade" style="animation-delay:700ms" x="{x + bar_w / 2:.1f}" '
                       f'y="{base - h - 6:.1f}" fill="{t["muted"]}" font-size="10" text-anchor="middle">{v}</text>')

    left, right = x0 + (step - bar_w) / 2, x1 - (step - bar_w) / 2
    out.append(f'<text x="{left:.1f}" y="172" fill="{t["muted"]}" font-size="11">{weekly[0][0]:%b %Y}</text>')
    out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="172" fill="{t["muted"]}" font-size="11" '
               f'text-anchor="middle">commits per week</text>')
    out.append(f'<text x="{right:.1f}" y="172" fill="{t["muted"]}" font-size="11" text-anchor="end">this week</text>')

    return frame(t, H, f"{data['commits']} commits since {data['created']:%B %Y}", out)


def frame(t, height, label, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img" aria-label="{label}" font-family="{SANS}">
<title>{label}</title>
<style>
  @keyframes rise {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  .rise {{ transform-box: fill-box; transform-origin: bottom; animation: rise .8s cubic-bezier(.2,.8,.2,1) both; }}
  .grow {{ transform-box: fill-box; transform-origin: left; animation: grow .9s cubic-bezier(.2,.8,.2,1) both; }}
  .fade {{ animation: fade .5s ease-out both; }}
  @media (prefers-reduced-motion: reduce) {{ .rise, .grow, .fade {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="10" fill="{t['bg']}" stroke="{t['border']}"/>
{chr(10).join(body)}
</svg>
"""


def fmt_day(d, today):
    return f"{d:%b} {d.day}" if d.year == today.year else f"{d:%b} {d.day}, {d.year}"


def repos_card(t, data):
    top, today = data["top"], data["today"]
    row_h, first = 32, 82
    height = first + row_h * (len(top) - 1) + 30
    out = [
        label_text(t, 28, 40, "MOST ACTIVE REPOS"),
        f'<text x="194" y="40" fill="{t["muted"]}" font-size="11">last 12 months</text>',
        label_text(t, 812, 40, "LAST COMMIT", anchor="end"),
    ]
    peak = max((r["commits"] for r in top), default=1)
    bar_x, bar_max = 390, 300
    for i, r in enumerate(top):
        y = first + i * row_h
        out.append(f'<text x="28" y="{y}" fill="{t["text"]}" font-size="14" font-weight="600">{html.escape(r["name"])}</text>')
        if r["lang"]:
            out.append(f'<circle cx="244" cy="{y - 4.5}" r="5" fill="{r["lang"]["color"] or t["muted"]}"/>')
            out.append(f'<text x="256" y="{y}" fill="{t["muted"]}" font-size="12.5">{html.escape(r["lang"]["name"])}</text>')
        w = max(4, bar_max * r["commits"] / peak)
        out.append(f'<rect x="{bar_x}" y="{y - 10}" width="{bar_max}" height="8" rx="4" fill="{t["levels"][0]}"/>')
        out.append(f'<rect class="grow" style="animation-delay:{i * 90}ms" x="{bar_x}" y="{y - 10}" '
                   f'width="{w:.1f}" height="8" rx="4" fill="{t["accent"]}"/>')
        out.append(f'<text x="{bar_x + bar_max + 14}" y="{y}" fill="{t["text"]}" font-size="12.5" font-weight="600">'
                   f'{r["commits"]:,}</text>')
        out.append(f'<text x="812" y="{y}" fill="{t["muted"]}" font-size="12.5" text-anchor="end">'
                   f'{fmt_day(r["last"], today)}</text>')
    names = ", ".join(f'{r["name"]} {r["commits"]}' for r in top)
    return frame(t, height, f"Most active repos in the last 12 months: {names}", out)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: stats_cards.py <username> <out_dir>")
    login, out_dir = sys.argv[1], Path(sys.argv[2])
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("set GH_TOKEN to a GitHub token")
    data = fetch(login, token)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, t in THEMES.items():
        (out_dir / f"commits-{name}.svg").write_text(commits_card(t, data))
        (out_dir / f"repos-{name}.svg").write_text(repos_card(t, data))
    print(f"wrote cards to {out_dir}: {data['commits']} commits, top repo {data['top'][0]['name'] if data['top'] else 'none'}")


if __name__ == "__main__":
    main()
