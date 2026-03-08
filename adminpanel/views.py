from django.shortcuts import render, redirect, get_object_or_404,HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.utils.text import slugify
import json
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from products.models import Product, ProductVariant, VariantImage, Brand, Category,Occasion
from .forms import ProductForm, ProductVariantForm
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator


User = get_user_model()

def is_admin(user):
    return user.is_authenticated and user.is_staff

@never_cache
@csrf_protect
def admin_login(request):

    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('home')

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid credentials.")
        elif not user.is_staff:
            messages.error(request, "You don't have admin access.")
        elif not user.is_active:
            messages.error(request, "This account is blocked.")
        else:
            login(request, user)
            return redirect('admin_dashboard')

    return render(request, 'adminpanel/admin-login.html')

@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def admin_dashboard(request):
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    blocked_users = User.objects.filter(is_active=False).count()

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_signups = User.objects.filter(
        date_joined__gte=today_start
    ).count()

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'today_signups': today_signups,
        'username': request.user.get_full_name() or request.user.username,  # for "Welcome back"
    }

    return render(request, 'adminpanel/dashboard.html', context)

@never_cache
@login_required
@user_passes_test(is_admin)
def user_management(request):
    query = request.GET.get('q', '').strip()
    page_number = request.GET.get('page')

    users = User.objects.filter(is_superuser=False).order_by('-date_joined')


    if query:
        users = users.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query)
        )

    paginator = Paginator(users, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
    }

    return render(request, 'adminpanel/user_list.html', context)

@never_cache
@login_required
@user_passes_test(is_admin)
def toggle_block_user(request, user_id):
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)

        if user == request.user:
            messages.error(request, "You cannot block yourself.")
            return redirect('user_management')

        if user.is_active:
            user.is_active = False
            messages.success(request, f"{user.username} has been blocked.")
        else:
            user.is_active = True
            messages.success(request, f"{user.username} has been unblocked.")

        user.save()

    return redirect('user_management')




@login_required
@user_passes_test(is_admin)
def search_users(request):
    query = request.GET.get('q', '').strip()

    users = User.objects.filter(is_superuser=False)

    if query:
        users = users.filter(username__istartswith=query
)

    data = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "date_joined": user.date_joined.strftime("%b %d, %Y")
        }
        for user in users
    ]

    return JsonResponse({"users": data})

def generate_unique_slug(name, instance=None):
    slug = slugify(name)
    unique_slug = slug
    counter = 1

    while True:
        slug_exists = Category.objects.filter(slug=unique_slug)

        if instance:
            slug_exists = slug_exists.exclude(id=instance.id)

        if not slug_exists.exists():
            break

        unique_slug = f"{slug}-{counter}"
        counter += 1

    return unique_slug


@login_required
@user_passes_test(is_admin)
def admin_category_list(request):
    query = request.GET.get('q', '')

    if request.method == "POST":
        name = request.POST.get('name', '').strip().title()


        if not name:
            messages.error(request, "Category name cannot be empty.")
            return redirect('admin_category_list')


        description = request.POST.get('description')
        offer_percentage = request.POST.get('offer_percentage')
        is_active = request.POST.get('is_active') == "True"

     
        existing_category = Category.objects.filter(
            name__iexact=name,
            is_deleted=True
        ).first()

        if existing_category:
            existing_category.is_deleted = False
            existing_category.description = description
            existing_category.offer_percentage = offer_percentage or None
            existing_category.is_active = is_active
            existing_category.slug = generate_unique_slug(name, instance=existing_category)
            existing_category.save()

            messages.success(request, "Deleted category restored successfully!")
            return redirect('admin_category_list')
        

       
        if Category.objects.filter(name__iexact=name, is_deleted=False).exists():
            messages.error(request, "Category already exists!")
            return redirect('admin_category_list')


        slug = generate_unique_slug(name)

        Category.objects.create(
            name=name,
            slug=slug,
            description=description,
            offer_percentage=offer_percentage if offer_percentage else None,
            is_active=is_active
        )

        messages.success(request, "Category added successfully!")
        return redirect('admin_category_list')

 
    categories = Category.objects.filter(is_deleted=False)

    if query:
        categories = categories.filter(name__icontains=query)

    categories = categories.order_by('-created_at')

    paginator = Paginator(categories, 5)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.page(page_number)
    except:
        page_obj = paginator.page(paginator.num_pages)


    context = {
    'page_obj': page_obj,
    'query': query,
    'request': request
}

    return render(request, 'adminpanel/category-management.html', context)



