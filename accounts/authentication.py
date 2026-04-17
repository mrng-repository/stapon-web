from .models import CustomerUser


def get_current_customer_user(request):
    customer_user_id = request.session.get('customer_user_id')

    if not customer_user_id:
        return None

    try:
        return CustomerUser.objects.get(id=customer_user_id, is_active=True)
    except CustomerUser.DoesNotExist:
        return None


def login_customer(request, customer_user):
    request.session['customer_user_id'] = customer_user.id


def logout_customer(request):
    request.session.pop('customer_user_id', None)