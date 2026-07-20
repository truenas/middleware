import json

import pytest

from middlewared.plugins.apps.compose_progress import ComposeProgressTracker

IMAGE = "Image nginx:1.27-alpine"


def make_tracker(resources_expected):
    emitted = []
    tracker = ComposeProgressTracker(
        lambda fraction, description: emitted.append((fraction, description)),
        resources_expected=resources_expected,
        min_interval=0,
    )
    return tracker, emitted


def feed(tracker, event):
    tracker.feed_line(json.dumps(event))


def layer_event(layer_id, text, current=None, total=None, status="Working"):
    event = {"id": layer_id, "parent_id": IMAGE, "status": status, "text": text}
    if current is not None:
        event.update(current=current, total=total)
    return event


def test_pull_progress_is_monotonic_and_completes():
    tracker, emitted = make_tracker(resources_expected=False)
    feed(tracker, {"id": IMAGE, "status": "Working", "text": "Pulling"})
    feed(tracker, layer_event("aaa", "Pulling fs layer"))
    feed(tracker, layer_event("bbb", "Pulling fs layer"))
    feed(tracker, layer_event("aaa", "Downloading", 500, 1000))
    feed(tracker, layer_event("aaa", "Downloading", 1000, 1000))
    feed(tracker, layer_event("bbb", "Downloading", 2000, 4000))
    feed(tracker, layer_event("aaa", "Extracting", 500, 1000))
    feed(tracker, layer_event("aaa", "Pull complete", status="Done"))
    feed(tracker, layer_event("bbb", "Downloading", 4000, 4000))
    feed(tracker, layer_event("bbb", "Extracting", 4000, 4000))
    feed(tracker, layer_event("bbb", "Pull complete", status="Done"))
    feed(tracker, {"id": IMAGE, "status": "Done", "text": "Pulled"})

    fractions = [fraction for fraction, _ in emitted]
    assert fractions, "no progress was emitted"
    assert fractions == sorted(fractions), fractions
    assert fractions[-1] == 1.0
    assert any(0 < fraction < 1 for fraction in fractions), fractions


def test_late_layer_size_announcement_does_not_regress():
    tracker, emitted = make_tracker(resources_expected=False)
    feed(tracker, layer_event("aaa", "Downloading", 1000, 1000))
    high_water = emitted[-1][0]
    # A second, much larger layer announcing its size grows the denominator
    feed(tracker, layer_event("bbb", "Downloading", 1, 10_000_000))
    fractions = [fraction for fraction, _ in emitted]
    assert fractions == sorted(fractions), fractions
    assert fractions[-1] >= high_water


def test_unsized_layers_damp_early_progress():
    tracker, emitted = make_tracker(resources_expected=False)
    for layer_id in ("aaa", "bbb", "ccc", "ddd"):
        feed(tracker, layer_event(layer_id, "Pulling fs layer"))
    feed(tracker, layer_event("aaa", "Downloading", 1000, 1000))
    feed(tracker, layer_event("aaa", "Pull complete", status="Done"))
    # One of four layers complete is roughly a quarter of the image, not almost all of it
    assert emitted[-1][0] == pytest.approx(0.25)


def test_up_reserves_progress_for_resources():
    tracker, emitted = make_tracker(resources_expected=True)
    feed(tracker, layer_event("aaa", "Downloading", 1000, 1000))
    feed(tracker, layer_event("aaa", "Pull complete", status="Done"))
    feed(tracker, {"id": IMAGE, "status": "Done", "text": "Pulled"})
    assert emitted[-1][0] == pytest.approx(0.9)

    feed(tracker, {"id": "Network myapp_default", "status": "Working", "text": "Creating"})
    feed(tracker, {"id": "Network myapp_default", "status": "Done", "text": "Created"})
    feed(tracker, {"id": "Container myapp-web-1", "status": "Working", "text": "Creating"})
    feed(tracker, {"id": "Container myapp-web-1", "status": "Done", "text": "Created"})
    feed(tracker, {"id": "Container myapp-web-1", "status": "Working", "text": "Starting"})
    feed(tracker, {"id": "Container myapp-web-1", "status": "Done", "text": "Started"})

    fractions = [fraction for fraction, _ in emitted]
    assert fractions == sorted(fractions), fractions
    # The reserved band climbs but does not collapse to 100% while containers are still deploying
    assert 0.9 < emitted[-1][0] < 1.0
    assert emitted[-1][1] == "Started Container myapp-web-1"

    tracker.flush()
    assert emitted[-1][0] == 1.0


