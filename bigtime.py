import ast
import json
import subprocess
import typing as t
import warnings
from dataclasses import dataclass
from pathlib import Path

import click


@click.group()
def bigtime():
    pass


# -------------------------------------------------------------------------
# Data Model
# -------------------------------------------------------------------------


class MatchingRepo(t.TypedDict, total=True):
    """Represents a matched GitHub repository."""

    id: str
    """Unique identifier of the repository."""

    isFork: bool
    """Indicates if the repository is a fork."""

    isPrivate: bool
    """Indicates if the repository is private."""

    nameWithOwner: str
    """Full name of the repository, like t-strings/tdom"""

    url: str
    """HTTPS URL of the repository."""


class MatchingRepoAndFile(t.TypedDict, total=True):
    """Represents a single matching file to our search criteria."""

    path: str
    """Path of the matching file, relative to the root of the repository."""

    sha: str
    """Current SHA of the matching file."""

    repository: MatchingRepo
    """Details about the repository containing the matching file."""


class BigTimeRepo(t.TypedDict, total=True):
    """Represents a repository we are tracking."""

    name_with_owner: str
    """Full name of the repository, like t-strings/tdom"""

    url: str
    """HTTPS URL of the repository."""

    last_checked_sha: str
    """The SHA of the last pyproject.toml version we checked."""

    description: str
    """Description of the repository, if any."""

    stargazers: int
    """Number of stargazers at the time we last checked."""

    homepage: str
    """Homepage URL of the repository, if any."""

    t_string_count: int
    """Number of t-string literals found in the repository."""

    line_count: int
    """Number of python lines of code found in the repository."""

    templatelib_imports: int
    """Number of files importing string.templatelib found in the repository."""

    file_count: int
    """Number of python files found in the repository."""

    license: str
    """License name for the repository, if any."""


# -------------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------------


def invoke_gh_cli(args: list[str]) -> str:
    """Invoke a gh command and return its output."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def shallow_clone_repo(git_url: str, clone_path: Path) -> None:
    """Shallow clone a git repository."""
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:limit=64k",
            git_url,
            str(clone_path),
        ],
        check=True,
        # silence!
        stderr=subprocess.DEVNULL,
    )


def make_git_url(name_with_owner: str) -> str:
    """Convert a GitHub name_with_owner to a git URL."""
    return f"https://github.com/{name_with_owner}.git"


# -------------------------------------------------------------------------
# AST Parsing and Counting Utilities
# -------------------------------------------------------------------------


def count_t_string_literals_in_ast(node: ast.AST) -> int:
    """Count the number of t-string literals in the AST node."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.TemplateStr):
            count += 1
    return count


def does_ast_import_templatelib(node: ast.AST) -> bool:
    """Check if there are import or from import statements for 'string.templatelib'."""
    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                if alias.name == "string.templatelib":
                    return True
        elif isinstance(child, ast.ImportFrom):
            if child.module == "string.templatelib":
                return True
    return False


def parse_python_file(path: Path) -> ast.Module:
    """Parse a Python file and return its AST."""
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.parse(content, filename=str(path))


def count_literals_and_check_imports(path: Path) -> tuple[int, bool]:
    """
    Return the number of t-string literals and whether 'string.templatelib'
    is imported in a given Python file.
    """
    try:
        tree = parse_python_file(path)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return 0, False
    return count_t_string_literals_in_ast(tree), does_ast_import_templatelib(tree)


def count_literals_and_import_files_in_repo(repo_path: Path) -> tuple[int, int]:
    """
    Count the number of t-string literals in all Python files in a repository,
    and the number of files importing 'string.templatelib'.
    """
    t_string_count = 0
    import_files = 0
    for py_file in repo_path.rglob("*.py"):
        count, imports = count_literals_and_check_imports(py_file)
        t_string_count += count
        if imports:
            import_files += 1
    return t_string_count, import_files


