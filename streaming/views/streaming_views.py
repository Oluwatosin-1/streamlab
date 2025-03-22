from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseForbidden
from django.utils import timezone

from streaming.forms import StreamingConfigurationForm
from streaming.models import StreamingConfiguration, StreamingSession
 
# List all streaming configurations for the logged-in user.
class StreamingConfigurationListView(LoginRequiredMixin, ListView):
    model = StreamingConfiguration
    template_name = "streaming/config_list.html"
    context_object_name = "configurations"

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)


# Create a new streaming configuration.
class StreamingConfigurationCreateView(LoginRequiredMixin, CreateView):
    model = StreamingConfiguration
    form_class = StreamingConfigurationForm
    template_name = "streaming/create_rtmp_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


# Update an existing streaming configuration.
class StreamingConfigurationUpdateView(LoginRequiredMixin, UpdateView):
    model = StreamingConfiguration
    form_class = StreamingConfigurationForm
    template_name = "streaming/update_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def get_queryset(self):
        # Ensure the user can only update his/her own configurations.
        return StreamingConfiguration.objects.filter(user=self.request.user)


# Delete a streaming configuration.
class StreamingConfigurationDeleteView(LoginRequiredMixin, DeleteView):
    model = StreamingConfiguration
    template_name = "streaming/delete_config.html"
    success_url = reverse_lazy("streaming:config_list")

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)


# Display detailed information for a specific streaming configuration.
class StreamingConfigurationDetailView(LoginRequiredMixin, DetailView):
    model = StreamingConfiguration
    template_name = "streaming/detail_config.html"
    context_object_name = "configuration"

    def get_queryset(self):
        return StreamingConfiguration.objects.filter(user=self.request.user)


# Start a live streaming session for a given configuration.
def start_streaming_session(request, pk):
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You must be logged in.")
    config = get_object_or_404(StreamingConfiguration, pk=pk, user=request.user)

    # Create a new streaming session (status defaults to 'live').
    session = StreamingSession.objects.create(configuration=config, status="live")
    
    # Optionally, call a Celery task to trigger external API calls for going live.
    # from .tasks import start_stream_task
    # start_stream_task.delay(session.id)

    return redirect("streaming:session_detail", session_id=session.id)


# End an ongoing streaming session.
def end_streaming_session(request, session_id):
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You must be logged in.")
    session = get_object_or_404(StreamingSession, id=session_id, configuration__user=request.user)
    
    if session.status != "live":
        # Only live sessions can be ended.
        return redirect("streaming:session_detail", session_id=session.id)
    
    session.status = "ended"
    session.session_end = timezone.now()
    session.save()
    
    # Optionally, call a Celery task to stop external streaming.
    # from .tasks import stop_stream_task
    # stop_stream_task.delay(session.id)
    
    return redirect("streaming:session_detail", session_id=session.id)


# Detail view for a streaming session.
class StreamingSessionDetailView(LoginRequiredMixin, DetailView):
    model = StreamingSession
    template_name = "streaming/session_detail.html"
    context_object_name = "session"
    pk_url_kwarg = "session_id"

    def get_queryset(self):
        return StreamingSession.objects.filter(configuration__user=self.request.user)
