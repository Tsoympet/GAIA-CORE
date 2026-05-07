from gaia.metacognition import ReflectionLoop


def test_reflection_loop_tracks_confidence_and_risks() -> None:
    report = ReflectionLoop().review("short", {"agent": 0.4, "route": 0.6})

    assert report.confidence.confidence == 0.5
    assert report.critique.risks
