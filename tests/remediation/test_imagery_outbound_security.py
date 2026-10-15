from types import SimpleNamespace
import pytest
from backend.scripts.imagery_detection_gateway import _fetch_image
from backend.services.outbound_http import safe_get


def test_legacy_private_override_cannot_bypass_pinned_transport(monkeypatch):
    monkeypatch.setenv("CIVORA_GATEWAY_ALLOW_PRIVATE_IMAGE_URLS","true")
    class Unexpected:
        def get(self,*args,**kwargs):
            pytest.fail("Private image destination reached transport")
    with pytest.raises(ValueError):
        _fetch_image(image_url="https://127.0.0.1/image.png",session=Unexpected())


def test_destination_policy_runs_before_transport():
    calls=[]
    def policy(url):
        calls.append(url)
        raise ValueError("Disallowed provider")
    session=SimpleNamespace(get=lambda *a,**kw:pytest.fail("Policy bypassed"))
    with pytest.raises(ValueError,match="Disallowed provider"):
        safe_get("https://example.test/image",session=session,response_kind="binary",destination_policy=policy)
    assert calls == ["https://example.test/image"]


@pytest.mark.parametrize("budget", [True,0,-1,15*1024*1024+1])
def test_unbounded_or_invalid_download_budget_rejected(budget):
    with pytest.raises(ValueError,match="byte budget"):
        safe_get("https://example.test/image",max_bytes=budget)
