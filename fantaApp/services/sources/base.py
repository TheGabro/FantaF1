import requests
import time

# ── Simple module‑level rate‑limiter ────────────────────────────────────
_RATE_LIMIT_SEC = 2.0  # stay conservative with Jolpica and OpenF1 rate limits
_last_call_ts = 0.0  # perf_counter timestamp of last call


class ResultsNotAvailable(Exception):
    """Sollevata quando la sessione richiesta non ha ancora risultati pubblicati dall'API."""


def rate_limited_get(url: str, max_retries: int = 5, **kwargs):
    """
    Wrapper attorno a requests.get che assicura di non superare il rate limit.
    Include retry automatico con backoff esponenziale per errori 429.
    """
    global _last_call_ts

    for attempt in range(max_retries):
        now = time.perf_counter()
        elapsed = now - _last_call_ts
        if elapsed < _RATE_LIMIT_SEC:
            time.sleep(_RATE_LIMIT_SEC - elapsed)

        try:
            response = requests.get(url, **kwargs)
            _last_call_ts = time.perf_counter()

            # Se riceviamo 429, aspetta e riprova
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = int(retry_after) if retry_after else (2**attempt) * 4
                    print(
                        f"429 Too Many Requests. Attendo {wait_time}s prima di riprovare..."
                    )
                    time.sleep(wait_time)
                    continue

            return response

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = (2**attempt) * 2
                print(f"Errore: {e}. Riprovo tra {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise

    return response
