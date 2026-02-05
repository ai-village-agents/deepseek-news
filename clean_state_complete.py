import json
from pathlib import Path


def main() -> None:
    state_path = Path("data_international/monitor_state.json")
    if not state_path.exists():
        raise FileNotFoundError(f"State file not found: {state_path}")

    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    seen_items = state.get("seen_items", {})
    state["seen_items"] = {
        key: value for key, value in seen_items.items() if not key.startswith("federal_register")
    }

    published_stories = state.get("published_stories", [])
    state["published_stories"] = [
        story
        for story in published_stories
        if not str(story.get("id", "")).startswith("federal_register")
    ]

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
