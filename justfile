ALL_REPOS_PATH := "data/all-repos.jsonl"
BIG_TIME_PATH := "data/big-time.jsonl"
BIG_TIME_UPDATES_PATH := "data/updated-big-time.jsonl"
INDEX_HTML := "dist/index.html"


default: find_repos process_updates


find_repos:
    # Find repositories with top-level pyproject.toml specifying requires-python >=3.14
    rm -f {{ALL_REPOS_PATH}}
    uv run python bigtime.py find-repos > {{ALL_REPOS_PATH}}

process_updates:
    # Process updates against existing big-time.jsonl, creating a new big-time.jsonl
    rm -f {{BIG_TIME_UPDATES_PATH}}
    uv run python bigtime.py process-updates -r {{ALL_REPOS_PATH}} -s {{BIG_TIME_PATH}} > {{BIG_TIME_UPDATES_PATH}}
    rm -f {{BIG_TIME_PATH}}
    mv {{BIG_TIME_UPDATES_PATH}} {{BIG_TIME_PATH}}

top_repos:
    uv run python bigtime.py top-repos {{BIG_TIME_PATH}}

top_repos_json:
    uv run python bigtime.py top-repos --asjson {{BIG_TIME_PATH}}

clean: 
    rm -f {{ALL_REPOS_PATH}} {{BIG_TIME_UPDATES_PATH}}

deep_clean: clean
    rm -f {{BIG_TIME_PATH}}
    rm -f data/*.jsonl

build_site:
    mkdir -p dist
    uv run python bigtime.py build-site {{BIG_TIME_PATH}} > dist/index.html
    cp public/* dist/
