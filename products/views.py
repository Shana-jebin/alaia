from django.shortcuts import render
from .models import Product
from .models import Category

def shop_view(request):
    products = Product.objects.filter(
        is_listed=True,
        is_blocked=False
    )

    context = {
        'products': products
    }

    return render(request, 'products/shop.html', context)




def admin_category_list(request):
    categories = Category.objects.filter(is_deleted=False).order_by('-created_at')

    context = {
        'categories': categories
    }
    return render(request, 'admin/category_list.html', context)

