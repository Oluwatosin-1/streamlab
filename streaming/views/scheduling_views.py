from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden

from streaming.forms import ScheduledVideoForm
from streaming.models import ScheduledVideo 

# List all scheduled videos for the logged-in user.
class ScheduledVideoListView(LoginRequiredMixin, ListView):
    model = ScheduledVideo
    template_name = "streaming/list_scheduled_videos.html"
    context_object_name = "scheduled_videos"

    def get_queryset(self):
        return ScheduledVideo.objects.filter(user=self.request.user)


# Create a new scheduled video.
class ScheduledVideoCreateView(LoginRequiredMixin, CreateView):
    model = ScheduledVideo
    form_class = ScheduledVideoForm
    template_name = "streaming/create_scheduled_video.html"
    success_url = reverse_lazy("streaming:scheduled_video_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


# Update an existing scheduled video.
class ScheduledVideoUpdateView(LoginRequiredMixin, UpdateView):
    model = ScheduledVideo
    form_class = ScheduledVideoForm
    template_name = "streaming/update_scheduled_video.html"
    success_url = reverse_lazy("streaming:scheduled_video_list")

    def get_queryset(self):
        return ScheduledVideo.objects.filter(user=self.request.user)


# Delete a scheduled video.
class ScheduledVideoDeleteView(LoginRequiredMixin, DeleteView):
    model = ScheduledVideo
    template_name = "streaming/delete_scheduled_video.html"
    success_url = reverse_lazy("streaming:scheduled_video_list")

    def get_queryset(self):
        return ScheduledVideo.objects.filter(user=self.request.user)


# Publish a scheduled video, e.g., trigger its live broadcast.
def publish_scheduled_video(request, pk):
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You must be logged in.")
    scheduled = get_object_or_404(ScheduledVideo, pk=pk, user=request.user)
    
    # Optionally, trigger a Celery task to start streaming the scheduled video.
    # from .tasks import publish_scheduled_video_task
    # publish_scheduled_video_task.delay(scheduled.id)
    
    scheduled.is_published = True
    scheduled.save()
    return redirect("streaming:scheduled_video_list")
