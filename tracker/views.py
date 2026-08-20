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


def is_compose_or_preview_request(request):
    """
    Detect if the incoming pixel request is coming from an email client's
    compose window (e.g. pasting into Gmail's 'Insert photo -> Web Address (URL)'),
    a link previewer, or a HEAD request.
    """
    # 1. HEAD requests are metadata checks (e.g. checking image dimensions), not actual views
    if request.method == 'HEAD':
        return True

    # 2. Check Referer header for mail client compose web applications
    referer = request.META.get('HTTP_REFERER', '').lower()
    compose_domains = [
        'mail.google.com',
        'mail.yahoo.com',
        'outlook.live.com',
        'outlook.office.com',
        'outlook.office365.com',
        'mail.aol.com',
        'mail.com',
        'zoho.com',
        'proton.me',
        'protonmail.com',
        'icloud.com',
        'web.whatsapp.com',
        'slack.com',
        'teams.microsoft.com',
        'discord.com',
    ]
    if any(domain in referer for domain in compose_domains):
        return True

    # 3. Check prefetch/preview headers sent by browsers or mail clients
    purpose = request.META.get('HTTP_PURPOSE', '').lower()
    x_purpose = request.META.get('HTTP_X_PURPOSE', '').lower()
    sec_purpose = request.META.get('HTTP_SEC_PURPOSE', '').lower()
    if any(p in ['prefetch', 'preview'] for p in [purpose, x_purpose, sec_purpose]):
        return True

    return False


@require_http_methods(['GET', 'HEAD'])
def track_pixel(request, email_id):
    """
    The tracking pixel itself. Embed the pixel URL in an outgoing email;
    when the recipient's client loads this image, we log an "open" event.
    This always returns a valid image. Compose/preview requests are served
    without logging an open event.
    """
    if not is_compose_or_preview_request(request):
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

