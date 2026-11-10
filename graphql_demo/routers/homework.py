from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.head("/foo")
async def head_foo() -> Response:
    return Response(status_code=200)


@router.get("/homework-ui", response_class=HTMLResponse)
async def homework_ui() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>CORS HEAD Request Homework</title>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="flex min-h-screen items-center justify-center bg-slate-100 p-6 text-slate-800">
        <main class="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h1 class="text-xl font-bold">CORS method restriction</h1>
          <p class="mt-2 text-sm text-slate-600">
            Send a HEAD request with a custom header. The browser preflight is
            expected to be rejected because HEAD is not in the CORS method allowlist.
          </p>
          <button id="test-request"
                  class="mt-6 w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700">
            Test HEAD /foo
          </button>
          <pre id="output" role="status" aria-live="polite"
               class="mt-4 min-h-24 whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">Click the button to test.</pre>
        </main>
        <script>
          const button = document.getElementById('test-request');
          const output = document.getElementById('output');

          function getCrossOriginFooUrl() {
            const url = new URL('/foo', window.location.origin);
            if (url.hostname === 'localhost') {
              url.hostname = '127.0.0.1';
            } else if (url.hostname === '127.0.0.1') {
              url.hostname = 'localhost';
            }
            return url.toString();
          }

          button.addEventListener('click', async () => {
            output.className = 'mt-4 min-h-24 whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm';
            output.textContent = 'Sending HEAD /foo with a custom header...';
            try {
              const response = await fetch(getCrossOriginFooUrl(), {
                method: 'HEAD',
                headers: { 'X-CORS-Test': 'trigger-preflight' }
              });
              output.textContent = response.ok
                ? 'Request succeeded with status ' + response.status + '.'
                : 'Request failed with status ' + response.status + '.';
              output.className += response.ok
                ? ' border-emerald-200 bg-emerald-50 text-emerald-800'
                : ' border-rose-200 bg-rose-50 text-rose-800';
            } catch (error) {
              output.textContent = 'CORS / network error: ' + error.message +
                '\\nThe browser blocked the request. The CORS policy does not allow HEAD.';
              output.className += ' border-rose-200 bg-rose-50 text-rose-800';
            }
          });
        </script>
      </body>
    </html>
    """
