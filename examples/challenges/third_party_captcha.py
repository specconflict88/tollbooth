"""Third-party CAPTCHA challenge — delegates to an external provider.

Usage:
    python examples/challenges/third_party_captcha.py recaptcha
    python examples/challenges/third_party_captcha.py hcaptcha
    python examples/challenges/third_party_captcha.py turnstile
    python examples/challenges/third_party_captcha.py friendly
    python examples/challenges/third_party_captcha.py captchafox
    python examples/challenges/third_party_captcha.py mtcaptcha
    python examples/challenges/third_party_captcha.py arkose
    python examples/challenges/third_party_captcha.py geetest
    python examples/challenges/third_party_captcha.py altcha
"""

import sys
from collections.abc import Iterable
from typing import Any
from wsgiref.simple_server import make_server

from tollbooth import (
    AltchaCreds,
    CaptchaCreds,
    Rule,
    ThirdPartyCaptchaChallenge,
    TollboothWSGI,
)

SECRET = "change-me-to-a-real-32-byte-key!"
RULES = [Rule(name="everyone", action="challenge")]

PROVIDERS: dict[str, CaptchaCreds | AltchaCreds] = {
    "recaptcha": CaptchaCreds(
        site_key="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI",  # Google test key
        secret_key="6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe",  # Google test secret
    ),
    "hcaptcha": CaptchaCreds(
        site_key="10000000-ffff-ffff-ffff-000000000001",  # hCaptcha test key
        secret_key="0x0000000000000000000000000000000000000000",  # hCaptcha test secret
    ),
    "turnstile": CaptchaCreds(
        site_key="1x00000000000000000000AA",  # Cloudflare always-passes test key
        secret_key="1x0000000000000000000000000000000AA",
    ),
    "friendly": CaptchaCreds(
        site_key="FCMGEMKGEIMH",  # Replace with real key
        secret_key="your-friendly-secret",
    ),
    "captchafox": CaptchaCreds(
        site_key="yfSzboYwBEAztLSBbPsE",  # Replace with real key
        secret_key="your-captchafox-secret",
    ),
    "mtcaptcha": CaptchaCreds(
        site_key="MTPublic-KZi6oZAuj",  # MTCaptcha demo key
        secret_key="MTSecretKey_demo",
    ),
    "arkose": CaptchaCreds(
        site_key="DF9C4D87-CB7B-4062-9FEB-BADB6ADA61E6",  # Replace with real key
        secret_key="your-arkose-secret",
    ),
    "geetest": CaptchaCreds(
        site_key="your-geetest-captcha-id",  # Replace with real key
        secret_key="your-geetest-secret",
    ),
    "altcha": AltchaCreds(
        secret_key="altcha-local-secret",  # Any string — self-hosted, no account needed
    ),
}


def app(_environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Hello from upstream!"]


if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "recaptcha"
    if provider not in PROVIDERS:
        print(f"Unknown provider: {provider}")
        print(f"Available: {', '.join(PROVIDERS)}")
        sys.exit(1)

    handler = ThirdPartyCaptchaChallenge(
        provider=provider,
        creds=PROVIDERS[provider],
        language="auto",
        theme="auto",
    )
    wrapped = TollboothWSGI(app, SECRET, rules=RULES, challenge_handler=handler)
    print(f"ThirdPartyCaptchaChallenge ({provider}) on http://localhost:8000")
    make_server("0.0.0.0", 8000, wrapped).serve_forever()
