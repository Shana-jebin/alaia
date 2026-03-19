import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q
from accounts.models import Address
from products.models import Cart, CartItem, Coupon, Product, ProductVariant
from .models import (
    CouponUsage, Order, OrderItem,
    Wallet, WalletTransaction,
    Wishlist, WishlistItem,
)
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse



def _get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def _wishlist(user):
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist


def _validate_coupon_for_user(code, user, subtotal):
    """
    Returns (coupon, discount_amount, error_string).
    error_string is '' on success.
    """
    now = timezone.now()
    try:
        coupon = Coupon.objects.get(
            code__iexact=code,
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now,
        )
    except Coupon.DoesNotExist:
        return None, 0, "Invalid or expired coupon code."

    if subtotal < coupon.min_order:
        return None, 0, f"Minimum order of ₹{coupon.min_order:.0f} required."

    ok, msg = coupon.can_user_apply(user)
    if not ok:
        return None, 0, msg

    discount = coupon.compute_discount(subtotal)
    return coupon, discount, ''

@login_required
@require_POST
def wallet_add_money(request):
    try:
        data   = json.loads(request.body)
        amount = Decimal(str(data.get('amount', 0)))
    except Exception:
        return JsonResponse({'error': 'Invalid amount.'}, status=400)

    if amount < Decimal('1'):
        return JsonResponse({'error': 'Minimum amount is ₹1.'}, status=400)
    if amount > Decimal('10000'):
        return JsonResponse({'error': 'Maximum amount is ₹10,000.'}, status=400)

    wallet = _get_wallet(request.user)
    wallet.credit(
        amount,
        description=f"Money added to wallet",
    )
    return JsonResponse({
        'success': True,
        'message': f'₹{amount:.0f} added to your wallet.',
        'new_balance': str(wallet.balance),
    })
# ── CHECKOUT ─────────────────────────────────────────────────────

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related(
        'variant', 'variant__product', 'variant__product__brand'
    ).prefetch_related('variant__images')

    valid_items   = []
    blocked_names = []
    for item in items:
        v = item.variant
        if (v and not v.is_deleted
                and v.product.is_active
                and not v.product.is_deleted
                and v.product.category.is_active
                and not v.product.category.is_deleted
                and v.product.brand.is_active
                and v.stock > 0):
            valid_items.append(item)
        else:
            blocked_names.append(v.product.name if v else 'Unknown item')

    if not valid_items:
        messages.error(request, "Your cart has no available items to checkout.")
        return redirect('orders:cart')

    if blocked_names:
        messages.warning(request, f"Removed unavailable items: {', '.join(blocked_names)}")

    from decimal import Decimal

    subtotal = sum(
    (Decimal(str(item.variant.final_price)) * item.quantity for item in valid_items),
    Decimal("0.00")
)

    shipping = Decimal("0") if subtotal >= Decimal("2999") else Decimal("99")
    total    = subtotal + shipping

    addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created_at')
    if addresses.count() < 2:
        messages.error(request, "Please add at least 2 delivery addresses before checkout.")
        return redirect(f"{reverse('address_list')}?next={request.path}")
    default_address = addresses.filter(is_default=True).first() or addresses.first()

    wallet  = _get_wallet(request.user)

    # Available coupons for display (not filtered by user usage here — done on apply)
    now         = timezone.now()
    product_ids = [i.variant.product_id for i in valid_items]
    category_ids= [i.variant.product.category_id for i in valid_items]
    coupons     = Coupon.objects.filter(
        is_active=True, valid_from__lte=now, valid_to__gte=now,
        min_order__lte=subtotal,
    ).filter(
        Q(products__id__in=product_ids) | Q(categories__id__in=category_ids)
        | Q(products__isnull=True, categories__isnull=True)
    ).distinct()

    return render(request, 'orders/checkout.html', {
        'items':           valid_items,
        'addresses':       addresses,
        'default_address': default_address,
        'subtotal':        subtotal,
        'shipping':        shipping,
        'total':           total,
        'coupons':         coupons,
        'wallet':          wallet,
        'RAZORPAY_KEY_ID': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    })




