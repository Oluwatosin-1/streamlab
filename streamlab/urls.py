from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
 
 
urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),  
    path("dashboard/", include("dashboard.urls")),
    path('', TemplateView.as_view(template_name="home.html"), name='home'),
    path("streaming/", include("streaming.urls", namespace="streaming")),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path('accounts/', include('allauth.urls')),
]

# Add static files support in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
