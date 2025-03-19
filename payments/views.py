import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import SubscriptionPlan, UserSubscription

stripe.api_key = settings.STRIPE_SECRET_KEY  # Ensure your STRIPE_SECRET_KEY is in your settings

@login_required
def subscription(request):
    if request.method == "POST":
        # Expecting a plan value such as 'free', 'basic', or 'pro'
        plan_name = request.POST.get("plan")
        try:
            subscription_plan = SubscriptionPlan.objects.get(name=plan_name)
        except SubscriptionPlan.DoesNotExist:
            messages.error(request, "Invalid subscription plan selected.")
            return redirect("payments:subscription")
        
        # Create a Stripe customer
        try:
            customer = stripe.Customer.create(
                email=request.user.email,
                name=request.user.username
            )
        except Exception as e:
            messages.error(request, "Error creating Stripe customer: " + str(e))
            return redirect("payments:subscription")
        
        # Map the plan to a Stripe Price ID (update these IDs to your real values)
        stripe_price_ids = {
            "free": "price_free_dummy",   # Typically free plans may not require a Stripe subscription
            "basic": "price_basic_dummy",
            "pro": "price_pro_dummy",
        }
        price_id = stripe_price_ids.get(plan_name)
        if not price_id:
            messages.error(request, "Subscription plan is not configured properly.")
            return redirect("payments:subscription")
        
        # Create a Stripe subscription
        try:
            stripe_subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": price_id}],
            )
        except Exception as e:
            messages.error(request, "Error creating Stripe subscription: " + str(e))
            return redirect("payments:subscription")
        
        # Update or create the UserSubscription record for the user
        user_subscription, created = UserSubscription.objects.get_or_create(user=request.user)
        user_subscription.plan = subscription_plan
        user_subscription.active = True
        # Optionally update other fields such as end_date based on your business logic
        user_subscription.save()
        
        messages.success(request, "Subscription updated successfully!")
        return redirect("dashboard:index")

    # For GET requests, display available plans
    subscription_plans = SubscriptionPlan.objects.all()
    context = {
        "subscription_plans": subscription_plans,
    }
    return render(request, "payments/subscription.html", context)
