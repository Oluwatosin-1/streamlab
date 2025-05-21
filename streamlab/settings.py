# settings.py

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-3!w*)^=uxe1qgvw^1ce94p@+42&#gefr6sfbva1!q=bx57zr@u"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*", "streaming.obairawoengineering.com", "localhost", ""]
# ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",  # API Framework
    "corsheaders",  # Cross-Origin Resource Sharing (for frontend)
    "rest_framework_simplejwt",  # JWT Authentication
    "users",  # User Authentication & Subscription
    "streaming",  # RTMP Streaming & Social Connection
    "dashboard",  # User Dashboard Integration
    "whitenoise",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # Add the providers you need:
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.twitch",
    "allauth.socialaccount.providers.instagram",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # <-- Required for allauth
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

# Allauth settings (adjust as needed)
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_EMAIL_VERIFICATION = "optional"

ROOT_URLCONF = "streamlab.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "streamlab.wsgi.application"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Database Setup
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'streamlab_db',
#         'USER': 'streamlab_user',
#         'PASSWORD': 'securepassword',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# Authentication Settings
AUTH_USER_MODEL = "users.CustomUser"
# settings.py
LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/"  # or any URL you want users to be redirected after login
SOCIALACCOUNT_ADAPTER = "streaming.allauth_adapter.CustomSocialAccountAdapter"

# REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}
# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
# DEFAULT_PROFILE_PICTURE = "default.png"

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SRS_SERVER_HOST = "localhost"  # or your SRS server domain/IP if different
SRS_API_PORT = 1985
# settings.py
CELERY_BROKER_URL = "redis://streamlab_redis:6379/0"
CELERY_RESULT_BACKEND = "redis://streamlab_redis:6379/0"
# CELERY_RESULT_BACKEND = 'redis://localhost:8000:6379/0'
# CELERY_BROKER_URL = 'redis://localhost:8000:6379/0'

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Set session to expire in 30 minutes (1800 seconds)
SESSION_COOKIE_AGE = 1800  # 30 minutes
# Ensure session expires when the browser is closed
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Enable database-backed session storage (Ensure you run migrations)
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    "https://stream.obairawoengineering.com",
    "https://www.stream.obairawoengineering.com",
]

# Social Auth configuration for each provider:
# --- YouTube (via Google OAuth2) ---
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = (
    "1003940566003-iipma78ri37njgi9c2h8gekp2m8rc9i4.apps.googleusercontent.com"
)
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = "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"


# Django CACHES configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_CACHE_URL", "redis://streamlab_redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "streaming": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
