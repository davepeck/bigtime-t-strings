ALL_REPOS_PATH := "data/all-repos.jsonl"
BIG_TIME_PATH := "data/big-time.jsonl"
OLD_BIG_TIME_PATH := "data/OLD-big-time.jsonl"
UPDATE_PATH := "data/updates.jsonl"
BIG_TIME_UPDATES_PATH := "data/updated-big-time.jsonl"


default: find_repos identify_updates process_updates merge_big_time


find_repos:
    # Find repositories with top-level pyproject.toml specifying requires-python >=3.14
    uv run python bigtime.py find-repos > {{ALL_REPOS_PATH}}


identify_updates:
    rm -f {{UPDATE_PATH}}
    uv run python bigtime.py identify-updates -r {{ALL_REPOS_PATH}} -s {{BIG_TIME_PATH}} > {{UPDATE_PATH}}

process_updates:
    rm -f {{BIG_TIME_UPDATES_PATH}}
    uv run python bigtime.py process-updates -u {{UPDATE_PATH}} > {{BIG_TIME_UPDATES_PATH}}


merge_big_time:
    mv {{BIG_TIME_PATH}} {{OLD_BIG_TIME_PATH}} || true
    uv run python bigtime.py merge-state -o {{OLD_BIG_TIME_PATH}} -n {{BIG_TIME_UPDATES_PATH}} > {{BIG_TIME_PATH}}
    rm -f {{OLD_BIG_TIME_PATH}}

top_repos:
    uv run python bigtime.py top-repos {{BIG_TIME_PATH}}

top_repos_json:
    uv run python bigtime.py top-repos --asjson {{BIG_TIME_PATH}}

clean: 
    rm -f {{ALL_REPOS_PATH}} {{UPDATE_PATH}} {{BIG_TIME_UPDATES_PATH}} {{OLD_BIG_TIME_PATH}}

deep_clean: clean
    rm -f {{BIG_TIME_PATH}}
    rm -f data/*.jsonl

