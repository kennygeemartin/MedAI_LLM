"""Temporary maintenance gate. Delete this file and redeploy to restore service."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Temporarily unavailable</title>
<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f8fa;color:#132d46;font-family:Arial,sans-serif}
main{padding:2rem;text-align:center}h1{font-size:clamp(1.8rem,5vw,3rem)}p{color:#506579}
</style>
</head>
<body><main><h1>Temporarily unavailable</h1><p>Please try again later.</p></main></body>
</html>"""

@app.middleware("http")
async def maintenance(request, call_next):
    # Intercept every path and HTTP method before routing or application work.
    return HTMLResponse(
        content="" if request.method == "HEAD" else PAGE,
        status_code=503,
        headers={"Cache-Control": "no-store", "Retry-After": "3600"},
    )
