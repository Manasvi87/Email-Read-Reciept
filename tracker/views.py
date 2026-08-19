import json
import base64
import uuid as uuid_lib

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import TrackedEmail, EmailOpen

# A 1x1 transparent PNG, held in memory — this is the entire tracking pixel.
PIXEL = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
    '42YAAAAASUVORK5CYII='
)

@ensure_csrf_cookie
def dashboard(request):
    return render(request, 'tracker/dashboard.html')


# NOTE: @csrf_exempt is used here because this is a prototype with no auth —
# the dashboard's fetch() calls don't carry a CSRF token. Before this touches
# real users, swap this for either proper CSRF-token handling in app.js or a
# real authenticated API layer.

@require_http_methods(['GET', 'POST', 'DELETE'])
def api_emails(request):
    if request.method == 'GET':
        emails = TrackedEmail.objects.prefetch_related('opens').all()
        return JsonResponse([e.to_dict() for e in emails], safe=False)

    if request.method == 'DELETE':
        TrackedEmail.objects.all().delete()
        return HttpResponse(status=204)

    # POST — create a new tracked email
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest(
            json.dumps({'error': 'Invalid JSON.'}), content_type='application/json'
        )

    recipient = (payload.get('recipient') or '').strip()
    subject = (payload.get('subject') or '').strip()

    try:
        validate_email(recipient)
    except ValidationError:
        return JsonResponse({'error': 'Enter a valid recipient email.'}, status=400)

    email = TrackedEmail.objects.create(recipient=recipient, subject=subject)
    return JsonResponse(email.to_dict(), status=201)


@require_http_methods(['GET'])
def track_pixel(request, email_id):
    """
    The tracking pixel itself. Embed <img src="/track/<id>.png"> in an
    outgoing email; when the recipient's client loads this image, we log
    an "open" event. This always returns a valid image, even for an
    unknown or malformed id — a broken image icon in someone's inbox would
    be a dead giveaway that something's being tracked.
    """
    try:
        parsed_id = uuid_lib.UUID(email_id)
        email = TrackedEmail.objects.get(pk=parsed_id)
        EmailOpen.objects.create(
            email=email,
            user_agent=request.META.get('HTTP_USER_AGENT', 'unknown')[:500],
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    except (ValueError, TrackedEmail.DoesNotExist):
        pass

    response = HttpResponse(PIXEL, content_type='image/png')
    # Never cache the pixel — a cached image never triggers a fresh request,
    # which would silently break tracking for repeat opens.
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