@login_required
def apply_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method.'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    code     = data.get('code', '').strip().upper()
    subtotal = Decimal(str(data.get('subtotal', 0)))

    if not code:
        return JsonResponse({'error': 'Please enter a coupon code.'}, status=400)

    coupon, discount, err = _validate_coupon_for_user(code, request.user, subtotal)
    if err:
        return JsonResponse({'error': err}, status=400)

    return JsonResponse({
        'success':  True,
        'discount': discount,
        'code':     coupon.code,
        'message':  f'Coupon applied! You saved ₹{discount:.0f}',
    })


# ── PLACE ORDER (COD / WALLET) ────────────────────────────────────

@login_required
@transaction.atomic
def place_order(request):
    if request.method != 'POST':
        return redirect('orders:checkout')

    cart  = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related(
        'variant', 'variant__product', 'variant__product__brand'
    ).prefetch_related('variant__images')

    address_id     = request.POST.get('address_id')
    payment_method = request.POST.get('payment_method', 'cod')
    coupon_code    = request.POST.get('coupon_code', '').strip().upper()

    address = get_object_or_404(Address, id=address_id, user=request.user)

    # ── validate items ──
    valid_items = []
    for item in items:
        v = item.variant
        if (v and not v.is_deleted and v.product.is_active
                and not v.product.is_deleted and v.stock >= item.quantity):
            valid_items.append(item)
        else:
            name = v.product.name if v else 'Item'
            messages.error(request, f"'{name}' is unavailable or has insufficient stock.")
            return redirect('orders:checkout')

    if not valid_items:
        messages.error(request, "No valid items to order.")
        return redirect('orders:cart')

    subtotal = sum(
    (Decimal(str(item.variant.final_price)) * item.quantity for item in valid_items),
    Decimal("0.00")
)
    shipping = Decimal('0') if subtotal >= Decimal('2999') else Decimal('99')
    discount = Decimal('0')
    coupon   = None

    # ── validate coupon ──
    if coupon_code:
        coupon, disc_float, err = _validate_coupon_for_user(coupon_code, request.user, subtotal)
        if coupon:
            discount = Decimal(str(disc_float))
        # silently ignore invalid coupon at this stage (was validated on apply)

    total = subtotal + shipping - discount

    # ── wallet payment ──
    if payment_method == 'wallet':
        wallet = _get_wallet(request.user)
        if wallet.balance < total:
            messages.error(request, f"Insufficient wallet balance. Your balance: ₹{wallet.balance:.0f}")
            return redirect('orders:checkout')

    # ── create order ──
    order = Order.objects.create(
        user=request.user,
        full_name=address.full_name,
        address_line1=address.address_line1,
        address_line2=address.address_line2 or '',
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        country=address.country,
        phone=address.phone,
        payment_method=payment_method,
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        total=total,
        coupon_code=coupon_code,
        payment_status='paid' if payment_method in ('wallet',) else 'pending',
    )

    # ── create order items & deduct stock ──
    for item in valid_items:
        v   = item.variant
        img = v.images.first()
        OrderItem.objects.create(
            order=order,
            variant=v,
            product_name=v.product.name,
            brand_name=v.product.brand.name,
            color=v.color,
            size=v.size,
            image_url=img.image.url if img else '',
            quantity=item.quantity,
            unit_price=v.final_price,
        )
        v.stock -= item.quantity
        v.save(update_fields=['stock'])

    # ── deduct wallet balance ──
    if payment_method == 'wallet':
        wallet = _get_wallet(request.user)
        wallet.debit(
            total,
            description=f"Payment for order {order.order_id}",
            order=order,
        )

    # ── record coupon usage ──
    if coupon:
        CouponUsage.objects.create(coupon=coupon, user=request.user, order=order)
        coupon.used_count += 1
        coupon.save(update_fields=['used_count'])

    cart.items.all().delete()

    # ── Razorpay: redirect to payment page instead of success ──
    if payment_method == 'online':
        return redirect('orders:razorpay_payment', order_id=order.order_id)

    return redirect('orders:order_success', order_id=order.order_id)


# ── RAZORPAY ──────────────────────────────────────────────────────

