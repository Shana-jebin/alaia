from django.shortcuts import render
from products.models import Product


def home(request):
    signature_products = (
        Product.objects
        .filter(
            is_active=True,
            is_deleted=False,
            is_featured=True
        )
        .prefetch_related('variants__images')
        .order_by('-created_at')[:3]
    )

    return render(request, 'core/home.html', {
        'signature_products': signature_products
    })