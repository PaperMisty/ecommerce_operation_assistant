import httpx

# 全局复用的异步HTTP客户端连接池
_http_client: httpx.AsyncClient | None = None


async def init_http_pool() -> httpx.AsyncClient:
    """职责:初始化全局复用的异步HTTP连接池"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
    return _http_client


def get_http_client() -> httpx.AsyncClient:
    """职责:获取已初始化的全局异步HTTP连接池客户端"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
    return _http_client


async def close_http_pool() -> None:
    """职责:关闭全局异步HTTP连接池"""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
