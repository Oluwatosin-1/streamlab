from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from dashboard.models import DashboardSettings
from streaming.models import StreamingConfiguration, StreamingPlatformAccount, StreamingSession
import json
from django.http import JsonResponse
from streaming.srs_utils import get_stream_stats 

@login_required
def dashboard(request):
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
    streaming_configs = StreamingConfiguration.objects.filter(user=request.user)
    streaming_sessions = StreamingSession.objects.filter(configuration__user=request.user).order_by('-session_start')
  
    # Check if the user has at least one active connected social account.
    social_connected = request.user.streaming_platform_accounts.filter(is_active=True).exists()

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
        'social_connected': social_connected,
        'metrics': metrics, 
        'active_tab': 'all',
    }
    return render(request, "dashboard/index.html", context)

@login_required
def dashboard_drafts(request):
    # "Drafts" tab: for example, non-active streaming configurations can be considered drafts.
    drafts = StreamingConfiguration.objects.filter(user=request.user, is_active=False)
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
 
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
        'active_tab': 'drafts',
    }
    return render(request, "dashboard/index.html", context)

@login_required
def dashboard_scheduled(request):
    # "Scheduled" tab: if you have scheduled streams, fetch them here.
    # For now, we'll use an empty list as a placeholder.
    scheduled = []
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
 
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
 
    metrics = {
        'views': '+24K',
        'rated_app': '+55K',
        'downloads': '+1M',
        'visitors': '+2M',
    }

    context = {
        'ended_streams': ended_streams,
        'dashboard_settings': dashboard_settings, 
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


# NEW: Video Storage
@login_required
def video_storage(request):
    """
    Example placeholder for 'Video Storage' page. 
    You might list user-uploaded or recorded videos stored on your platform.
    """
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
 
    context = {
        'dashboard_settings': dashboard_settings, 
    }
    return render(request, "dashboard/video_storage.html", context)

# NEW: Analytics
@login_required
def analytics(request):
    """
    Example 'Analytics' page. Replace with real logic if you track viewer metrics, etc.
    """
    dashboard_settings, _ = DashboardSettings.objects.get_or_create(user=request.user)
 
    # Example metrics
    context = {
        'dashboard_settings': dashboard_settings, 
        'some_analytics_data': {...}  # Replace with real data
    }
    return render(request, "dashboard/analytics.html", context)
 
@login_required
def relay_monitor(request):
    # Fetch latest live session (or filter by param)
    session = StreamingSession.objects.filter(configuration__user=request.user, status="live").order_by('-session_start').first()
    if not session:
        return render(request, "streaming/relay_monitor.html", {"relay_statuses": [], "session": None})

    relay_statuses = session.relay_statuses.all()

    return render(request, "streaming/relay_monitor.html", {
        "relay_statuses": relay_statuses,
        "session": session
    })


@login_required
def stream_health(request):
    # Assume the active configuration is used.
    config = request.user.streaming_configurations.filter(is_active=True).first()
    if not config:
        return JsonResponse({"error": "No active configuration"}, status=404)
    stats = get_stream_stats("live", config.stream_key)
    if stats:
        return JsonResponse({"status": "ok", "stats": stats})
    return JsonResponse({"error": "Failed to retrieve stream stats"}, status=500)

def check_stream_status(request, stream_key):
    app = "live"
    stats = get_stream_stats(app, stream_key)

    session = StreamingSession.objects.filter(configuration__stream_key=stream_key, status="live").first()
    relay_stats = []
    if session:
        for relay in session.relay_statuses.all():
            relay_stats.append({
                "platform": relay.platform,
                "status": relay.status,
                "log_summary": relay.log_summary,
                "last_attempted": relay.last_attempted.strftime("%Y-%m-%d %H:%M:%S")
            })

    return JsonResponse({
        "srs_stats": stats,
        "relay_stats": relay_stats
    })
