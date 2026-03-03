from django.shortcuts import render
from django.core.paginator import Paginator
from .models import Product, Category, Brand,ProductVariant
from django.db.models import Q, Min, Sum, F, ExpressionWrapper, DecimalField, Avg, Max
from .models import Occasion
# ── Colour map: model value → display label + hex ──────────────────────────
COLOR_MAP = {
    'black':    {'label': 'Black',    'hex': '#1a1a1a'},
    'white':    {'label': 'White',    'hex': '#f5f0e8'},
    'nude':     {'label': 'Nude',     'hex': '#e8c9a0'},
    'beige':    {'label': 'Beige',    'hex': '#c9b99a'},
    'brown':    {'label': 'Brown',    'hex': '#7c5c3a'},
    'tan':      {'label': 'Tan',      'hex': '#c8975a'},
    'gold':     {'label': 'Gold',     'hex': '#c9a96e'},
    'silver':   {'label': 'Silver',   'hex': '#aaa89e'},
    'rose_gold':{'label': 'Rose Gold','hex': '#c9917a'},
    'maroon':   {'label': 'Maroon',   'hex': '#6e2c2c'},
    'navy':     {'label': 'Navy',     'hex': '#1c2a4a'},
    'olive':    {'label': 'Olive',    'hex': '#6b6b3a'},
    'peach':    {'label': 'Peach',    'hex': '#e8b09a'},
}

OCCASION_MAP = [
    {'value': 'casual',   'label': 'Casual'},
    {'value': 'formal',   'label': 'Formal'},
    {'value': 'sports',   'label': 'Sports'},
    {'value': 'party',    'label': 'Party'},
    {'value': 'wedding',  'label': 'Wedding'},
    {'value': 'ethnic',   'label': 'Ethnic'},
    {'value': 'beach',    'label': 'Beach'},
    {'value': 'office',   'label': 'Office'},
    {'value': 'outdoor',  'label': 'Outdoor'},
    {'value': 'festive',  'label': 'Festive'},
]


