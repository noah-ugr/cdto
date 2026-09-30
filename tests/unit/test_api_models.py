from core.api import ChatRequest, find_available_port


def test_chat_request_defaults() -> None:
    request = ChatRequest(message="hello")

    assert request.thread_id == "session_web_demo"
    assert request.include_episodic_memory is True


def test_find_available_port_returns_requested_port_when_free() -> None:
    port = find_available_port("127.0.0.1", 0, max_tries=1)

    assert isinstance(port, int)