@login_required
def razorpay_payment(request, order_id):
    """Show the Razorpay payment page."""
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    if order.payment_status == 'paid':
        return redirect('orders:order_success', order_id=order.order_id)

    try:
        import razorpay
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        rz_order = client.order.create({
            'amount':   int(float(order.total) * 100),  # paise
            'currency': 'INR',
            'receipt':  order.order_id,
            'payment_capture': 1,
        })
        order.razorpay_order_id = rz_order['id']
        order.save(update_fields=['razorpay_order_id'])
    except Exception as e:
        messages.error(request, f"Payment gateway error: {e}")
        return redirect('orders:payment_failed', order_id=order.order_id)

    return render(request, 'orders/razorpay_payment.html', {
        'order':           order,
        'RAZORPAY_KEY_ID': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': order.razorpay_order_id,
        'amount_paise':      int(float(order.total) * 100),
    })
@csrf_exempt
@require_POST
def razorpay_callback(request):
    print("=== RAZORPAY CALLBACK ===")
    print("POST:", dict(request.POST))
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_order_id   = request.POST.get('razorpay_order_id', '')
    razorpay_signature  = request.POST.get('razorpay_signature', '')

    if request.POST.get('error[code]') or request.POST.get('error[description]'):
        # Extract order_id from error metadata
        import json as _json
        try:
            metadata = _json.loads(request.POST.get('error[metadata]', '{}'))
            rz_order_id = metadata.get('order_id', '')
            order = Order.objects.get(razorpay_order_id=rz_order_id)
            order.payment_status = 'failed'
            order.save(update_fields=['payment_status', 'updated_at'])
            return redirect('orders:payment_failed', order_id=order.order_id)
        except Exception:
            return redirect('orders:order_list')

    if not razorpay_order_id:
        return redirect('orders:order_list')

    try:
        order = Order.objects.get(razorpay_order_id=razorpay_order_id)
    except Order.DoesNotExist:
        return redirect('orders:order_list')

    # If no payment ID or signature — payment was cancelled/failed
    if not razorpay_payment_id or not razorpay_signature:
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status', 'updated_at'])
        return redirect('orders:payment_failed', order_id=order.order_id)

    try:
        import razorpay
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        client.utility.verify_payment_signature({
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        })

        order.razorpay_payment_id = razorpay_payment_id
        order.payment_status      = 'paid'
        order.status              = 'confirmed'
        order.save(update_fields=['razorpay_payment_id', 'payment_status', 'status', 'updated_at'])
        return redirect('orders:order_success', order_id=order.order_id)

    except Exception as e:
        print("Signature error:", e)
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status', 'updated_at'])
        return redirect('orders:payment_failed', order_id=order.order_id)
@login_required
def payment_failed(request, order_id):
    """Payment failure page with retry option."""
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/payment_failed.html', {'order': order})


@login_required
@require_POST
def retry_payment(request, order_id):
    """Re-initiate Razorpay payment for a failed order."""
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if order.payment_status == 'paid':
        return redirect('orders:order_success', order_id=order.order_id)
    return redirect('orders:razorpay_payment', order_id=order.order_id)




@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/order-success.html', {'order': order})


# ── ORDER LIST / DETAIL ───────────────────────────────────────────

