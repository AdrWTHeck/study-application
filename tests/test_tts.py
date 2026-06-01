from domain.accessibility.tts_service import TTSService


def test_no_engine_is_safe_noop():
    # autostart=False simulates an environment without pyttsx3 / audio.
    tts = TTSService(autostart=False)
    assert tts.available is False
    tts.speak("hello")          # must not raise
    tts.stop()
    tts.set_rate(180)
    tts.set_voice("x")
    assert tts.is_speaking() is False
    assert tts.get_available_voices() == []


def test_empty_text_does_not_start_thread():
    tts = TTSService(autostart=False)
    tts._engine = object()  # pretend an engine exists
    tts.speak("   ")
    assert tts.is_speaking() is False
