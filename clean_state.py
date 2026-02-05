import json
from pathlib import Path


def main() -> None:
    state_path = Path("data_international/monitor_state.json")
    if not state_path.exists():
        raise FileNotFoundError(f"State file not found: {state_path}")

    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    seen_items = state.get("seen_items", {})
    filtered_seen = {
        key: value
        for key, value in seen_items.items()
        if not key.startswith("federal_register")
    }

    # Preserve all other fields (e.g., last_check, published_stories).
    state["seen_items"] = filtered_seen

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
