from django.urls import reverse, resolve

try:
    url = reverse("login")
    res = resolve(url)
    print("reverse('login') ->", url)
    # mostra função/resolved view e módulo
    print("resolve ->", getattr(res, "func", res), "(module:", getattr(res.func, "__module__", None), ")")
except Exception:
    import traceback
    traceback.print_exc()