@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user)
    q = request.GET.get('q', '').strip()
    if q:
        orders = orders.filter(
            Q(order_id__icontains=q) | Q(items__product_name__icontains=q)
        ).distinct()
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    return render(request, 'orders/order-list.html', {
        'orders':         orders.order_by('-created_at'),
        'q':              q,
        'status_filter':  status_filter,
        'status_choices': Order.STATUS_CHOICES,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/order-detail.html', {'order': order})


# ── CANCEL ORDER ─────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if not order.can_cancel:
        return JsonResponse({'error': 'This order cannot be cancelled.'}, status=400)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = ''

    for item in order.items.filter(status='active'):
        if item.variant:
            item.variant.stock += item.quantity
            item.variant.save(update_fields=['stock'])
        item.status       = 'cancelled'
        item.cancel_reason= reason
        item.cancelled_at = timezone.now()
        item.save()

    order.status = 'cancelled'
    order.save(update_fields=['status', 'updated_at'])

    # ── Wallet refund for prepaid orders ──
    refund_amount = order.refund_amount()
    if refund_amount > 0:
        wallet = _get_wallet(request.user)
        wallet.credit(
            refund_amount,
            description=f"Refund for cancelled order {order.order_id}",
            order=order,
        )
        return JsonResponse({
            'success': True,
            'message': f'Order cancelled. ₹{refund_amount:.0f} refunded to your wallet.',
            'refunded': True,
            'refund_amount': refund_amount,
        })

    return JsonResponse({'success': True, 'message': 'Order cancelled successfully.', 'refunded': False})


# ── CANCEL ITEM ───────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def cancel_item(request, order_id, item_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    item  = get_object_or_404(OrderItem, id=item_id, order=order)

    if not order.can_cancel or item.status != 'active':
        return JsonResponse({'error': 'This item cannot be cancelled.'}, status=400)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = ''

    if item.variant:
        item.variant.stock += item.quantity
        item.variant.save(update_fields=['stock'])

    item.status       = 'cancelled'
    item.cancel_reason= reason
    item.cancelled_at = timezone.now()
    item.save()

    # If all items cancelled → cancel the order too
    if not order.items.filter(status='active').exists():
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])

    # ── Proportional wallet refund for prepaid orders ──
    refund_amount = 0
    if order.payment_method in ('online', 'wallet'):
        refund_amount = float(item.subtotal())
        wallet = _get_wallet(request.user)
        wallet.credit(
            refund_amount,
            description=f"Refund for cancelled item '{item.product_name}' in order {order.order_id}",
            order=order,
        )

    return JsonResponse({
        'success':      True,
        'message':      'Item cancelled successfully.',
        'refunded':     refund_amount > 0,
        'refund_amount': refund_amount,
    })


# ── RETURN ORDER ──────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def return_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if not order.can_return:
        return JsonResponse({'error': 'This order is not eligible for return.'}, status=400)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = request.POST.get('reason', '').strip()

    if not reason:
        return JsonResponse({'error': 'A reason is required for returns.'}, status=400)

    for item in order.items.filter(status='active'):
        item.status        = 'return_requested'
        item.return_reason = reason
        item.save()

    order.status = 'return_requested'
    order.save(update_fields=['status', 'updated_at'])

    return JsonResponse({'success': True, 'message': 'Return request submitted. We will process it shortly.'})


# ── WALLET PAGE ───────────────────────────────────────────────────

@login_required
def wallet_page(request):
    wallet       = _get_wallet(request.user)
    transactions = wallet.transactions.select_related('order').all()[:50]
    return render(request, 'orders/wallet.html', {
        'wallet':       wallet,
        'transactions': transactions,
    })


# ── INVOICE DOWNLOAD ──────────────────────────────────────────────