@login_required
@user_passes_test(is_admin)
def admin_category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        name = request.POST.get('name', '').strip().title()

        # ❗ EMPTY NAME BLOCK
        if not name:
            messages.error(request, "Category name cannot be empty.")
            return redirect('admin_category_list')



        category.name = name
        category.slug = generate_unique_slug(name, instance=category)
        category.description = request.POST.get('description')
        category.offer_percentage = request.POST.get('offer_percentage') or None
        category.is_active = request.POST.get('is_active') == "True"

        category.save()

        messages.success(request, "Category updated successfully!")
        return redirect('admin_category_list')

    return redirect('admin_category_list')



@login_required
@user_passes_test(is_admin)
def admin_category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        category.is_deleted = True  
        category.save()

        messages.success(request, "Category deleted successfully!")

    return redirect('admin_category_list')






@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def product_list(request):
    
    search_query = request.GET.get('q', '')
    per_page = int(request.GET.get('per_page', 10))
    page_number = request.GET.get('page', 1)
    show_deleted = request.GET.get('show') == 'deleted'

    if per_page not in [5, 10, 25, 50]:
        per_page = 10

   

    if show_deleted:
        products = Product.all_objects.filter(is_deleted=True)
    else:
        products = Product.objects.all()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(brand__name__icontains=search_query)
        )

    products = products.order_by('-created_at' if not show_deleted else '-deleted_at')


    all_active = Product.objects.filter(is_deleted=False)
    total_products = all_active.count()
    active_products = all_active.filter(is_active=True).count()
    inactive_products = all_active.filter(is_active=False).count()
    deleted_count = Product.objects.filter(is_deleted=True).count()

    paginator = Paginator(products, per_page)
    products_page = paginator.get_page(page_number)

    categories = Category.objects.filter(
    is_deleted=False,
    is_active=True
)
    brands = Brand.objects.all()

    context = {
        'products': products_page,
        'search_query': search_query,
        'per_page': per_page,
        'show_deleted': show_deleted,
        'categories': categories,
        'brands': brands,
        'total_products': total_products,
        'active_products': active_products,
        'inactive_products': inactive_products,
        'deleted_count': deleted_count,
        'occasions': Occasion.objects.all(),
    }
    return render(request, 'adminpanel/product_list.html', context)

@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
@require_POST
def product_add(request):

    data = request.POST
    product_form = ProductForm(data)

    if not product_form.is_valid():
        return JsonResponse({
            'success': False,
            'errors': product_form.errors
        }, status=400)

    product = product_form.save()
    variants_json = data.get('variants')

    if not variants_json:
        return JsonResponse({
            'success': False,
            'message': 'Variants data is required.'
        }, status=400)

    try:
        variants_data = json.loads(variants_json)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid variants JSON'
        }, status=400)

   
    for index, variant_data in enumerate(variants_data, start=1):

        image_count = int(variant_data.get('image_count', 0))

        if image_count < 3:
            return JsonResponse({
                'success': False,
                'message': 'Each variant must have at least 3 images.'
            }, status=400)

      
        variant = ProductVariant.objects.create(
            product=product,
            color=variant_data.get('color'),
            size=variant_data.get('size'),
            price=variant_data.get('price'),
            sales_price=variant_data.get('sales_price') or None,
            stock=variant_data.get('stock'),
        )

        
        image_key = f'variant_images_{index}'
        images = request.FILES.getlist(image_key)

        if image_count < 3:
            return JsonResponse({
                'success': False,
                'message': 'Each variant must have at least 3 images uploaded.'
            }, status=400)

        for img in images:
            VariantImage.objects.create(
                variant=variant,
                image=img
            )

    return JsonResponse({
        'success': True,
        'product_id': product.id,
        'message': 'Product added successfully!'
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, is_deleted=False)

    if request.method == 'POST':

        product_form = ProductForm(request.POST, request.FILES, instance=product)

        if not product_form.is_valid():
            return JsonResponse({
                'success': False,
                'errors': product_form.errors
            }, status=400)

        product = product_form.save()

        variants_json = request.POST.get('variants')

        if variants_json:
            try:
                variants_data = json.loads(variants_json)
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid variant data'
                }, status=400)

            for variant_data in variants_data:
                variant_id = variant_data.get('id')

                if not variant_id:
                    continue

                try:
                    variant = ProductVariant.objects.get(
                        id=variant_id,
                        product=product
                    )
                except ProductVariant.DoesNotExist:
                    continue

                variant.color = variant_data.get('color')
                variant.size = variant_data.get('size')

                # Convert properly
                variant.price = float(variant_data.get('price') or 0)
                variant.sales_price = (
                    float(variant_data.get('sales_price'))
                    if variant_data.get('sales_price')
                    else None
                )
                variant.stock = int(variant_data.get('stock') or 0)

                variant.save()

        
                index = variants_data.index(variant_data) + 1
                image_key = f'variant_images_{index}'
                images = request.FILES.getlist(image_key)

                if images:
                  
                    variant.images.all().delete()

                    for img in images:
                        VariantImage.objects.create(
                            variant=variant,
                            image=img
                        )

        return JsonResponse({
            'success': True,
            'message': 'Product updated successfully!'
        })

    # ---- GET PART ----
    variants = []
    for v in product.variants.filter(is_deleted=False):

        images = []
        for img in v.images.all():
            images.append({
                'id': img.id,
                'url': img.image.url,
            })

        variants.append({
            'id': v.id,
            'color': v.color,
            'size': v.size,
            'price': str(v.price),
            'sales_price': str(v.sales_price) if v.sales_price else '',
            'stock': v.stock,
            'images': images,
        })

    return JsonResponse({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'category': product.category_id,
        'brand': product.brand_id,
        'occasions': list(product.occasions.values_list('id', flat=True)),
        'is_active': product.is_active,
        'is_featured': product.is_featured,
        'variants': variants,
    })
