from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("subscription/", views.subscription, name="subscription"),
    # Add more payment-related URLs here if needed.
]
