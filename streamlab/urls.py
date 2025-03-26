from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LogoutView 

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("streaming/", include("streaming.urls", namespace="streaming")),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("payments/", include("payments.urls", namespace="payments")), 
]
