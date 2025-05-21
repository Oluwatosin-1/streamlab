from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django import forms

from streaming.forms import ChatMessageForm
from streaming.models import ChatMessage, StreamingSession


@login_required
def chat_room(request, session_id):
    """
    Displays a chat room for a given streaming session. Users can view
    all chat messages and post new messages.
    """
    session = get_object_or_404(
        StreamingSession, id=session_id, configuration__user=request.user
    )

    # Get chat messages ordered by creation time.
    chat_messages = session.chat_messages.all().order_by("created_at")

    form = ChatMessageForm()
    if request.method == "POST":
        form = ChatMessageForm(request.POST)
        if form.is_valid():
            chat = form.save(commit=False)
            chat.user = request.user
            chat.streaming_session = session
            chat.created_at = timezone.now()
            chat.save()
            # After posting, redirect to the same chat room to clear the form.
            return redirect(reverse("streaming:session_chat", args=[session_id]))

    context = {
        "session": session,
        "chat_messages": chat_messages,
        "form": form,
    }
    return render(request, "streaming/chat_room.html", context)