@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
@require_POST
def product_soft_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, is_deleted=False)
    product.soft_delete()
    return JsonResponse({'success': True, 'message': f'"{product.name}" has been deactivated (soft deleted).'})

@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
@require_POST
def restore_product(request, pk):
    try:
        product = Product.all_objects.get(pk=pk)  
        product.restore()

        return JsonResponse({
            "success": True,
            "message": "Product restored successfully!"
        })

    except Product.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Product not found"
        })
    
@require_POST
def product_toggle_status(request, pk):
    product = get_object_or_404(Product, pk=pk, is_deleted=False)
    product.is_active = not product.is_active
    product.save()
    status = 'Active' if product.is_active else 'Inactive'
    return JsonResponse({'success': True, 'is_active': product.is_active, 'message': f'Product is now {status}.'})


def product_upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image = request.FILES['image']
        variant_id = request.POST.get('variant_id')
        
        if variant_id:
            variant = get_object_or_404(ProductVariant, pk=variant_id)
            variant_image = VariantImage.objects.create(variant=variant, image=image)
            return JsonResponse({'success': True, 'image_id': variant_image.id, 'image_url': variant_image.image.url})
        
        return JsonResponse({'success': False, 'message': 'variant_id is required'}, status=400)
    
    return JsonResponse({'success': False, 'message': 'No image provided'}, status=400)


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def brand_list(request):

    query = request.GET.get('q','').strip()

    active_brands = Brand.objects.filter(is_active=True).order_by('name')
    inactive_brands = Brand.objects.filter(is_active=False).order_by('name')


    if query:
        active_brands = active_brands.filter(name__icontains=query)
        inactive_brands = inactive_brands.filter(name__icontains=query)


    paginator = Paginator(active_brands, 5)  
    page_number = request.GET.get('page')
    brands = paginator.get_page(page_number)

    return render(request,'adminpanel/brand-management.html',{
        'brands': brands,
        'inactive_brands': inactive_brands,
        'query': query,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def brand_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        rating = request.POST.get('rating')
        logo = request.FILES.get('logo')

        if not name:
            messages.error(request, "Brand name is required")
            return redirect('brand_create')

        if Brand.objects.filter(name__iexact=name).exists():
            messages.error(request, "Brand already exists")
            return redirect('brand_create')

        if rating:
            try:
                rating = float(rating)
                if rating < 0 or rating > 5:
                    messages.error(request, "Rating must be between 0 and 5")
                    return redirect('brand_create')
            except:
                messages.error(request, "Invalid rating value")
                return redirect('brand_create')
        else:
            rating = 0.0

        Brand.objects.create(
            name=name,
            rating=rating,
            logo=logo
        )

        messages.success(request, "Brand added successfully")
        return redirect('brand_list')


    return render(request, 'adminpanel/brand-management.html')


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def brand_edit(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        rating = request.POST.get('rating')
        logo = request.FILES.get('logo')

   
        if not name:
            messages.error(request, "Brand name is required")
            return redirect('brand_edit', pk=pk)

        if Brand.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, "Brand already exists")
            return redirect('brand_edit', pk=pk)

        if rating:
            try:
                rating = float(rating)
                if rating < 0 or rating > 5:
                    messages.error(request, "Rating must be between 0 and 5")
                    return redirect('brand_edit', pk=pk)
            except:
                messages.error(request, "Invalid rating value")
                return redirect('brand_edit', pk=pk)
        else:
            rating = 0.0

        brand.name = name
        brand.rating = rating

        if logo:
            brand.logo = logo

        brand.save()

        messages.success(request, "Brand updated successfully")
        return redirect('brand_list')

    return render(request, 'adminpanel/brand-edit.html', {
        'brand': brand
    })

@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    brand.is_active = False
    brand.save()
    return redirect('brand_list')

@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def brand_restore(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    brand.is_active = True
    brand.save()
    return redirect('brand_list')



# ADD THESE IMPORTS AND VIEWS TO YOUR adminpanel/views.py

from orders.models import Order, OrderItem
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncDate


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def admin_order_list(request):
    orders = Order.objects.select_related('user').prefetch_related('items')

    q = request.GET.get('q', '').strip()
    if q:
        orders = orders.filter(
            Q(order_id__icontains=q) |
            Q(user__email__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(full_name__icontains=q) |
            Q(items__product_name__icontains=q)
        ).distinct()

    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)

    date_from = request.GET.get('date_from', '')
    if date_from:
        try:
            from datetime import datetime
            orders = orders.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass

    date_to = request.GET.get('date_to', '')
    if date_to:
        try:
            from datetime import datetime
            orders = orders.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    sort = request.GET.get('sort', '-created_at')
    allowed_sorts = ['created_at', '-created_at', 'total', '-total', 'status']
    if sort in allowed_sorts:
        orders = orders.order_by(sort)
    else:
        orders = orders.order_by('-created_at')

    paginator = Paginator(orders, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Stats
    all_orders = Order.objects.all()
    stats = {
        'total':     all_orders.count(),
        'pending':   all_orders.filter(status='pending').count(),
        'shipped':   all_orders.filter(status='shipped').count(),
        'delivered': all_orders.filter(status='delivered').count(),
        'cancelled': all_orders.filter(status='cancelled').count(),
        'revenue':   all_orders.filter(status='delivered').aggregate(t=Sum('total'))['t'] or 0,
    }

    return render(request, 'adminpanel/order_list.html', {
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
        'stats': stats,
        'status_choices': Order.STATUS_CHOICES,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'adminpanel/order_detail.html', {
        'order': order,
        'status_choices': Order.STATUS_CHOICES,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
@require_POST
def admin_order_status(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    try:
        data = json.loads(request.body)
        new_status = data.get('status', '').strip()
    except Exception:
        new_status = request.POST.get('status', '').strip()

    valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Invalid status.'}, status=400)

    # If cancelling from admin side, restore stock
    if new_status == 'cancelled' and order.status not in ('cancelled', 'returned'):
        for item in order.items.filter(status='active'):
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=['stock'])
            item.status = 'cancelled'
            item.save()

    # If marking as returned, restore stock
    if new_status == 'returned' and order.status == 'return_requested':
        for item in order.items.filter(status='return_requested'):
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=['stock'])
            item.status = 'returned'
            item.save()

    order.status = new_status
    order.save(update_fields=['status', 'updated_at'])

    return JsonResponse({
        'success': True,
        'message': f'Order status updated to {order.get_status_display()}.',
        'new_status': new_status,
        'new_status_display': order.get_status_display(),
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
def admin_inventory(request):
    """Stock management view for admin."""
    from products.models import Product, ProductVariant

    variants = ProductVariant.objects.filter(
        is_deleted=False,
        product__is_deleted=False,
        product__is_active=True,
    ).select_related('product', 'product__category', 'product__brand').order_by('stock')

    q = request.GET.get('q', '').strip()
    if q:
        variants = variants.filter(
            Q(product__name__icontains=q) |
            Q(product__brand__name__icontains=q) |
            Q(product__category__name__icontains=q)
        )

    stock_filter = request.GET.get('stock', '')
    if stock_filter == 'out':
        variants = variants.filter(stock=0)
    elif stock_filter == 'low':
        variants = variants.filter(stock__gt=0, stock__lte=10)
    elif stock_filter == 'ok':
        variants = variants.filter(stock__gt=10)

    paginator = Paginator(variants, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    stats = {
        'total':    ProductVariant.objects.filter(is_deleted=False).count(),
        'out':      ProductVariant.objects.filter(is_deleted=False, stock=0).count(),
        'low':      ProductVariant.objects.filter(is_deleted=False, stock__gt=0, stock__lte=10).count(),
        'healthy':  ProductVariant.objects.filter(is_deleted=False, stock__gt=10).count(),
    }

    return render(request, 'adminpanel/inventory.html', {
        'page_obj': page_obj,
        'q': q,
        'stock_filter': stock_filter,
        'stats': stats,
    })


@never_cache
@login_required
@user_passes_test(is_admin, login_url='admin_login')
@require_POST
def admin_update_stock(request, variant_id):
    from products.models import ProductVariant
    variant = get_object_or_404(ProductVariant, id=variant_id)
    try:
        data = json.loads(request.body)
        new_stock = int(data.get('stock', 0))
        if new_stock < 0:
            return JsonResponse({'error': 'Stock cannot be negative.'}, status=400)
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid stock value.'}, status=400)

    variant.stock = new_stock
    variant.save(update_fields=['stock'])
    return JsonResponse({
        'success': True,
        'stock': variant.stock,
        'message': f'Stock updated to {variant.stock}.',
    })