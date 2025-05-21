from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required


def user_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Since your CustomUser uses email as USERNAME_FIELD, use it to authenticate.
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Successfully logged in.")
            return redirect("dashboard:index")  # Redirect to the dashboard after login.
        else:
            messages.error(request, "Invalid email or password.")
    return render(request, "users/login.html")


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful. You are now logged in!")
            return redirect("dashboard:index")
        else:
            # Optionally, you can log form errors here for debugging.
            messages.error(request, "Registration failed. Please fix the errors below.")
    else:
        form = CustomUserCreationForm()
    return render(request, "users/register.html", {"form": form})


def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("login")


@login_required
def account_settings(request):
    """
    A placeholder for a user "Account Settings" page.
    Let user update name, email, password, etc.
    """
    if request.method == "POST":
        # Example: update user’s info
        current_user = request.user
        new_username = request.POST.get("username")
        if new_username:
            current_user.username = new_username
            current_user.save()
            messages.success(request, "Account settings updated!")
        # etc...
        return redirect("users:account_settings")

    return render(request, "users/account_settings.html")
