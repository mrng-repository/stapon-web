from datetime import datetime
from urllib.parse import urlencode

from django.core import signing
from django.urls import reverse


SIGNING_SALT = 'stamp-grant-qr'


def build_stamp_grant_payload(store_user_id, stamp_card_id, grant_count, expires_at):
    return {
        'store_user_id': store_user_id,
        'stamp_card_id': stamp_card_id,
        'grant_count': grant_count,
        'expires_at': expires_at.isoformat(),
    }


def sign_stamp_grant_payload(payload):
    return signing.dumps(payload, salt=SIGNING_SALT)


def unsign_stamp_grant_payload(token):
    return signing.loads(token, salt=SIGNING_SALT)


def build_stamp_grant_url(request, signed_token):
    path = reverse('customer_stamp_grant')
    return request.build_absolute_uri(f'{path}?token={signed_token}')