def test_up_without_pull_progresses_incrementally():
    # Real compose ordering for a config-only update: no image events (image already present),
    # the network is created before the containers, which are then recreated and started.
    tracker, emitted = make_tracker(resources_expected=True)
    feed(tracker, {"id": "Network myapp_default", "status": "Working", "text": "Creating"})
    feed(tracker, {"id": "Network myapp_default", "status": "Done", "text": "Created"})
    # The network finishing must not read as 100% - the slow container recreates are still to come
    after_network = emitted[-1][0]
    assert after_network < 1.0
    feed(tracker, {"id": "Container myapp-web-1", "status": "Working", "text": "Recreate"})
    feed(tracker, {"id": "Container myapp-web-1", "status": "Done", "text": "Created"})
    feed(tracker, {"id": "Container myapp-web-1", "status": "Working", "text": "Starting"})
    feed(tracker, {"id": "Container myapp-web-1", "status": "Done", "text": "Started"})
    # The first container finishing advances progress but must not read as 100%
    # while another is still pending
    after_first = emitted[-1][0]
    assert after_network < after_first < 1.0
    feed(tracker, {"id": "Container myapp-db-1", "status": "Done", "text": "Created"})

    fractions = [fraction for fraction, _ in emitted]
    assert fractions == sorted(fractions), fractions
    assert after_first < emitted[-1][0] < 1.0
    tracker.flush()
    assert emitted[-1][0] == 1.0


def test_cached_layers_count_as_complete():
    # Mixed pull: one layer already present locally, one still downloading. The cached layer
    # must count as complete (weighted as average-sized, its size is never announced), not as
    # not-started.
    tracker, emitted = make_tracker(resources_expected=False)
    feed(tracker, layer_event("aaa", "Already exists", status="Done"))
    feed(tracker, layer_event("bbb", "Downloading", 0, 1000))
    assert emitted[-1][0] == pytest.approx(0.5)
    feed(tracker, layer_event("bbb", "Pull complete", status="Done"))
    feed(tracker, {"id": IMAGE, "status": "Done", "text": "Pulled"})
    assert emitted[-1][0] == 1.0


def test_description_reports_downloaded_bytes():
    tracker, emitted = make_tracker(resources_expected=False)
    feed(tracker, layer_event("aaa", "Downloading", 512 * 1024, 1024 * 1024))
    assert emitted[-1][1] == "Pulling app images (512 KiB / 1 MiB)"


def test_malformed_input_is_ignored():
    tracker, emitted = make_tracker(resources_expected=False)
    tracker.feed_line("")
    tracker.feed_line("plain text output")
    tracker.feed_line('{"truncated json')
    tracker.feed_line("[1, 2, 3]")
    tracker.feed_line(json.dumps({"error": True, "message": "pull access denied"}))
    tracker.feed_line(json.dumps({"id": IMAGE, "status": "Error", "text": "Error", "details": "denied"}))
    tracker.feed_line(json.dumps({"id": 42, "status": "Done", "text": "Pulled"}))
    assert emitted == []


def test_duplicate_progress_not_reemitted():
    tracker, emitted = make_tracker(resources_expected=False)
    feed(tracker, layer_event("aaa", "Downloading", 500, 1000))
    feed(tracker, layer_event("aaa", "Downloading", 500, 1000))
    assert len(emitted) == 1


def test_flush_bypasses_throttle():
    emitted = []
    tracker = ComposeProgressTracker(
        lambda fraction, description: emitted.append((fraction, description)),
        resources_expected=False,
        min_interval=3600,
    )
    feed(tracker, layer_event("aaa", "Downloading", 500, 1000))
    # Final events land within the throttle interval and are suppressed
    feed(tracker, layer_event("aaa", "Pull complete", status="Done"))
    feed(tracker, {"id": IMAGE, "status": "Done", "text": "Pulled"})
    assert emitted[-1][0] < 1.0

    tracker.flush()
    assert emitted[-1][0] == 1.0
