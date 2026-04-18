from django.shortcuts import render

# Create your views here.
def csrf_failure(request, reason=""):
    path = request.path

    context = {
        "title": "操作を完了できませんでした",
        "message": "お手数ですが、もう一度画面を開き直してお試しください。",
        "login_url": "",
        "show_browser_note": False,
    }

    if path.startswith("/store/login/"):
        context.update({
            "title": "店舗ログインを完了できませんでした",
            "message": "LINE・Gmailなどのアプリ内ブラウザでは、ログイン時にエラーになる場合があります。下記URLをSafariまたはChromeに直接貼り付けて開いてください。",
            "login_url": "https://stapon.retail-system.shop/store/login/",
            "show_browser_note": True,
        })

    elif path.startswith("/store/customer/login/"):
        context.update({
            "title": "顧客ログインを完了できませんでした",
            "message": "LINE・Gmailなどのアプリ内ブラウザでは、ログイン時にエラーになる場合があります。下記URLをSafariまたはChromeに直接貼り付けて開いてください。",
            "login_url": "https://stapon.retail-system.shop/store/customer/login/",
            "show_browser_note": True,
        })

    return render(request, "errors/csrf_error.html", context, status=403)