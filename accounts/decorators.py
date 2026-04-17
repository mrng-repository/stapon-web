from functools import wraps
from django.shortcuts import redirect
from .authentication import get_current_customer_user


def customer_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        customer_user = get_current_customer_user(request)
        if not customer_user:
            return redirect('customer_login')
        request.customer_user = customer_user
        return view_func(request, *args, **kwargs)
    return _wrapped_view