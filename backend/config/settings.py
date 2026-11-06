from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()


def required(name):
    value = env(name)
    if not value.strip():
        raise ImproperlyConfigured(f"{name} must not be empty")
    return value


SECRET_KEY = required("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
    "apps.assets.apps.AssetsConfig",
    "apps.members.apps.MembersConfig",
    "apps.content.apps.ContentConfig",
    "apps.workflow.apps.WorkflowConfig",
    "apps.ai_assistant.apps.AIAssistantConfig",
    "apps.analytics.apps.AnalyticsConfig",

]
MIDDLEWARE = [
    "apps.core.middleware.RequestContextMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required("POSTGRES_DB"),
        "USER": required("POSTGRES_USER"),
        "PASSWORD": required("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env.int("POSTGRES_PORT", default=5432),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 5},
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.VersionedSessionAuthentication"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_COOKIE_SECURE = env.bool("DJANGO_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "apps.accounts.views.csrf_failure"


def positive_int(name, default):
    value = env.int(name, default=default)
    if value <= 0:
        raise ImproperlyConfigured(f"{name} must be positive")
    return value


AUTH_LOGIN_WINDOW_SECONDS = positive_int("AUTH_LOGIN_WINDOW_SECONDS", 900)
AUTH_LOGIN_ACCOUNT_IP_LIMIT = positive_int("AUTH_LOGIN_ACCOUNT_IP_LIMIT", 10)
AUTH_LOGIN_IP_LIMIT = positive_int("AUTH_LOGIN_IP_LIMIT", 60)

# Private assets never live under the Nginx frontend root.
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 22 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 64

# V7: opt-in, official-provider-only AI. Missing prices fail closed at job creation.
AI_ENABLED = env.bool('AI_ENABLED', default=False)
AI_PROVIDER = env('AI_PROVIDER', default='deepseek')
DEEPSEEK_API_KEY = env('DEEPSEEK_API_KEY', default='')
DEEPSEEK_BASE_URL = env('DEEPSEEK_BASE_URL', default='https://api.deepseek.com')
DEEPSEEK_MODEL = env('DEEPSEEK_MODEL', default='deepseek-flash')
AI_CONNECT_TIMEOUT_SECONDS = positive_int('AI_CONNECT_TIMEOUT_SECONDS', 5)
AI_REQUEST_TIMEOUT_SECONDS = positive_int('AI_REQUEST_TIMEOUT_SECONDS', 60)
AI_MAX_RETRIES = env.int('AI_MAX_RETRIES', default=2)
AI_MAX_INPUT_TOKENS = positive_int('AI_MAX_INPUT_TOKENS', 24000)
AI_MAX_OUTPUT_TOKENS = positive_int('AI_MAX_OUTPUT_TOKENS', 4000)
AI_USER_DAILY_LIMIT = positive_int('AI_USER_DAILY_LIMIT', 10)
AI_GLOBAL_DAILY_LIMIT = positive_int('AI_GLOBAL_DAILY_LIMIT', 100)
AI_GLOBAL_DAILY_BUDGET_CNY = env('AI_GLOBAL_DAILY_BUDGET_CNY', default='10')
AI_PRICE_INPUT_CNY_PER_MILLION = env('AI_PRICE_INPUT_CNY_PER_MILLION', default='')
AI_PRICE_OUTPUT_CNY_PER_MILLION = env('AI_PRICE_OUTPUT_CNY_PER_MILLION', default='')
AI_PRICE_EFFECTIVE_DATE = env('AI_PRICE_EFFECTIVE_DATE', default='')
AI_SOURCE_RETENTION_DAYS = positive_int('AI_SOURCE_RETENTION_DAYS', 7)
AI_CANDIDATE_RETENTION_DAYS = positive_int('AI_CANDIDATE_RETENTION_DAYS', 30)
AI_LEASE_SECONDS = positive_int('AI_LEASE_SECONDS', 240)

# V9: forwarded headers are ignored unless REMOTE_ADDR belongs to this explicit trust boundary.
TRUSTED_PROXY_NETWORKS = env.list('TRUSTED_PROXY_NETWORKS', default=[])
CSRF_TRUSTED_ORIGINS = env.list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = env.bool('DJANGO_SSL_REDIRECT', default=False)
SECURE_HSTS_SECONDS = env.int('DJANGO_HSTS_SECONDS', default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https') if TRUSTED_PROXY_NETWORKS else None
LOGGING = {'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},'loggers':{'lab.requests':{'handlers':['console'],'level':'INFO','propagate':False}}}

FILE_SCAN_REQUIRED = env.bool('FILE_SCAN_REQUIRED', default=False)
CLAMAV_SOCKET = env('CLAMAV_SOCKET', default='')
