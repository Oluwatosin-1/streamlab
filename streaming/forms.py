# streaming/forms.py
from django import forms
from .models import (
    ChatMessage,
    StreamingConfiguration,
    ScheduledVideo,
    StreamingPlatformAccount,
)


class SocialAccountForm(forms.ModelForm):
    class Meta:
        model = StreamingPlatformAccount
        # Only include the fields the user should manually input.
        fields = ["platform", "display_name", "rtmp_url", "stream_key"]
        widgets = {
            # Hide the platform field if you want to pre-set it from the URL/view.
            "platform": forms.HiddenInput(),
        }


class StreamingConfigurationForm(forms.ModelForm):
    class Meta:
        model = StreamingConfiguration
        fields = [
            "stream_title",
            "description",
            "rtmp_url",
            "stream_key",
            "backup_rtmp_url",
            "backup_stream_key",
            "pull_links",
            "embed_player_url",
            "embed_chat_url",
            "resolution",
            "bitrate",
            "is_active",
        ]


class ScheduledVideoForm(forms.ModelForm):
    class Meta:
        model = ScheduledVideo
        fields = ["title", "video_file", "scheduled_time", "description"]


class RecordingForm(forms.Form):
    title = forms.CharField(max_length=200, required=True)
    notes = forms.CharField(
        widget=forms.Textarea,
        required=False,
        help_text="Any extra notes for this recording.",
    )


# A simple ModelForm for posting chat messages.
class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ["text"]
