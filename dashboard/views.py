from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from dashboard.models import DashboardSettings
from streaming.models import StreamingConfiguration, StreamingSession
from payments.models import UserSubscription

@login_required
def dashboard(request):
    # "All" tab: display all streaming configurations & sessions
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    streaming_configs = StreamingConfiguration.objects.filter(user=request.user)
    streaming_sessions = StreamingSession.objects.filter(configuration__user=request.user).order_by('-session_start')
    try:
        user_subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        user_subscription = None

    metrics = {
        'views': '+24K',
        'rated_app': '+55K',
        'downloads': '+1M',
        'visitors': '+2M',
    }
    
    context = {
        'dashboard_settings': dashboard_settings,
        'streaming_configs': streaming_configs,
        'streaming_sessions': streaming_sessions,
        'metrics': metrics,
        'user_subscription': user_subscription,
        'active_tab': 'all',
    }
    return render(request, "dashboard/index.html", context)

@login_required
def dashboard_drafts(request):
    # "Drafts" tab: for example, non-active streaming configurations can be considered drafts.
    drafts = StreamingConfiguration.objects.filter(user=request.user, is_active=False)
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    try:
        user_subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        user_subscription = None

    metrics = {
        'views': '+24K',
        'rated_app': '+55K',
        'downloads': '+1M',
        'visitors': '+2M',
    }
    
    context = {
        'drafts': drafts,
        'dashboard_settings': dashboard_settings,
        'metrics': metrics,
        'user_subscription': user_subscription,
        'active_tab': 'drafts',
    }
    return render(request, "dashboard/index.html", context)

@login_required
def dashboard_scheduled(request):
    # "Scheduled" tab: if you have scheduled streams, fetch them here.
    # For now, we'll use an empty list as a placeholder.
    scheduled = []
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    try:
        user_subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        user_subscription = None

    metrics = {
        'views': '+24K',
        'rated_app': '+55K',
        'downloads': '+1M',
        'visitors': '+2M',
    }
    
    context = {
        'scheduled': scheduled,
        'dashboard_settings': dashboard_settings,
        'metrics': metrics,
        'user_subscription': user_subscription,
        'active_tab': 'scheduled',
    }
    return render(request, "dashboard/index.html", context)

@login_required
def past_streams(request):
    # Example logic for retrieving ended streams
    ended_streams = StreamingSession.objects.filter(
        configuration__user=request.user,
        status='ended'
    ).order_by('-session_end')

    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    try:
        user_subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        user_subscription = None

    metrics = {
        'views': '+24K',
        'rated_app': '+55K',
        'downloads': '+1M',
        'visitors': '+2M',
    }

    context = {
        'ended_streams': ended_streams,
        'dashboard_settings': dashboard_settings,
        'user_subscription': user_subscription,
        'metrics': metrics,
        'active_tab': 'past_streams',
    }
    return render(request, "dashboard/past_streams.html", context)


@login_required
def dashboard_settings(request):
    """
    Displays or updates user-specific dashboard settings.
    """
    # Fetch or create the user's DashboardSettings entry
    dash_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        # For example, update the theme, notifications, etc.
        new_theme = request.POST.get("theme")
        new_notifications = request.POST.get("notifications_enabled") == "on"
        dash_settings.theme = new_theme if new_theme else dash_settings.theme
        dash_settings.notifications_enabled = new_notifications
        dash_settings.save()
        
        # Possibly show a success message
        # messages.success(request, "Dashboard settings updated!")
        return render(request, "dashboard/settings.html", {"dashboard_settings": dash_settings})
    
    # If GET, just display the existing settings
    return render(request, "dashboard/settings.html", {"dashboard_settings": dash_settings})