def count_python_lines_in_file(path: Path) -> int:
    """Count the number of lines in a Python file, ignoring empty lines and comments."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            lines = file.readlines()
    except (UnicodeDecodeError, OSError):
        return 0
    return sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))


def count_python_lines_in_repo(repo_path: Path) -> int:
    """Count the number of lines in all Python files in a repository."""
    total_count = 0
    for py_file in repo_path.rglob("*.py"):
        total_count += count_python_lines_in_file(py_file)
    return total_count


# -------------------------------------------------------------------------
# find-repos
# -----------------------------------------------------------------------


SPAMMY_USERS = ["poisontr33s"]


def is_maybe_spammy(item: MatchingRepoAndFile) -> bool:
    """Heuristic to identify spammy repositories."""
    # Sigh.
    name = item["repository"]["nameWithOwner"].lower()
    return any(name.startswith(f"{user}/") for user in SPAMMY_USERS)


def filter_repo_match(item: MatchingRepoAndFile) -> bool:
    """Filter repo matches to only top-level pyproject.toml files in non-fork, non-private repos."""
    return (
        item["path"] == "pyproject.toml"
        and not item["repository"]["isFork"]
        and not item["repository"]["isPrivate"]
        and not is_maybe_spammy(item)
    )


@bigtime.command()
def find_repos():
    """
    Run the github command line to find all repos that require Python 3.14
    in their pyproject.toml file. Emit json lines.
    """
    # Echo to stderr that we're running the command
    click.echo("Finding Python 3.14 repositories on GitHub...", err=True)
    json_str = invoke_gh_cli(
        [
            "search",
            "code",
            "--filename=pyproject.toml",
            'requires-python = ">=3.14"',
            "--json",
            "repository,path,sha",
            "--limit",
            "1000",
        ]
    )
    data = t.cast(list[MatchingRepoAndFile], json.loads(json_str))
    matching = [item for item in data if filter_repo_match(item)]
    for item in matching:
        click.echo(json.dumps(item))


# -------------------------------------------------------------------------
# identify-updates
# -------------------------------------------------------------------------


@bigtime.command()
@click.option("-r", "--repos_path", type=click.Path(exists=True, path_type=Path))
@click.option("-s", "--state_path", type=click.Path(path_type=Path))
def identify_updates(repos_path: Path, state_path: Path):
    """
    Identify which repos have been updated since we last checked them.

    REPOS_PATH is a path to a file containing json lines of repos to check.
    STATE_PATH is a path to a json file containing the last known state.

    Emit json lines of repos that have been updated (or are new).
    """
    click.echo("Identifying new or updated repositories...", err=True)
    with open(repos_path, "r", encoding="utf-8") as f:
        repos = t.cast(list[MatchingRepoAndFile], [json.loads(line) for line in f])

    state: list[BigTimeRepo] = []
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            state = t.cast(list[BigTimeRepo], [json.loads(line) for line in f])

    state_map = {repo["name_with_owner"]: repo for repo in state}
    updates: list[MatchingRepoAndFile] = []
    for repo in repos:
        name_with_owner = repo["repository"]["nameWithOwner"]
        sha = repo["sha"]

        if (
            name_with_owner not in state_map
            or state_map[name_with_owner]["last_checked_sha"] != sha
        ):
            updates.append(repo)

    for update in updates:
        click.echo(json.dumps(update))


# -------------------------------------------------------------------------
# process-updates
# -------------------------------------------------------------------------


@bigtime.command()
@click.option("-u", "--updates_path", type=click.Path(exists=True, path_type=Path))
def process_updates(updates_path: Path):
    with open(updates_path, "r", encoding="utf-8") as f:
        updates = t.cast(list[MatchingRepoAndFile], [json.loads(line) for line in f])

    for update in updates:
        click.echo(f"Processing: {update['repository']['nameWithOwner']}", err=True)
        big_time_repo = process_single_update(update)
        click.echo(json.dumps(big_time_repo))


def process_single_update(update: MatchingRepoAndFile) -> BigTimeRepo:
    """
    Process a single repository update or new repository and return its
    BigTimeRepo representation.

    To do this, we must:

    1. Use the `gh` CLI to get stargazer count, description, and homepage.
    2. Shallow clone the repository to a temp directory.
    3. Walk the repository to find all Python files.
    4. Parse each Python file to count t-string literals and lines of code.
    """
    name_with_owner = update["repository"]["nameWithOwner"]

    meta = get_repository_meta(name_with_owner)
    stats = get_repository_code_stats(name_with_owner)

    return BigTimeRepo(
        name_with_owner=name_with_owner,
        url=update["repository"]["url"],
        last_checked_sha=update["sha"],
        description=meta.description,
        stargazers=meta.stargazers,
        homepage=meta.homepage,
        license=meta.license,
        t_string_count=stats.t_string_count,
        line_count=stats.line_count,
        templatelib_imports=stats.templatelib_imports,
        file_count=stats.file_count,
    )


# -------------------------------------------------------------------------
# repo-meta
# -------------------------------------------------------------------------


@bigtime.command()
@click.argument("name_with_owner")
def repo_meta(name_with_owner: str):
    """Get repository metadata using gh CLI."""
    meta = get_repository_meta(name_with_owner)
    click.echo(f"Repository: {name_with_owner}", err=True)
    click.echo(f"Stargazers: {meta.stargazers:,}", err=True)
    click.echo(f"Description: {meta.description}", err=True)
    click.echo(f"Homepage: {meta.homepage}", err=True)
    click.echo(f"License: {meta.license}", err=True)


@dataclass(frozen=True, slots=True)
class RepoMeta:
    stargazers: int
    description: str
    homepage: str
    license: str


def get_repository_meta(name_with_owner: str) -> RepoMeta:
    """Use gh repo view to get stargazers, description, and homepage."""
    repo_info = invoke_gh_cli(
        [
            "repo",
            "view",
            name_with_owner,
            "--json",
            "stargazerCount,description,homepageUrl,licenseInfo",
        ]
    )
    data = json.loads(repo_info)
    return RepoMeta(
        stargazers=data["stargazerCount"],
        description=data.get("description", ""),
        homepage=data.get("homepageUrl", ""),
        license=data.get("licenseInfo", {}).get("name", "")
        if data.get("licenseInfo")
        else "",
    )


# -------------------------------------------------------------------------
# repo-stats
# -------------------------------------------------------------------------


@bigtime.command()
@click.argument("name_with_owner")
def repo_stats(name_with_owner: str):
    """Get repository code stats by shallow cloning and analyzing."""
    stats = get_repository_code_stats(name_with_owner)
    click.echo(f"Repository: {name_with_owner}", err=True)
    click.echo(f"T-string literals: {stats.t_string_count:,}", err=True)
    click.echo(f"Python lines of code: {stats.line_count:,}", err=True)
    click.echo(
        f"Files importing string.templatelib: {stats.templatelib_imports:,}", err=True
    )
    click.echo(f"Python files: {stats.file_count:,}", err=True)


@dataclass(frozen=True, slots=True)
class CodeStats:
    t_string_count: int
    templatelib_imports: int
    line_count: int
    file_count: int


def get_repository_code_stats(name_with_owner: str) -> CodeStats:
    """Shallow clone the repository and count t-string literals and lines of code."""
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        git_url = make_git_url(name_with_owner)
        try:
            shallow_clone_repo(git_url, repo_path)
        except subprocess.CalledProcessError as e:
            click.echo(f"Error cloning repository {name_with_owner}: {e}", err=True)
            return CodeStats(0, 0, 0, 0)
        t_string_count, import_files = count_literals_and_import_files_in_repo(
            repo_path
        )
        line_count = count_python_lines_in_repo(repo_path)
        file_count = sum(1 for _ in repo_path.rglob("*.py"))
    return CodeStats(t_string_count, import_files, line_count, file_count)


# -------------------------------------------------------------------------
# merge-state
# -------------------------------------------------------------------------


@bigtime.command()
@click.option("-o", "--old_path", type=click.Path(path_type=Path))
@click.option("-n", "--new_path", type=click.Path(exists=True, path_type=Path))
def merge_state(old_path: Path, new_path: Path):
    """
    Merge old state with new state, preferring new state entries.

    OLD_PATH is a path to a file containing json lines of old state.
    NEW_PATH is a path to a file containing json lines of new state.

    Emit merged json lines to stdout.
    """
    click.echo("Merging old and new state...", err=True)
    old_state: list[BigTimeRepo] = []
    if old_path.exists():
        with open(old_path, "r", encoding="utf-8") as f:
            old_state = t.cast(list[BigTimeRepo], [json.loads(line) for line in f])

    new_state: list[BigTimeRepo] = []
    with open(new_path, "r", encoding="utf-8") as f:
        new_state = t.cast(list[BigTimeRepo], [json.loads(line) for line in f])

    state_map = {repo["name_with_owner"]: repo for repo in old_state}
    for repo in new_state:
        state_map[repo["name_with_owner"]] = repo

    merged_state = list(state_map.values())
    for repo in merged_state:
        click.echo(json.dumps(repo))


# -------------------------------------------------------------------------
# top-repos
# -------------------------------------------------------------------------


def t_string_power(repo: BigTimeRepo) -> float:
    """Calculate a "t-string power" metric for ranking repositories."""
    if repo["line_count"] == 0:
        return 0
    if repo["t_string_count"] == 0:
        return 0
    return repo["t_string_count"] / repo["line_count"] * (repo["stargazers"] + 1.0)


def build_top_repos(state: list[BigTimeRepo]) -> list[BigTimeRepo]:
    """Build a list of top repositories based on t-string power."""
    t_string_using = (
        repo for repo in state if repo["t_string_count"] > 0 and repo["line_count"] > 0
    )
    return sorted(t_string_using, reverse=True, key=t_string_power)


@bigtime.command()
@click.argument("state_path", type=click.Path(exists=True, path_type=Path))
@click.option("--asjson", is_flag=True, default=False, help="Output as JSON lines.")
def top_repos(state_path: Path, asjson: bool):
    """
    List the BIG TIME t-string-usiest repositories.

    A repository is considered "big time" if it has a high number of
    t-string literals relative to its lines of Python code. Stargazer
    count is also displayed for context.
    """
    with open(state_path, "r", encoding="utf-8") as f:
        state = t.cast(list[BigTimeRepo], [json.loads(line) for line in f])

    top_repos = build_top_repos(state)

    if asjson:
        for repo in top_repos:
            click.echo(json.dumps(repo))
        return

    click.echo(
        f"{'Repository':<30} {'T-Strings':>9} {'Lines':>8} {'Imports':>8} {'Stars':>8} {'Power':>8}"
    )
    click.echo("-" * 80)
    for repo in top_repos:
        power = t_string_power(repo)
        click.echo(
            f"{repo['name_with_owner']:<30} {repo['t_string_count']:>9} {repo['line_count']:>8} {repo['templatelib_imports']:>8} {repo['stargazers']:>8} {power:>8.1f}"
        )


if __name__ == "__main__":
    bigtime()
