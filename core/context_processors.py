from core.models import CartItem

def cart_count_processor(request):
    if request.user.is_authenticated:
        count = CartItem.objects.filter(user=request.user).count()
    else:
        count = 0
    return {'cart_count': count}
