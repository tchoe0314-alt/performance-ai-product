from types import SimpleNamespace
import pytest
from backend.scripts.imagery_detection_gateway import _call_generic_detector, _call_roboflow


@pytest.mark.parametrize("provider", ["generic","roboflow_json","roboflow_url"])
@pytest.mark.parametrize("status", [301,302,303,307,308,401,500])
def test_provider_never_follows_or_parses_redirects(monkeypatch, provider, status):
    monkeypatch.setenv("CIVORA_GATEWAY_GENERIC_DETECTOR_URL","https://detector.example.test/")
    monkeypatch.setenv("ROBOFLOW_API_URL","https://detector.example.test/")
    monkeypatch.setenv("ROBOFLOW_API_KEY","synthetic-secret")
    monkeypatch.setenv("ROBOFLOW_IMAGE_MODE","json" if provider.endswith("json") else "url_param")
    calls=[]
    def post(url, **kwargs):
        calls.append(kwargs)
        assert kwargs["allow_redirects"] is False
        return SimpleNamespace(status_code=status,json=lambda:pytest.fail("Non-success body parsed"))
    session=SimpleNamespace(post=post)
    with pytest.raises(ValueError,match="redirects are not allowed"):
        if provider == "generic":
            _call_generic_detector(payload={},image_url="https://imagery.example.test/source.png",session=session)
        else:
            _call_roboflow(image_url="https://imagery.example.test/source.png",session=session)
    assert len(calls) == 1
