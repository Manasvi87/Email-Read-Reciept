import uuid
from django.db import models


class TrackedEmail(models.Model):
    """One email you want to know the fate of."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} — {self.subject or "(no note)"}'

    @property
    def open_count(self):
        return len(self.opens.all())

    def to_dict(self):
        opens = list(self.opens.all().order_by('timestamp'))
        return {
            'id': str(self.id),
            'recipient': self.recipient,
            'subject': self.subject,
            'createdAt': self.created_at.isoformat(),
            'opens': [
                {
                    'timestamp': o.timestamp.isoformat(),
                    'userAgent': o.user_agent,
                    'ip': o.ip_address,
                }
                for o in opens
            ],
        }


class EmailOpen(models.Model):
    """A single moment the tracking pixel was loaded."""

    email = models.ForeignKey(TrackedEmail, related_name='opens', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'{self.email.recipient} opened at {self.timestamp}'