def product_list(request):
 
   
    search_query       = request.GET.get('q', '').strip()
    sort               = request.GET.get('sort', '')
    selected_categories = request.GET.getlist('category')
    selected_brands     = request.GET.getlist('brand')
    selected_colors     = request.GET.getlist('color')
    selected_sizes      = request.GET.getlist('size')
    selected_occasions  = request.GET.getlist('occasion')
    price_min           = request.GET.get('price_min', '').strip()
    price_max           = request.GET.get('price_max', '').strip()
    page_number         = request.GET.get('page', 1)

    # ── Base queryset ────────────────────────────────────────────────────────
    products = (
        Product.objects
        .filter(is_deleted=False, is_active=True)
        .select_related('brand', 'category')
        .prefetch_related('variants__images')
    )

    # ── Search ────────────────────────────────────────────────────────────────
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(brand__name__icontains=search_query)
        )

   
    if selected_categories:
        products = products.filter(category__id__in=selected_categories)

    
    if selected_brands:
        products = products.filter(brand__id__in=selected_brands)

    
    if selected_colors:
        products = products.filter(variants__color__in=selected_colors).distinct()

    
    if selected_sizes:
        products = products.filter(variants__size__in=selected_sizes).distinct()

    
    if selected_occasions:
        products = products.filter(
            occasions__id__in=selected_occasions
        ).distinct()


        


   
    products = products.annotate(
        calculated_min_price=Min('variants__sales_price')
)


    if price_min:
        try:
            products = products.filter(calculated_min_price__gte=float(price_min))
        except ValueError:
            pass

    if price_max:
        try:
            products = products.filter(calculated_min_price__lte=float(price_max))
        except ValueError:
            pass

    # ── Sort ──────────────────────────────────────────────────────────────────
    if sort == 'price_low_high':
        products = products.order_by('calculated_min_price')

    elif sort == 'price_high_low':
        products = products.order_by('-calculated_min_price')
    elif sort == 'popularity':
        products = products.order_by('-created_at')


    elif sort == 'discount':
        products = products.annotate(
            discount_amount=Max(
                F('variants__price') - F('variants__sales_price')
            )
        ).order_by('-discount_amount')

    else:
        # Default → New Arrivals
        products = products.order_by('-created_at')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator     = Paginator(products, 12)
    products_page = paginator.get_page(page_number)
  

    # ── Sidebar data ──────────────────────────────────────────────────────────
    categories = Category.objects.filter(is_deleted=False, is_active=True).order_by('name')
    brands     = Brand.objects.filter(is_active=True).order_by('name')

    # Colors: only show colours that actually exist in current active products
    used_colors = (
        ProductVariant.objects
        .filter(product__is_deleted=False, product__is_active=True)
        .values_list('color', flat=True)
        .distinct()
    )
    available_colors = [
        {'value': c, 'label': COLOR_MAP.get(c, {}).get('label', c.title()), 'hex': COLOR_MAP.get(c, {}).get('hex', '#888')}
        for c in used_colors if c
    ]

    # Sizes: same logic
    used_sizes = (
        ProductVariant.objects
        .filter(product__is_deleted=False, product__is_active=True)
        .values_list('size', flat=True)
        .distinct()
        .order_by('size')
    )
    available_sizes = [s for s in used_sizes if s]

   
    available_occasions = Occasion.objects.filter(
        products__is_deleted=False,
        products__is_active=True
    ).distinct().order_by('name')
 
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    query_string = get_copy.urlencode()  

   
    def qs_without(key):
        q = request.GET.copy()
        q.pop(key, None)
        q.pop('page', None)
        return q.urlencode()
    def qs_without_price():
        q = request.GET.copy()
        q.pop('price_min', None)
        q.pop('price_max', None)
        q.pop('page', None)
        return q.urlencode()

    context = {
        # Products
        'products':            products_page,

        # Active filter values
        'search_query':        search_query,
        'sort':                sort,
        'selected_categories': selected_categories,
        'selected_brands':     selected_brands,
        'selected_colors':     selected_colors,
        'selected_sizes':      selected_sizes,
        'selected_occasions':  selected_occasions,
        'price_min':           price_min,
        'price_max':           price_max,

        # Sidebar lists
        'categories':          categories,
        'brands':              brands,
        'available_colors':    available_colors,
        'available_sizes':     available_sizes,
        'available_occasions': available_occasions,

        # URL helpers
        'query_string':        query_string,
        'query_string_no_cat':   qs_without('category'),
        'query_string_no_brand': qs_without('brand'),
        'query_string_no_color': qs_without('color'),
        'query_string_no_size':  qs_without('size'),
        'query_string_no_occ':   qs_without('occasion'),
        'query_string_no_price': qs_without_price(),
        
    }

    return render(request, 'products/shop.html', context)


from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils import timezone
import json

