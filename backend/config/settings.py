import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DJANGO_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-only-not-for-production" if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false")

ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
if not DEBUG and not os.getenv("DJANGO_ALLOWED_HOSTS"):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG is false")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "shop.apps.ShopConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"

POSTGRES_DB_HOST = os.getenv("POSTGRES_DB_HOST", "").strip()
if POSTGRES_DB_HOST:
    required_postgres_settings = ("POSTGRES_DB_NAME", "POSTGRES_DB_USER", "POSTGRES_DB_PASSWORD")
    missing_postgres_settings = [name for name in required_postgres_settings if not os.getenv(name)]
    if missing_postgres_settings:
        raise ImproperlyConfigured(
            "Set POSTGRES_DB_NAME, POSTGRES_DB_USER, and POSTGRES_DB_PASSWORD when POSTGRES_DB_HOST is configured"
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB_NAME"],
            "USER": os.environ["POSTGRES_DB_USER"],
            "PASSWORD": os.environ["POSTGRES_DB_PASSWORD"],
            "HOST": os.environ["POSTGRES_DB_HOST"],
            "PORT": os.getenv("POSTGRES_DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("DJANGO_SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        }
    }
else:
    raise ImproperlyConfigured("Set POSTGRES_DB_HOST, POSTGRES_DB_NAME, POSTGRES_DB_USER, and POSTGRES_DB_PASSWORD for PostgreSQL")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = os.getenv(
    "DJANGO_SECURE_SSL_REDIRECT", "0" if DEBUG else "1"
).strip().lower() in {"1", "true", "yes", "on"}
if os.getenv("DJANGO_BEHIND_PROXY", "0").strip().lower() in {"1", "true", "yes", "on"}:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
