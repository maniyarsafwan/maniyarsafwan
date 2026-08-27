"""
generate_stats.py
------------------
Builds two self-hosted, brand-colored SVG cards (stats.svg and langs.svg) from the
GitHub REST/GraphQL API, so the README never depends on third-party stat-card
services that can be slow, rate-limited, or blocked on restrictive networks.

This is meant to be run inside a GitHub Actions workflow (see
.github/workflows/update-stats.yml) where a GITHUB_TOKEN with read access to the
account is available as an environment variable. It writes:
    assets/stats.svg   -> public repos, stars, followers, total commits (approx)
    assets/langs.svg   -> top languages across public repos, by byte count

Run locally for testing (optional):
    set GITHUB_TOKEN=ghp_xxx   (Windows PowerShell: $env:GITHUB_TOKEN="ghp_xxx")
    set GH_USERNAME=maniyarsafwan
    python scripts/generate_stats.py
"""

import os
import sys
import requests
from collections import defaultdict

USERNAME = os.environ.get("GH_USERNAME", "maniyarsafwan")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

API = "https://api.github.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

# Brand palette
NAVY = "#092634"
BLUE = "#004E72"
ORANGE = "#FF6E42"
WHITE = "#F9F9F9"


def get_json(url, params=None):
    resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_user():
    return get_json(f"{API}/users/{USERNAME}")


def fetch_repos():
    repos, page = [], 1
    while True:
        batch = get_json(
            f"{API}/users/{USERNAME}/repos",
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def fetch_languages(repos):
    totals = defaultdict(int)
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            langs = get_json(repo["languages_url"])
        except requests.RequestException:
            continue
        for lang, count in langs.items():
            totals[lang] += count
    return totals


def build_stats_svg(user, repos):
    public_repos = user.get("public_repos", len(repos))
    followers = user.get("followers", 0)
    stars = sum(r.get("stargazers_count", 0) for r in repos)

    rows = [
        ("Public Repos", public_repos),
        ("Total Stars", stars),
        ("Followers", followers),
    ]

    height = 60 + len(rows) * 42
    svg = [
        f'<svg width="420" height="{height}" viewBox="0 0 420 {height}" '
        'xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="420" height="{height}" rx="14" fill="{NAVY}"/>',
        f'<rect x="0" y="0" width="6" height="{height}" fill="{ORANGE}"/>',
        f'<text x="28" y="42" font-family="Segoe UI, sans-serif" font-size="19" '
        f'font-weight="700" fill="{WHITE}">GitHub Stats</text>',
    ]
    y = 78
    for label, value in rows:
        svg.append(
            f'<text x="28" y="{y}" font-family="Segoe UI, sans-serif" font-size="15" '
            f'fill="{WHITE}" opacity="0.85">{label}</text>'
        )
        svg.append(
            f'<text x="392" y="{y}" text-anchor="end" font-family="Consolas, monospace" '
            f'font-size="16" font-weight="700" fill="{ORANGE}">{value}</text>'
        )
        y += 42
    svg.append("</svg>")
    return "\n".join(svg)


def build_langs_svg(lang_totals, top_n=6):
    total = sum(lang_totals.values()) or 1
    top = sorted(lang_totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]

    height = 60 + len(top) * 34
    svg = [
        f'<svg width="420" height="{height}" viewBox="0 0 420 {height}" '
        'xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="420" height="{height}" rx="14" fill="{NAVY}"/>',
        f'<rect x="0" y="0" width="6" height="{height}" fill="{BLUE}"/>',
        f'<text x="28" y="42" font-family="Segoe UI, sans-serif" font-size="19" '
        f'font-weight="700" fill="{WHITE}">Top Languages</text>',
    ]
    y = 74
    bar_x, bar_w_max = 150, 220
    for lang, count in top:
        pct = count / total
        bar_w = max(6, int(bar_w_max * pct))
        svg.append(
            f'<text x="28" y="{y}" font-family="Segoe UI, sans-serif" font-size="14" '
            f'fill="{WHITE}">{lang}</text>'
        )
        svg.append(
            f'<rect x="{bar_x}" y="{y - 12}" width="{bar_w_max}" height="10" rx="5" '
            f'fill="{WHITE}" opacity="0.10"/>'
        )
        svg.append(
            f'<rect x="{bar_x}" y="{y - 12}" width="{bar_w}" height="10" rx="5" '
            f'fill="{ORANGE}"/>'
        )
        svg.append(
            f'<text x="{bar_x + bar_w_max + 10}" y="{y}" font-family="Consolas, monospace" '
            f'font-size="12" fill="{WHITE}" opacity="0.7">{pct * 100:.0f}%</text>'
        )
        y += 34
    svg.append("</svg>")
    return "\n".join(svg)


def main():
    if not TOKEN:
        print("WARNING: GITHUB_TOKEN not set. Public API calls are rate-limited to 60/hr.")

    try:
        user = fetch_user()
        repos = fetch_repos()
        langs = fetch_languages(repos)
    except requests.RequestException as exc:
        print(f"ERROR fetching GitHub data: {exc}", file=sys.stderr)
        sys.exit(1)

    os.makedirs("assets", exist_ok=True)

    with open("assets/stats.svg", "w", encoding="utf-8") as f:
        f.write(build_stats_svg(user, repos))

    with open("assets/langs.svg", "w", encoding="utf-8") as f:
        f.write(build_langs_svg(langs))

    print(f"Generated assets/stats.svg and assets/langs.svg for '{USERNAME}'.")


if __name__ == "__main__":
    main()