@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    try:
        from io import BytesIO
        from reportlab.lib              import colors
        from reportlab.lib.pagesizes    import A4
        from reportlab.lib.styles       import ParagraphStyle
        from reportlab.lib.units        import mm
        from reportlab.platypus         import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        )

        buffer = BytesIO()
        doc    = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=20*mm, leftMargin=20*mm,
            topMargin=20*mm,   bottomMargin=20*mm
        )

        brand_style = ParagraphStyle('Brand', fontSize=28, fontName='Helvetica-Bold',
                                     textColor=colors.HexColor('#2a2520'), spaceAfter=2)
        sub_style   = ParagraphStyle('Sub', fontSize=9, fontName='Helvetica',
                                     textColor=colors.HexColor('#888888'), spaceAfter=4)
        h2_style    = ParagraphStyle('H2', fontSize=11, fontName='Helvetica-Bold',
                                     textColor=colors.HexColor('#2a2520'), spaceBefore=8, spaceAfter=4)
        body_style  = ParagraphStyle('Body', fontSize=9, fontName='Helvetica',
                                     textColor=colors.HexColor('#333333'), spaceAfter=2)
        small_style = ParagraphStyle('Small', fontSize=8, fontName='Helvetica',
                                     textColor=colors.HexColor('#888888'), spaceAfter=2)

        story = []
        story.append(Paragraph('ALAIA', brand_style))
        story.append(Paragraph('Architectural Footwear · Premium Collection', sub_style))
        story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#c9a96e'), spaceAfter=8))
        story.append(Paragraph('TAX INVOICE', h2_style))

        info_data  = [
            ['Order ID', order.order_id, 'Date', order.created_at.strftime('%d %b %Y')],
            ['Payment',  order.get_payment_method_display(), 'Status', order.get_status_display()],
        ]
        info_table = Table(info_data, colWidths=[35*mm, 65*mm, 25*mm, 45*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME',     (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME',     (0,0), (0,-1),  'Helvetica-Bold'),
            ('FONTNAME',     (2,0), (2,-1),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 9),
            ('TEXTCOLOR',    (0,0), (0,-1),  colors.HexColor('#888888')),
            ('TEXTCOLOR',    (2,0), (2,-1),  colors.HexColor('#888888')),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 8*mm))

        story.append(Paragraph('Ship To', h2_style))
        story.append(Paragraph(order.full_name, body_style))
        story.append(Paragraph(order.address_line1, body_style))
        if order.address_line2:
            story.append(Paragraph(order.address_line2, body_style))
        story.append(Paragraph(f"{order.city}, {order.state} — {order.postal_code}", body_style))
        story.append(Paragraph(order.country, body_style))
        story.append(Paragraph(f"Phone: {order.phone}", body_style))
        story.append(Spacer(1, 6*mm))

        story.append(Paragraph('Order Items', h2_style))
        rows = [['Product', 'Colour / Size', 'Qty', 'Unit Price', 'Subtotal']]
        for item in order.items.all():
            rows.append([
                item.product_name,
                f"{item.color.title()} / {item.size}",
                str(item.quantity),
                f"₹{item.unit_price:,.0f}",
                f"₹{item.subtotal():,.0f}",
            ])

        item_table = Table(rows, colWidths=[70*mm, 35*mm, 15*mm, 25*mm, 25*mm])
        item_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), colors.HexColor('#2a2520')),
            ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME',      (0,1), (-1,-1),'Helvetica'),
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('ALIGN',         (2,0), (-1,-1), 'RIGHT'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#fdfcfa')]),
            ('GRID',          (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
        ]))
        story.append(item_table)
        story.append(Spacer(1, 6*mm))

        total_data = [['', 'Subtotal', f"₹{order.subtotal:,.0f}"]]
        if float(order.discount) > 0:
            total_data.append(['', f'Discount ({order.coupon_code})', f"- ₹{order.discount:,.0f}"])
        total_data.append(['', 'Shipping',
                           f"₹{order.shipping:,.0f}" if float(order.shipping) > 0 else 'FREE'])
        total_data.append(['', 'TOTAL', f"₹{order.total:,.0f}"])

        tot_table = Table(total_data, colWidths=[100*mm, 40*mm, 30*mm])
        tot_table.setStyle(TableStyle([
            ('FONTNAME',  (1,-1),  (-1,-1), 'Helvetica-Bold'),
            ('FONTNAME',  (0,0),   (-1,-2), 'Helvetica'),
            ('FONTSIZE',  (0,0),   (-1,-1), 9),
            ('ALIGN',     (2,0),   (2,-1),  'RIGHT'),
            ('ALIGN',     (1,0),   (1,-1),  'RIGHT'),
            ('LINEABOVE', (1,-1),  (-1,-1), 1, colors.HexColor('#c9a96e')),
            ('TEXTCOLOR', (1,-1),  (-1,-1), colors.HexColor('#2a2520')),
            ('TOPPADDING',(0,-1),  (-1,-1), 6),
            ('FONTSIZE',  (1,-1),  (-1,-1), 11),
        ]))
        story.append(tot_table)
        story.append(Spacer(1, 10*mm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#dddddd')))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            'Thank you for choosing ALAIA. For returns or queries, contact support@alaia.com',
            small_style
        ))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="ALAIA-Invoice-{order.order_id}.pdf"'
        )
        return response

    except ImportError:
        return HttpResponse(
            f"PDF generation requires reportlab.\npip install reportlab\n\nOrder: {order.order_id}",
            content_type='text/plain'
        )


