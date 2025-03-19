# payments/models.py

from django.db import models
from django.conf import settings

class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
    ]
    name = models.CharField(
        max_length=50, 
        choices=PLAN_CHOICES, 
        unique=True,
        help_text="Name of the subscription plan"
    )
    price = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0.00, 
        help_text="Price of the plan (free plans can be 0.00)"
    )
    duration_days = models.PositiveIntegerField(
        help_text="Duration of the plan in days", 
        default=30
    )
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.get_name_display()

class UserSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=False)
    auto_renew = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan}"

class Invoice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='invoices'
    )
    subscription = models.ForeignKey(
        UserSubscription, 
        on_delete=models.CASCADE, 
        related_name='invoices'
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    issued_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    paid = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Invoice #{self.id} for {self.user.username}"

class PaymentTransaction(models.Model):
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    transaction_reference = models.CharField(max_length=255)
    status = models.CharField(
        max_length=50, 
        choices=[('success', 'Success'), ('failed', 'Failed')],
        help_text="Status of the transaction"
    )

    def __str__(self):
        return f"Transaction {self.transaction_reference} - {self.status}"
