#!/usr/bin/env python3
"""Draw the streak and commit cards for the profile README.

Run by .github/workflows/stats-cards.yml. Pulls contribution data from the
GitHub GraphQL API and writes four SVGs (a light and a dark version of each
card) into an output folder. Standard library only.

    GH_TOKEN=... python3 stats_cards.py <username> <out_dir>

With the workflow's built-in token, commits in private repos are not counted on
the commit card. The streak card reads the contribution calendar, which also
counts private activity if "Include private contributions" is on in profile
settings.
"""

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com/graphql"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
W, H = 420, 196
STRIP_DAYS = 31

# Colors follow GitHub's own palette so the cards sit naturally on the page.
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
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(login, token):
    now = datetime.now(timezone.utc)
    info = gql(token, """query($login: String!) { user(login: $login) {
        createdAt contributionsCollection { contributionYears } } }""", login=login)["user"]

    days, commits, prs, repos = {}, 0, 0, set()
    for year in info["contributionsCollection"]["contributionYears"]:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc), now)
        c = gql(token, YEAR_QUERY, login=login, **{"from": iso(start), "to": iso(end)})
        c = c["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"]
        prs += c["totalPullRequestContributions"]
        repos.update(r["repository"]["nameWithOwner"] for r in c["commitContributionsByRepository"])
        for week in c["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                day = date.fromisoformat(d["date"])
                if start.date() <= day <= end.date():  # skip padding days from other years
                    days[day] = d["contributionCount"]

    # Commits per month for the last 12 months, in one query using aliases.
    months, y, m = [], now.year, now.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    months.reverse()
    parts = []
    for i, (y, m) in enumerate(months):
        start = datetime(y, m, 1, tzinfo=timezone.utc)
        nxt = datetime(y + 1, 1, 1, tzinfo=timezone.utc) if m == 12 else datetime(y, m + 1, 1, tzinfo=timezone.utc)
        end = min(nxt - timedelta(seconds=1), now)
        parts.append(f'm{i}: contributionsCollection(from: "{iso(start)}", to: "{iso(end)}") '
                     "{ totalCommitContributions }")
    res = gql(token, "query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }",
              login=login)["user"]
    monthly = [(date(y, m, 1), res[f"m{i}"]["totalCommitContributions"]) for i, (y, m) in enumerate(months)]

    created = datetime.fromisoformat(info["createdAt"].replace("Z", "+00:00")).date()
    return {"days": days, "commits": commits, "prs": prs, "repos": len(repos),
            "monthly": monthly, "created": created}


def streaks(days):
    """Return (current, longest), each as (length, first_day, last_day)."""
    first, today = min(days), max(days)
    longest, run, run_start, d = (0, None, None), 0, None, first
    while d <= today:
        if days.get(d, 0) > 0:
            run_start = d if run == 0 else run_start
            run += 1
            if run > longest[0]:
                longest = (run, run_start, d)
        else:
            run = 0
        d += timedelta(days=1)

    # Today still counts as "in progress", so a streak ending yesterday is alive.
    end = today if days.get(today, 0) > 0 else today - timedelta(days=1)
    start = end
    while days.get(start, 0) > 0:
        start -= timedelta(days=1)
    length = (end - start).days
    return (length, start + timedelta(days=1), end), longest


# ---------- drawing ----------

def plural(n, word):
    return f"{word}" if n == 1 else f"{word}s"


def fmt_day(d, today):
    s = f"{d:%b} {d.day}"
    return s if d.year == today.year else f"{s}, {d.year}"


def fmt_range(a, b, today):
    if a is None:
        return ""
    return fmt_day(a, today) if a == b else f"{fmt_day(a, today)} – {fmt_day(b, today)}"


def frame(t, label, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}" font-family="{SANS}">
<title>{label}</title>
<style>
  @keyframes rise {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  .rise {{ transform-box: fill-box; transform-origin: bottom; animation: rise .8s cubic-bezier(.2,.8,.2,1) both; }}
  .fade {{ animation: fade .5s ease-out both; }}
  @media (prefers-reduced-motion: reduce) {{ .rise, .fade {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="{t['bg']}" stroke="{t['border']}"/>
{body}
</svg>
"""


def label_text(t, x, y, text, anchor="start"):
    return (f'<text x="{x}" y="{y}" fill="{t["muted"]}" font-size="11" font-weight="600" '
            f'letter-spacing="1.2" text-anchor="{anchor}">{text}</text>')


def level(count, peak):
    if count <= 0 or peak <= 0:
        return 0
    return min(4, max(1, -(-4 * count // peak)))  # ceiling of 4 * count / peak


def streak_card(t, data):
    days = data["days"]
    today = max(days)
    (cur, cur_a, cur_b), (lon, lon_a, lon_b) = streaks(days)
    total = sum(days.values())

    cur_range = fmt_range(cur_a, cur_b, today) if cur else "Commit today to start one"
    out = [
        label_text(t, 24, 40, "CURRENT STREAK"),
        f'<text x="24" y="98" fill="{t["accent"]}" font-size="56" font-weight="700" letter-spacing="-1.5">{cur}'
        f'<tspan dx="8" font-size="16" font-weight="500" letter-spacing="0" fill="{t["muted"]}">{plural(cur, "day")}</tspan></text>',
        f'<text x="24" y="122" fill="{t["muted"]}" font-size="12.5">{cur_range}</text>',
        f'<line x1="246" y1="28" x2="246" y2="128" stroke="{t["border"]}"/>',
        label_text(t, 268, 40, "LONGEST"),
        f'<text x="268" y="63" fill="{t["text"]}" font-size="18" font-weight="600">{lon} {plural(lon, "day")}</text>',
        f'<text x="268" y="80" fill="{t["muted"]}" font-size="11.5">{fmt_range(lon_a, lon_b, today)}</text>',
        label_text(t, 268, 106, "CONTRIBUTIONS"),
        f'<text x="268" y="129" fill="{t["text"]}" font-size="18" font-weight="600">{total:,}'
        f'<tspan dx="6" font-size="11.5" font-weight="400" fill="{t["muted"]}">since {data["created"]:%b %Y}</tspan></text>',
    ]

    # The last month as a strip of squares, like a slice of the contribution graph.
    window = [today - timedelta(days=STRIP_DAYS - 1 - i) for i in range(STRIP_DAYS)]
    peak = max((days.get(d, 0) for d in window), default=0)
    size, gap, y = 9, 3, 150
    for i, d in enumerate(window):
        color = t["levels"][level(days.get(d, 0), peak)]
        out.append(f'<rect class="fade" style="animation-delay:{i * 18}ms" x="{24 + i * (size + gap)}" y="{y}" '
                   f'width="{size}" height="{size}" rx="2" fill="{color}"/>')
    out.append(f'<text x="24" y="178" fill="{t["muted"]}" font-size="11">Last {STRIP_DAYS} days</text>')
    out.append(f'<text x="{24 + STRIP_DAYS * (size + gap) - gap}" y="178" fill="{t["muted"]}" font-size="11" '
               f'text-anchor="end">today</text>')
    return frame(t, f"Current streak {cur} days, longest {lon} days, {total} contributions", "\n".join(out))


def commits_card(t, data):
    monthly = data["monthly"]
    out = [
        label_text(t, 24, 40, "COMMITS"),
        f'<text x="24" y="98" fill="{t["accent"]}" font-size="56" font-weight="700" letter-spacing="-1.5">{data["commits"]:,}</text>',
        f'<text x="24" y="122" fill="{t["muted"]}" font-size="12.5">since {data["created"]:%b %Y}</text>',
        f'<text x="24" y="178" font-size="12.5"><tspan fill="{t["text"]}" font-weight="600">{data["repos"]}</tspan>'
        f'<tspan fill="{t["muted"]}"> {plural(data["repos"], "repo")}  ·  </tspan>'
        f'<tspan fill="{t["text"]}" font-weight="600">{data["prs"]}</tspan>'
        f'<tspan fill="{t["muted"]}"> {plural(data["prs"], "pull request")}</tspan></text>',
    ]

    # Bar chart of commits per month, last 12 months, current month on the right.
    x0, x1, base, top = 212, 396, 154, 44
    step = (x1 - x0) / len(monthly)
    bar_w = step * 0.66
    peak = max((v for _, v in monthly), default=0)
    peak_i = max(range(len(monthly)), key=lambda i: monthly[i][1]) if peak else None
    for i, (month, v) in enumerate(monthly):
        cx = x0 + step * i + step / 2
        if v > 0:
            h = max(3, (base - top) * v / peak)
            out.append(f'<rect class="rise" style="animation-delay:{i * 45}ms" x="{cx - bar_w / 2:.1f}" '
                       f'y="{base - h:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2" fill="{t["accent"]}"/>')
        else:
            out.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{base - 2}" width="{bar_w:.1f}" height="2" '
                       f'rx="1" fill="{t["levels"][0]}"/>')
        if i == peak_i:
            out.append(f'<text class="fade" style="animation-delay:600ms" x="{cx:.1f}" y="{base - h - 6:.1f}" '
                       f'fill="{t["muted"]}" font-size="10" text-anchor="middle">{v}</text>')
        is_now = i == len(monthly) - 1  # highlight the current month's initial
        fill, weight = (t["text"], 600) if is_now else (t["muted"], 400)
        initial = month.strftime("%b")[0]
        out.append(f'<text x="{cx:.1f}" y="178" fill="{fill}" font-size="10" font-weight="{weight}" '
                   f'text-anchor="middle">{initial}</text>')
    return frame(t, f"{data['commits']} commits since {data['created']:%B %Y}", "\n".join(out))


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
        (out_dir / f"streak-{name}.svg").write_text(streak_card(t, data))
        (out_dir / f"commits-{name}.svg").write_text(commits_card(t, data))
    cur = streaks(data["days"])[0][0]
    print(f"wrote cards to {out_dir}: streak {cur} days, {data['commits']} commits")


if __name__ == "__main__":
    main()
