"""
Minimal self-contained Django example.

Run:
    python examples/integrations/django_app.py
"""

import sys

import django
from django.conf import settings
from django.http import HttpResponse
from django.urls import path

SECRET = "change-me-to-a-real-32-byte-key!"

settings.configure(
    DEBUG=True,
    SECRET_KEY=SECRET,
    ALLOWED_HOSTS=["*"],
    ROOT_URLCONF=__name__,
    MIDDLEWARE=[
        "tollbooth.integrations.django.TollboothMiddleware",
    ],
    TOLLBOOTH={
        "rules": [{"name": "everyone", "action": "challenge"}],
    },
)

django.setup()

from tollbooth import Rule
from tollbooth.integrations.django import (
    make_verify_view,
    tollbooth_exempt,
    tollbooth_protect,
)

_tb_rules = [Rule(name="everyone", action="challenge")]


def index(request):
    return HttpResponse("Hello from upstream!")


@tollbooth_exempt
def open_route(request):
    return HttpResponse("No challenge here")


@tollbooth_protect(SECRET, rules=_tb_rules)
def protected(request):
    return HttpResponse("Per-route protection")


urlpatterns = [
    path("", index),
    path("open/", open_route),
    path("protected/", protected),
    path("verify/", make_verify_view(SECRET, rules=_tb_rules)),
]

if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], "runserver", "8000"])
