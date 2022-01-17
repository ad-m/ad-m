import os
from github import Github
from itertools import groupby, islice
from tqdm import tqdm
import time

# Design assumptions:
# * minimal dependency count
# * minimal maintenance
# * if maintenance required, make it dead easy to remind

query = "is:pr author:ad-m"

MAX_PR = 10 ** 5
MIN_STARGAZE = 10

PR_TAG_START = "<!-- PR-list-start -->"
PR_TAG_END = "<!-- PR-list-end -->"

g = Github(os.environ["GH_TOKEN"])

popular_org = ["ad-m", "watchdogpolska", "hyperonecom"]


def throttled_iterator(iter, sleep=0.1):
    # poor rate-limit protection
    for x in iter:
        yield x
        time.sleep(sleep)


def download_issues(query, orgs):
    exclude_org = " ".join(f"-org:{o}" for o in orgs)
    yield from throttled_iterator(g.search_issues(query=f"{query} {exclude_org}"))
    for o in orgs:
        yield from throttled_iterator(g.search_issues(query=f"{query} org:{o}"))


def format_issues(issues):
    # GitHub does not support sorting issues by repository / stargers of repository
    issues_sorted = sorted(
        tqdm(islice(issues, MAX_PR)),
        key=lambda i: (
            i.repository.stargazers_count,
            i.repository.full_name,
            i.created_at,
        ),
        reverse=True,
    )
    issues_by_repository = groupby(issues_sorted, key=lambda i: i.repository)
    minimum_issue = 0
    minimum_repo = 0
    for i, (repo, issues) in enumerate(issues_by_repository):
        issues = list(issues)
        issue_count = len(issues)
        if repo.stargazers_count < MIN_STARGAZE:
            minimum_issue += issue_count
            minimum_repo += 1
            continue
        star_img = (
            f"![about {repo.stargazers_count} stars]"
            + "(https://img.shields.io/github/stars/{repo.full_name}?style=plastic)"
        )
        fork_img = (
            f"![about {repo.forks} forks]"
            + "(https://img.shields.io/github/forks/{repo.full_name}?style=plastic)"
        )
        yield f"* [{repo.full_name}]({repo.html_url}) {star_img} {fork_img}"
        yield ""
        p = " " * 4
        if issue_count > 100:
            yield f"{p}* skipped {issue_count} for the sake of clarity"
        else:
            for issue in issues:
                status = "[ ]" if issue.state == "open" else "[x]"
                stime = issue.created_at.strftime("%Y.%m.%d")
                yield f"{p}* {status} [{issue.title}]({issue.html_url}) - {stime}"
    yield ""
    yield (
        f"Also, {minimum_issue} pull requests in {minimum_repo} repositories "
        + "not worth mentioning (< {MIN_STARGAZE} stars) here for the sake of clarity."
    )


def replace_content(content, value, start, end):
    pre, x = content.split(start, 2)
    _, post = x.split(end, 2)
    return "\n".join(x.strip() for x in [pre, start, value, end, post])


def replace_pr_list(value, filename):
    with open(filename) as fp:
        content = fp.read()

    updated_content = replace_content(content, value, PR_TAG_START, PR_TAG_END)

    with open(filename, "w") as fp:
        fp.write(updated_content)


if __name__ == "__main__":
    issues = download_issues(query, popular_org)
    pr_list_value = "\n".join(format_issues(issues))
    replace_pr_list(pr_list_value, "./README.md")
