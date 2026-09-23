#!/usr/bin/env python3
"""Collect git history into a structured digest for a weekly report.

Scans one or more git repos, filters by date window + author, parses
Conventional Commit subjects (`type(scope): subject`), and groups by
repo -> type -> scope. The model consuming this output writes the prose.

Defaults: current repo, this week (Mon 00:00 -> now), author = each
repo's `git config user.email`.

Usage:
  python weekly.py
  python weekly.py --repo ../repo-a --repo ../repo-b
  python weekly.py --since 2026-05-12 --until 2026-05-19
  python weekly.py --all-authors          # everyone, not just me
  python weekly.py --author alice        # override author filter
  python weekly.py --branch develop-bl     # one branch (default: all branches)
  python weekly.py --stat                  # add files/insertions/deletions
  python weekly.py --body                  # include commit body (the "why")
"""
import os, sys, subprocess, argparse
from collections import defaultdict, OrderedDict
from datetime import date, datetime, timedelta

# Windows consoles mojibake non-ASCII; force UTF-8 so Chinese subjects survive.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TYPE_ORDER = ["feat", "fix", "perf", "refactor", "test", "docs",
              "chore", "style", "build", "ci"]


def parse_args():
    p = argparse.ArgumentParser(description="Git -> weekly report digest")
    p.add_argument("--repo", action="append", default=[],
                   help="repo path (repeatable; default: cwd)")
    p.add_argument("--since", help="start date YYYY-MM-DD (default: Monday this week)")
    p.add_argument("--until", help="end date YYYY-MM-DD inclusive (default: today)")
    p.add_argument("--author", help="author filter substring (default: repo user.email)")
    p.add_argument("--all-authors", action="store_true", help="do not filter by author")
    p.add_argument("--branch", help="restrict to one branch (default: all branches)")
    p.add_argument("--stat", action="store_true", help="add files/+/- aggregates")
    p.add_argument("--body", action="store_true", help="include commit body")
    return p.parse_args()


def week_window(a):
    until = a.until or date.today().isoformat()
    if a.since:
        since = a.since
    else:
        t = date.today()
        since = (t - timedelta(days=t.weekday())).isoformat()  # Monday
    return since, until


def git(repo, args):
    try:
        out = subprocess.run(["git", "-C", repo] + args,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return out.stdout if out.returncode == 0 else ""
    except FileNotFoundError:
        sys.exit("error: git not found on PATH")


def split_conventional(subject):
    """`feat(scope): msg` -> ('feat', 'scope', 'msg'); else ('other', '', subj)."""
    head = subject.split(":", 1)
    if len(head) == 2 and head[0].strip():
        left, msg = head[0].strip(), head[1].strip()
        bang = left.endswith("!")
        left = left.rstrip("!")
        if "(" in left and left.endswith(")"):
            typ, scope = left.split("(", 1)
            scope = scope[:-1]
        else:
            typ, scope = left, ""
        typ = typ.strip().lower()
        if typ in TYPE_ORDER or typ == "sync":
            return typ, scope.strip(), msg + ("  [BREAKING]" if bang else "")
    return "other", "", subject


def collect(repo, since, until, author, branch, want_body):
    rng = ["--all"] if not branch else [branch]
    sep = "\x1e"  # record sep
    fmt = "%H%x1f%cI%x1f%an%x1f%s%x1f%b" + sep
    args = ["log"] + rng + ["--no-merges",
            f"--since={since} 00:00", f"--until={until} 23:59",
            f"--pretty=format:{fmt}"]
    if author:
        args.append(f"--author={author}")
    raw = git(repo, args)
    commits = []
    for rec in raw.split(sep):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split("\x1f")
        if len(parts) < 4:
            continue
        h, ci, an, subj = parts[0], parts[1], parts[2], parts[3]
        body = parts[4].strip() if want_body and len(parts) > 4 else ""
        typ, scope, msg = split_conventional(subj)
        commits.append((h[:7], ci[:10], an, typ, scope, msg, body))
    # de-dup by short hash (a commit can appear on multiple branches)
    seen, uniq = set(), []
    for c in commits:
        if c[0] in seen:
            continue
        seen.add(c[0]); uniq.append(c)
    return uniq


def repo_stat(repo, since, until, author, branch):
    rng = ["--all"] if not branch else [branch]
    args = ["log"] + rng + ["--no-merges", f"--since={since} 00:00",
            f"--until={until} 23:59", "--shortstat", "--pretty=format:%H"]
    if author:
        args.append(f"--author={author}")
    files = ins = dele = 0
    for line in git(repo, args).splitlines():
        line = line.strip()
        if "file" in line and "changed" in line:
            for tok in line.split(","):
                tok = tok.strip()
                n = int(tok.split()[0]) if tok and tok.split()[0].isdigit() else 0
                if "file" in tok:
                    files += n
                elif "insertion" in tok:
                    ins += n
                elif "deletion" in tok:
                    dele += n
    return files, ins, dele


def main():
    a = parse_args()
    repos = a.repo or [os.getcwd()]
    since, until = week_window(a)
    print(f"window: {since} ~ {until}  | "
          f"author: {'(all)' if a.all_authors else (a.author or 'per-repo user.email')}  | "
          f"branch: {a.branch or 'ALL'}")

    grand = 0
    for repo in repos:
        repo = repo.replace("\\", "/").rstrip("/")
        if not os.path.isdir(os.path.join(repo, ".git")) and \
           git(repo, ["rev-parse", "--is-inside-work-tree"]).strip() != "true":
            print(f"\n=== repo: {repo}  [SKIPPED: not a git repo] ===")
            continue
        if a.all_authors:
            author = None
        else:
            author = a.author or git(repo, ["config", "user.email"]).strip() or None
        commits = collect(repo, since, until, author, a.branch, a.body)
        name = os.path.basename(repo)
        print(f"\n=== repo: {name}  ({repo}) ===")
        if not commits:
            print("  (no commits in window)")
            continue
        grand += len(commits)
        by_type = defaultdict(lambda: defaultdict(list))
        for h, ci, an, typ, scope, msg, body in commits:
            by_type[typ][scope].append((h, ci, msg, body))
        ordered = [t for t in TYPE_ORDER if t in by_type] + \
                  [t for t in by_type if t not in TYPE_ORDER]
        for typ in ordered:
            n = sum(len(v) for v in by_type[typ].values())
            print(f"  {typ} ({n})")
            for scope in sorted(by_type[typ]):
                tag = f"[{scope}] " if scope else ""
                for h, ci, msg, body in by_type[typ][scope]:
                    print(f"    {tag}{h} {ci}  {msg}")
                    if body:
                        for bl in body.splitlines():
                            if bl.strip():
                                print(f"        | {bl.strip()}")
        line = f"  -- {name}: {len(commits)} commits"
        if a.stat:
            f, i, d = repo_stat(repo, since, until, author, a.branch)
            line += f", {f} files, +{i}/-{d}"
        print(line + " --")

    print(f"\n=== TOTAL: {grand} commits across {len(repos)} repo(s) "
          f"({since} ~ {until}) ===")


if __name__ == "__main__":
    main()
