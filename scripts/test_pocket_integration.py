import os
import sys
from pprint import pprint

# Ensure workspace root is on sys.path for `src.*` imports
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from src.app.integrations.pocket import PocketClient, extract_latest_summary, extract_transcript_text


def main():
    api_key = os.getenv("POCKET_API_KEY")
    if not api_key:
        print("POCKET_API_KEY not set. Export it before running.")
        print("Example: export POCKET_API_KEY=pk_...\n")
        return

    client = PocketClient(api_key=api_key)
    print("Listing recent recordings…")
    listings = client.list_recordings(page=1, limit=5)
    pprint(listings)

    data = listings.get("data") or {}
    items = data if isinstance(data, list) else data.get("items") or []
    if not items:
        print("No recordings found.")
        return

    rec_id = items[0].get("id") or items[0].get("recording_id")
    if not rec_id:
        print("Could not determine recording id from list item:")
        pprint(items[0])
        return

    print(f"\nFetching details for recording: {rec_id}")
    details = client.get_recording(rec_id, include_transcript=True, include_summarizations=True)
    pprint(details)

    summary_text, _ = extract_latest_summary(details)
    transcript_text = extract_transcript_text(details)

    print("\nLatest summary (truncated to 500 chars):\n")
    if summary_text:
        print(summary_text[:500])
    else:
        print("<no summary>")

    print("\nTranscript (truncated to 500 chars):\n")
    if transcript_text:
        print(transcript_text[:500])
    else:
        print("<no transcript>")


if __name__ == "__main__":
    main()
