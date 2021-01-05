import json

from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .tasks import sync_google_events, sync_outlook_events
from users.models import UserSocialAuth


@csrf_exempt
@require_http_methods(["POST"])
def google_web_hook(request):
    channel_id = request.headers.get('X-Goog-Channel-ID')
    if channel_id and UserSocialAuth.objects.filter(subscription_id=channel_id, provider='google-oauth2').exists():
        social = UserSocialAuth.objects.get(subscription_id=channel_id, provider='google-oauth2')
        sync_google_events.delay(social.pk)
        return HttpResponse()
    return HttpResponse()


@csrf_exempt
@require_http_methods(["POST"])
def outlook_web_hook(request):
    vt = request.GET.get('validationToken')
    if vt:
        return HttpResponse(vt)

    notifications = json.loads(request.body)

    for n in notifications['value']:
        subscription_id = n['subscriptionId']
        if UserSocialAuth.objects.filter(subscription_id=subscription_id, provider='microsoft-graph').exists():
            social = UserSocialAuth.objects.get(subscription_id=subscription_id, provider='microsoft-graph')
            sync_outlook_events.delay(social.pk)

    return HttpResponse()