from .models import (
    Product, ProductVariant, VariantImage,   # ← VariantImage, not ProductImage
    Review, Coupon, Category
)


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)   # ProductManager hides deleted

    # ── Redirect guard: deleted or inactive → back to shop ──────────
    if not product.is_active or product.is_deleted:
        return redirect('products:shop')

    # ── Variants ─────────────────────────────────────────────────────
    variants = (
        product.variants
        .filter(is_deleted=False)
        .prefetch_related('images')
        .order_by('price')
    )
    default_variant = variants.filter(stock__gt=0).first() or variants.first()

    # ── Reviews ──────────────────────────────────────────────────────
    reviews = (
        Review.objects
        .filter(product=product, is_approved=True)
        .select_related('user')
        .order_by('-created_at')
    )
    stats        = reviews.aggregate(avg=Avg('rating'), total=Count('id'))
    avg_rating   = round(stats['avg'] or 0, 1)
    review_count = stats['total']
    star_breakdown = {s: reviews.filter(rating=s).count() for s in range(5, 0, -1)}

    # ── Coupons ───────────────────────────────────────────────────────
    now = timezone.now()
    coupons = Coupon.objects.filter(
        Q(products=product) | Q(categories=product.category),
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now,
    ).distinct()

    # ── Related products ──────────────────────────────────────────────
    related = (
        Product.objects                        # ProductManager auto-hides deleted
        .filter(
            Q(category=product.category) | Q(brand=product.brand),
            is_active=True,
        )
        .exclude(id=product.id)
        .prefetch_related('variants__images')
        .distinct()[:8]
    )

    # ── Stock status ──────────────────────────────────────────────────
    total_stock  = product.total_stock
    stock_status = (
        'out_of_stock' if total_stock == 0
        else 'low_stock'  if total_stock <= 10
        else 'in_stock'
    )

    # ── Has current user already reviewed? ───────────────────────────
    user_reviewed = (
        request.user.is_authenticated
        and reviews.filter(user=request.user).exists()
    )

    return render(request, 'products/detail.html', {
        'product':          product,
        'variants':         variants,
        'default_variant':  default_variant,
        'reviews':          reviews,
        'avg_rating':       avg_rating,
        'review_count':     review_count,
        'star_breakdown':   star_breakdown,
        'related':          related,
        'coupons':          coupons,
        'total_stock':      total_stock,
        'stock_status':     stock_status,
        'user_reviewed':    user_reviewed,
    })


# ── AJAX: variant price/stock/images on size change ──────────────────
def variant_data(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)
    images  = [
        {'url': img.image.url}
        for img in variant.images.all()
    ]
    return JsonResponse({
        'id':          variant.id,
        'price':       str(variant.price),
        'sales_price': str(variant.final_price),   # uses your final_price property
        'discount_pct': variant.discount_percentage,
        'stock':       variant.stock,
        'images':      images,
    })


# ── AJAX: submit review ───────────────────────────────────────────────
@require_POST
@login_required
def submit_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        data    = json.loads(request.body)
        rating  = int(data.get('rating', 0))
        comment = data.get('comment', '').strip()

        if not (1 <= rating <= 5):
            return JsonResponse({'error': 'Rating must be between 1 and 5.'}, status=400)
        if len(comment) < 10:
            return JsonResponse({'error': 'Review must be at least 10 characters.'}, status=400)
        if Review.objects.filter(product=product, user=request.user).exists():
            return JsonResponse({'error': 'You have already reviewed this product.'}, status=400)

        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment,
            is_approved=False,   # admin approves before it shows
        )
        return JsonResponse({'success': True, 'message': 'Review submitted — it will appear after approval.'})

    except (ValueError, KeyError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid request data.'}, status=400)
















from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Cart, CartItem, ProductVariant


def add_to_cart(request, variant_id):

    if not request.user.is_authenticated:
        messages.error(request, "Please login first.")
        return redirect("account_login")

    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)

    # Stock check
    if variant.stock <= 0:
        messages.error(request, "This product is out of stock.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    cart = Cart.objects.get(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={
            "quantity": 1,
            "price_at_added": variant.final_price
        }
    )

    if not created:
     
        if cart_item.quantity + 1 > variant.stock:
            messages.error(request, "Not enough stock available.")
        else:
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, "Quantity updated in cart.")
    else:
        messages.success(request, "Product added to cart.")

    return redirect(request.META.get("HTTP_REFERER", "/"))


from django.shortcuts import render
from .models import Cart


def cart_view(request):

    if not request.user.is_authenticated:
        return redirect("account_login")

    cart = Cart.objects.get(user=request.user)

    items = cart.items.select_related("variant", "variant__product")

    total = 0

    for item in items:
        total += item.subtotal()

    context = {
        "cart": cart,
        "items": items,
        "total": total,
    }

    return render(request, "cart/cart.html", context)



from django.db import transaction


@transaction.atomic
def update_cart_quantity(request, item_id, action):

    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

    variant = cart_item.variant

    if action == "increase":
        if cart_item.quantity + 1 > variant.stock:
            messages.error(request, "Not enough stock available.")
        else:
            cart_item.quantity += 1
            cart_item.save()

    elif action == "decrease":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()

    return redirect("cart")