# ── WISHLIST ──────────────────────────────────────────────────────

@login_required
def wishlist_page(request):
    wishlist = _wishlist(request.user)
    items    = wishlist.items.select_related(
        'product', 'product__brand', 'product__category'
    ).prefetch_related('product__variants__images')

    in_cart = set()
    try:
        in_cart = set(request.user.cart.items.values_list('variant__product_id', flat=True))
    except Exception:
        pass

    return render(request, 'orders/wishlist.html', {
        'wishlist': wishlist,
        'items':    items,
        'in_cart':  in_cart,
    })


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    product  = get_object_or_404(Product, id=product_id, is_active=True, is_deleted=False)
    wishlist = _wishlist(request.user)

    cart = Cart.objects.filter(user=request.user).first()
    if cart and cart.items.filter(variant__product=product).exists():
        return JsonResponse({'success': False, 'message': 'Product already in cart.'})

    item = WishlistItem.objects.filter(wishlist=wishlist, product=product).first()
    if item:
        item.delete()
        added = False
    else:
        WishlistItem.objects.create(wishlist=wishlist, product=product)
        added = True

    return JsonResponse({
        'success': True,
        'added':   added,
        'count':   wishlist.items.count(),
        'message': 'Saved to wishlist' if added else 'Removed from wishlist',
    })


@login_required
def wishlist_status(request):
    wishlist = _wishlist(request.user)
    ids      = list(wishlist.items.values_list('product_id', flat=True))
    return JsonResponse({'product_ids': ids, 'count': len(ids)})


@login_required
@require_POST
def move_to_cart(request, product_id):
    product  = get_object_or_404(Product, id=product_id, is_active=True, is_deleted=False)
    wishlist = _wishlist(request.user)

    variant = product.variants.filter(is_deleted=False, stock__gt=0).order_by('price').first()
    if not variant:
        return JsonResponse({'error': 'No stock available for this product.'}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant,
        defaults={'quantity': 1, 'price_at_added': variant.final_price}
    )
    if not created:
        if cart_item.quantity + 1 > variant.stock:
            return JsonResponse({'error': 'Not enough stock.'}, status=400)
        cart_item.quantity      += 1
        cart_item.price_at_added = variant.final_price
        cart_item.save()

    WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()

    return JsonResponse({
        'success':    True,
        'message':    'Moved to cart.',
        'cart_count': cart.items.count(),
        'wish_count': wishlist.items.count(),
    })


@login_required
@require_POST
def remove_from_wishlist(request, product_id):
    wishlist = _wishlist(request.user)
    WishlistItem.objects.filter(wishlist=wishlist, product_id=product_id).delete()
    return JsonResponse({'success': True, 'count': wishlist.items.count()})


# ── CART ──────────────────────────────────────────────────────────

@require_POST
def add_to_cart(request, variant_id):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "login required"})

    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)
    if variant.stock <= 0:
        return JsonResponse({"success": False, "error": "out of stock"})

    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={"quantity": 1, "price_at_added": variant.final_price}
    )
    if not created:
        if cart_item.quantity + 1 > variant.stock:
            return JsonResponse({"success": False, "error": "not enough stock"})
        cart_item.quantity += 1
        cart_item.save()

    WishlistItem.objects.filter(
        wishlist__user=request.user, product=variant.product
    ).delete()

    return JsonResponse({"success": True})


def cart_view(request):
    if not request.user.is_authenticated:
        return redirect("account_login")

    cart, _ = Cart.objects.get_or_create(user=request.user)
    items   = cart.items.select_related(
        "variant", "variant__product", "variant__product__brand"
    ).prefetch_related("variant__images")

    total = sum(item.subtotal() for item in items)
    return render(request, "orders/cart.html", {"cart": cart, "items": items, "total": total})


def update_cart_quantity(request, item_id, action):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    variant   = cart_item.variant

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
    elif action == "remove":
        cart_item.delete()

    return redirect("orders:cart")