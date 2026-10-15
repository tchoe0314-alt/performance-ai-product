"""Bounded public HTTPS GET with DNS validation and connection pinning.

No ambient proxy credentials/cookies, no private IPs, no unvalidated redirect hop.
Injected sessions are test doubles only; production uses the pinned stdlib transport.
"""
from dataclasses import dataclass
import http.client
import inspect
import ipaddress
import json
import math
import socket
import queue
import threading
import time
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

MAX_BYTES = 2 * 1024 * 1024
_DNS_SLOTS = threading.BoundedSemaphore(8)


class UnsafeDestination(ValueError):
    pass


def _bounded_lookup(host, timeout):
    """Bound DNS latency without accumulating unbounded blocked resolver threads.

    OS resolver calls cannot be cancelled safely. A timed-out daemon keeps its
    slot until it finishes; saturation fails closed instead of spawning more.
    """
    if timeout <= 0 or not _DNS_SLOTS.acquire(blocking=False):
        raise TimeoutError("DNS request budget unavailable.")
    result = queue.Queue(maxsize=1)

    def resolve():
        try:
            result.put((socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM), None))
        except Exception as exc:
            result.put((None, exc))
        finally:
            _DNS_SLOTS.release()

    try:
        threading.Thread(target=resolve, daemon=True, name="civora-public-dns").start()
    except Exception:
        _DNS_SLOTS.release()
        raise
    try:
        addresses, error = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError("DNS resolution deadline exceeded.") from exc
    if error is not None:
        raise error
    return addresses


def _public_address(address):
    value = ipaddress.ip_address(address)
    # Reject transition mechanisms that may encapsulate otherwise private
    # destinations, not just direct RFC1918/link-local address literals.
    if isinstance(value, ipaddress.IPv6Address):
        if value.sixtofour is not None or value.teredo is not None:
            return False
        if value in ipaddress.ip_network("64:ff9b::/96") or value in ipaddress.ip_network("64:ff9b:1::/48"):
            return False
        if value.ipv4_mapped is not None:
            return value.ipv4_mapped.is_global
    return value.is_global


def validate_destination(url, *, resolver=None, dns_timeout=10):
    if len(str(url)) > 4096:
        raise UnsafeDestination("Destination URL is too long.")
    parsed = urlsplit(str(url))
    if any(ord(char) <= 32 or ord(char) == 127 for char in str(url)):
        raise UnsafeDestination("Control characters and whitespace are not allowed in URLs.")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise UnsafeDestination("Only public HTTPS URLs without credentials/fragments are allowed.")
    if parsed.port not in (None,443):
        raise UnsafeDestination("Only the HTTPS service port is allowed.")
    host = parsed.hostname.rstrip(".").encode("idna").decode("ascii")
    if host in {"localhost","metadata.google.internal"} or host.endswith((".localhost",".local",".internal")):
        raise UnsafeDestination("Private/internal destinations are not allowed.")
    try:
        addresses=[str(ipaddress.ip_address(host))]
    except ValueError:
        rows = resolver(host,443,type=socket.SOCK_STREAM) if resolver is not None else _bounded_lookup(host, dns_timeout)
        addresses=list(dict.fromkeys(row[4][0] for row in rows))
    if not addresses or any(not _public_address(address) for address in addresses):
        raise UnsafeDestination("Destination must resolve exclusively to public addresses.")
    return parsed,host,addresses


@dataclass
class SafeResponse:
    status_code: int
    content: bytes
    headers: dict

    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise ValueError(f"Upstream returned HTTP {self.status_code}.")

    def json(self):
        return json.loads(self.content)


def safe_get(url, *, params=None, timeout=10, session=None, resolver=None):
    """Return a small requests-compatible response; each HTTPS connect pins IP.

    `session` is solely a fake-transport seam for offline tests. It must not be
    a real requests module/session (which would re-resolve and allow rebinding).
    """
    if session is not None and (getattr(session,"__name__","")=="requests" or type(session).__module__.startswith("requests")):
        raise UnsafeDestination("Real requests transports are not permitted; use the pinned transport.")
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be positive.")
    fake_url=url
    if params:
        parsed=urlsplit(url)
        url=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,parsed.query+("&" if parsed.query else "")+urlencode(params,doseq=True),""))
    deadline=time.monotonic()+min(timeout,20)
    for hop in range(4):
        effective_resolver = resolver
        if session is not None and effective_resolver is None:
            # An explicit fake session must remain fully offline. Literal/private
            # hosts are still rejected. Real production transports cannot enter
            # this branch; DNS/rebinding tests supply an explicit fake resolver.
            effective_resolver = lambda *a, **k: [(socket.AF_INET,socket.SOCK_STREAM,6,"",("93.184.216.34",443))]
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Upstream request deadline exceeded.")
        parsed,host,addresses=validate_destination(url,resolver=effective_resolver,dns_timeout=remaining)
        if session is not None:
            kwargs={"params":params,"timeout":min(timeout,20),"allow_redirects":False,"stream":True}
            signature=inspect.signature(session.get)
            if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
                kwargs={key:value for key,value in kwargs.items() if key in signature.parameters}
            response=session.get(fake_url,**kwargs)
            response.raise_for_status()
            # A fake JSON response is bounded too; no external session is used.
            payload=json.dumps(response.json(),allow_nan=False).encode()
            if len(payload)>MAX_BYTES:raise ValueError("Upstream response is too large.")
            return SafeResponse(200,payload,{})
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError("Upstream request deadline exceeded.")
        connection=http.client.HTTPSConnection(host,timeout=remaining)
        # Preserve TLS SNI/certificate validation for host, but never resolve host
        # again during connect. The exact previously validated IP is used.
        connection._create_connection=lambda address,timeout=None,source_address=None: socket.create_connection((addresses[0],443),timeout,source_address)
        try:
            path=urlunsplit(("","",parsed.path or "/",parsed.query,""))
            connection.request("GET",path,headers={"Accept":"application/json","Accept-Encoding":"identity","User-Agent":"Civora-GIS/1"})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader("Location")
                if not location or hop==3:raise UnsafeDestination("Invalid or excessive upstream redirects.")
                url=urljoin(url,location)
                continue
            if response.getheader("Content-Encoding", "identity").lower() not in ("identity",""):
                raise ValueError("Compressed upstream responses are not supported by the bounded GIS client.")
            length=response.getheader("Content-Length")
            if length is not None and int(length)>MAX_BYTES:
                raise ValueError("Upstream response is too large.")
            chunks=[];total=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError("Upstream response deadline exceeded.")
                if connection.sock is not None:connection.sock.settimeout(remaining)
                block=response.read1(min(65536,MAX_BYTES+1-total))
                if not block:break
                total+=len(block)
                if total>MAX_BYTES:raise ValueError("Upstream response is too large.")
                chunks.append(block)
            content=b"".join(chunks)
            return SafeResponse(response.status,content,dict(response.getheaders()))
        finally:
            connection.close()
    raise UnsafeDestination("Upstream redirect limit exceeded.")
