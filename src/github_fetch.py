import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from github import Auth, Github, GithubException

import config

_INTERESTING_KEYWORDS = re.compile(r"\b(fix|refactor|ship|rewrite|delete|remove|overhaul|migrate|redesign)\b", re.I)
_MAX_DIFF_CHARS = 8_000


@dataclass
class Commit:
    repo: str
    sha: str
    message: str
    additions: int
    deletions: int
    files_changed: list[str] = field(default_factory=list)
    committed_at: str = ""
    url: str = ""
    diff: str | None = None


def _is_interesting(commit: Commit) -> bool:
    total_lines = commit.additions + commit.deletions
    if total_lines > 50:
        return True
    if _INTERESTING_KEYWORDS.search(commit.message):
        return True
    return False


def fetch_recent_commits(hours: int = 24) -> list[Commit]:
    auth = Auth.Token(config.GITHUB_TOKEN)
    gh = Github(auth=auth)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    results: list[Commit] = []
    total_diff_chars = 0

    try:
        user = gh.get_user()  # authenticated user — sees private repos
        repos = list(user.get_repos(type="all"))
    except GithubException as e:
        raise RuntimeError(f"failed to fetch repos: {e}") from e

    for repo in repos:
        if repo.name in config.REPO_BLACKLIST:
            continue
        if repo.fork:
            continue

        try:
            commits = repo.get_commits(since=since)
            for raw in commits:
                stats = raw.stats
                files = [f.filename for f in raw.files]

                commit = Commit(
                    repo=repo.name,
                    sha=raw.sha[:7],
                    message=raw.commit.message.split("\n")[0],
                    additions=stats.additions,
                    deletions=stats.deletions,
                    files_changed=files,
                    committed_at=raw.commit.committer.date.isoformat(),
                    url=raw.html_url,
                )

                if _is_interesting(commit) and total_diff_chars < _MAX_DIFF_CHARS:
                    try:
                        patch_parts = [f.patch for f in raw.files if f.patch]
                        patch = "\n".join(patch_parts)
                        remaining = _MAX_DIFF_CHARS - total_diff_chars
                        commit.diff = patch[:remaining]
                        total_diff_chars += len(commit.diff)
                    except Exception:
                        pass

                results.append(commit)
        except GithubException:
            continue

    gh.close()
    results.sort(key=lambda c: c.committed_at, reverse=True)
    return results


@dataclass
class StaleRepo:
    name: str
    last_commit_days_ago: int
    last_message: str


def fetch_stale_repos(stale_after_days: int = 14) -> list[StaleRepo]:
    auth = Auth.Token(config.GITHUB_TOKEN)
    gh = Github(auth=auth)
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_after_days)
    stale = []

    try:
        user = gh.get_user()
        repos = user.get_repos(type="all")
        for repo in repos:
            if repo.fork or repo.name in config.REPO_BLACKLIST:
                continue
            try:
                commits = list(repo.get_commits())
                if not commits:
                    continue
                latest = commits[0]
                last_date = latest.commit.committer.date
                if last_date.tzinfo is None:
                    last_date = last_date.replace(tzinfo=timezone.utc)
                if last_date < cutoff:
                    days_ago = (datetime.now(timezone.utc) - last_date).days
                    stale.append(StaleRepo(
                        name=repo.name,
                        last_commit_days_ago=days_ago,
                        last_message=latest.commit.message.split("\n")[0],
                    ))
            except GithubException:
                continue
    finally:
        gh.close()

    stale.sort(key=lambda r: r.last_commit_days_ago, reverse=True)
    return stale


def summarize_for_llm(commits: list[Commit], stale_repos: list[StaleRepo] | None = None) -> str:
    lines = []

    if not commits:
        lines.append("commits today: none.")
    else:
        for c in commits:
            diff_note = f"\n  diff (truncated):\n{c.diff}" if c.diff else ""
            files = ", ".join(c.files_changed[:5])
            if len(c.files_changed) > 5:
                files += f" (+{len(c.files_changed) - 5} more)"
            lines.append(
                f"- [{c.repo}] {c.message} (+{c.additions}/-{c.deletions} lines, files: {files}){diff_note}"
            )

    if stale_repos:
        lines.append(f"\nunfinished project debt ({len(stale_repos)} repos abandoned):")
        for r in stale_repos[:5]:
            lines.append(f"- {r.name}: last commit {r.last_commit_days_ago} days ago (\"{r.last_message}\")")

    return "\n".join(lines)
