from types import SimpleNamespace
import pytest
from backend.scripts import imagery_detection_gateway as gateway


@pytest.mark.parametrize("body", [b"x"*(2*1024*1024+1), b"not JSON", b"[]", b'{"x":NaN}'])
def test_invalid_response_always_closes(body):
    closed=[]
    response=SimpleNamespace(status_code=200,iter_content=lambda **kw:iter([body]),close=lambda:closed.append(True))
    with pytest.raises(ValueError):
        gateway._provider_json(response)
    assert closed == [True]


def test_stream_stops_before_reading_tail_when_budget_exceeded():
    closed=[]
    def blocks(**kwargs):
        yield b"x"*(2*1024*1024+1)
        pytest.fail("Oversized response tail consumed")
    with pytest.raises(ValueError,match="resource budget"):
        gateway._provider_json(SimpleNamespace(status_code=200,iter_content=blocks,close=lambda:closed.append(True)))
    assert closed == [True]


def test_valid_stream_and_redirect_cleanup():
    for status in (200,307):
        closed=[]
        response=SimpleNamespace(status_code=status,iter_content=lambda **kw:iter([b'{"detections":',b'[]}']),close=lambda:closed.append(True))
        if status==200:
            assert gateway._provider_json(response) == {"detections":[]}
        else:
            with pytest.raises(ValueError,match="redirects"):
                gateway._provider_json(response)
        assert closed == [True]


def test_response_deadline(monkeypatch):
    clock=[0]
    monkeypatch.setattr(gateway.time,"monotonic",lambda:clock[0])
    closed=[]
    def blocks(**kwargs):
        clock[0]=21
        yield b"{}"
    with pytest.raises(ValueError,match="resource budget"):
        gateway._provider_json(SimpleNamespace(status_code=200,iter_content=blocks,close=lambda:closed.append(True)))
    assert closed == [True]
