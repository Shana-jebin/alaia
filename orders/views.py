from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from products.models import Cart, CartItem, Coupon
from accounts.models import Address
from .models import Order, OrderItem

import json


@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related(
        'variant', 'variant__product', 'variant__product__brand'
    ).prefetch_related('variant__images')

    valid_items = []
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
        return redirect('products:cart')

    if blocked_names:
        messages.warning(request, f"Removed unavailable items: {', '.join(blocked_names)}")

    subtotal = sum(item.variant.final_price * item.quantity for item in valid_items)
    shipping = 0 if subtotal >= 2999 else 99
    total = subtotal + shipping

    addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created_at')
    default_address = addresses.filter(is_default=True).first() or addresses.first()

    now = timezone.now()
    product_ids = [i.variant.product_id for i in valid_items]
    category_ids = [i.variant.product.category_id for i in valid_items]
    coupons = Coupon.objects.filter(
        Q(products__id__in=product_ids) | Q(categories__id__in=category_ids),
        is_active=True, valid_from__lte=now, valid_to__gte=now,
        min_order__lte=subtotal,
    ).distinct()

    return render(request, 'orders/checkout.html', {
        'items': valid_items, 'addresses': addresses,
        'default_address': default_address,
        'subtotal': subtotal, 'shipping': shipping,
        'total': total, 'coupons': coupons,
    })


@login_required
def apply_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    code = data.get('code', '').strip().upper()
    subtotal = float(data.get('subtotal', 0))
    now = timezone.now()

    try:
        coupon = Coupon.objects.get(code__iexact=code, is_active=True,
                                    valid_from__lte=now, valid_to__gte=now)
    except Coupon.DoesNotExist:
        return JsonResponse({'error': 'Invalid or expired coupon code.'}, status=400)

    if subtotal < float(coupon.min_order):
        return JsonResponse({'error': f'Minimum order of Rs.{coupon.min_order:.0f} required.'}, status=400)

    discount = round(subtotal * float(coupon.discount_value) / 100, 2) if coupon.discount_type == 'percent' else float(coupon.discount_value)
    discount = min(discount, subtotal)

    return JsonResponse({'success': True, 'discount': discount, 'code': coupon.code,
                         'message': f'Coupon applied! You saved Rs.{discount:.0f}'})


@login_required
@transaction.atomic
def place_order(request):
    if request.method != 'POST':
        return redirect('orders:checkout')

    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related('variant', 'variant__product', 'variant__product__brand').prefetch_related('variant__images')

    address_id = request.POST.get('address_id')
    payment_method = request.POST.get('payment_method', 'cod')
    coupon_code = request.POST.get('coupon_code', '').strip().upper()

    address = get_object_or_404(Address, id=address_id, user=request.user)

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
        return redirect('products:cart')

    subtotal = sum(item.variant.final_price * item.quantity for item in valid_items)
    shipping = 0 if subtotal >= 2999 else 99
    discount = 0

    if coupon_code:
        now = timezone.now()
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, is_active=True,
                                        valid_from__lte=now, valid_to__gte=now,
                                        min_order__lte=subtotal)
            discount = round(float(subtotal) * float(coupon.discount_value) / 100, 2) if coupon.discount_type == 'percent' else float(coupon.discount_value)
            discount = min(discount, float(subtotal))
        except Coupon.DoesNotExist:
            pass

    total = float(subtotal) + float(shipping) - float(discount)

    order = Order.objects.create(
        user=request.user,
        full_name=address.full_name, address_line1=address.address_line1,
        address_line2=address.address_line2 or '', city=address.city,
        state=address.state, postal_code=address.postal_code,
        country=address.country, phone=address.phone,
        payment_method=payment_method, subtotal=subtotal,
        discount=discount, shipping=shipping, total=total,
        coupon_code=coupon_code,
    )

    for item in valid_items:
        v = item.variant
        img = v.images.first()
        OrderItem.objects.create(
            order=order, variant=v,
            product_name=v.product.name, brand_name=v.product.brand.name,
            color=v.color, size=v.size,
            image_url=img.image.url if img else '',
            quantity=item.quantity, unit_price=v.final_price,
        )
        v.stock -= item.quantity
        v.save(update_fields=['stock'])

    cart.items.all().delete()
    return redirect('orders:order_success', order_id=order.order_id)


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/order_success.html', {'order': order})


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user)
    q = request.GET.get('q', '').strip()
    if q:
        orders = orders.filter(Q(order_id__icontains=q) | Q(items__product_name__icontains=q)).distinct()
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    return render(request, 'orders/order_list.html', {
        'orders': orders.order_by('-created_at'),
        'q': q, 'status_filter': status_filter,
        'status_choices': Order.STATUS_CHOICES,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if not order.can_cancel:
        return JsonResponse({'error': 'This order cannot be cancelled.'}, status=400)
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = ''
    for item in order.items.filter(status='active'):
        if item.variant:
            item.variant.stock += item.quantity
            item.variant.save(update_fields=['stock'])
        item.status = 'cancelled'
        item.cancel_reason = reason
        item.cancelled_at = timezone.now()
        item.save()
    order.status = 'cancelled'
    order.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'success': True, 'message': 'Order cancelled successfully.'})


@login_required
@require_POST
def cancel_item(request, order_id, item_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    item = get_object_or_404(OrderItem, id=item_id, order=order)
    if not order.can_cancel or item.status != 'active':
        return JsonResponse({'error': 'This item cannot be cancelled.'}, status=400)
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = ''
    if item.variant:
        item.variant.stock += item.quantity
        item.variant.save(update_fields=['stock'])
    item.status = 'cancelled'
    item.cancel_reason = reason
    item.cancelled_at = timezone.now()
    item.save()
    if not order.items.filter(status='active').exists():
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'success': True, 'message': 'Item cancelled successfully.'})


@login_required
@require_POST
def return_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    if not order.can_return:
        return JsonResponse({'error': 'This order is not eligible for return.'}, status=400)
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
    except Exception:
        reason = request.POST.get('reason', '').strip()
    if not reason:
        return JsonResponse({'error': 'A reason is required for returns.'}, status=400)
    for item in order.items.filter(status='active'):
        item.status = 'return_requested'
        item.return_reason = reason
        item.save()
    order.status = 'return_requested'
    order.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'success': True, 'message': 'Return request submitted successfully.'})


@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from io import BytesIO

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)

        styles = getSampleStyleSheet()
        brand_style = ParagraphStyle('Brand', fontSize=28, fontName='Helvetica-Bold', textColor=colors.HexColor('#2a2520'), spaceAfter=2)
        sub_style = ParagraphStyle('Sub', fontSize=9, fontName='Helvetica', textColor=colors.HexColor('#888888'), spaceAfter=4)
        h2_style = ParagraphStyle('H2', fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#2a2520'), spaceBefore=8, spaceAfter=4)
        body_style = ParagraphStyle('Body', fontSize=9, fontName='Helvetica', textColor=colors.HexColor('#333333'), spaceAfter=2)
        small_style = ParagraphStyle('Small', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#888888'), spaceAfter=2)

        story = []
        story.append(Paragraph('ALAIA', brand_style))
        story.append(Paragraph('Architectural Footwear · Premium Collection', sub_style))
        story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#c9a96e'), spaceAfter=8))
        story.append(Paragraph('TAX INVOICE', h2_style))

        info_data = [
            ['Order ID', order.order_id, 'Date', order.created_at.strftime('%d %b %Y')],
            ['Payment', order.get_payment_method_display(), 'Status', order.get_status_display()],
        ]
        info_table = Table(info_data, colWidths=[35*mm, 65*mm, 25*mm, 45*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#888888')),
            ('TEXTCOLOR', (2,0), (2,-1), colors.HexColor('#888888')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
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
            rows.append([item.product_name, f"{item.color.title()} / {item.size}", str(item.quantity), f"Rs.{item.unit_price:,.0f}", f"Rs.{item.subtotal():,.0f}"])

        item_table = Table(rows, colWidths=[70*mm, 35*mm, 15*mm, 25*mm, 25*mm])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2a2520')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fdfcfa')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(item_table)
        story.append(Spacer(1, 6*mm))

        total_data = [['', 'Subtotal', f"Rs.{order.subtotal:,.0f}"]]
        if float(order.discount) > 0:
            total_data.append(['', f'Discount ({order.coupon_code})', f"- Rs.{order.discount:,.0f}"])
        total_data.append(['', 'Shipping', f"Rs.{order.shipping:,.0f}" if float(order.shipping) > 0 else 'FREE'])
        total_data.append(['', 'TOTAL', f"Rs.{order.total:,.0f}"])

        tot_table = Table(total_data, colWidths=[100*mm, 40*mm, 30*mm])
        tot_table.setStyle(TableStyle([
            ('FONTNAME', (1,-1), (-1,-1), 'Helvetica-Bold'),
            ('FONTNAME', (0,0), (-1,-2), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('LINEABOVE', (1,-1), (-1,-1), 1, colors.HexColor('#c9a96e')),
            ('TEXTCOLOR', (1,-1), (-1,-1), colors.HexColor('#2a2520')),
            ('TOPPADDING', (0,-1), (-1,-1), 6),
            ('FONTSIZE', (1,-1), (-1,-1), 11),
        ]))
        story.append(tot_table)
        story.append(Spacer(1, 10*mm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#dddddd')))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('Thank you for choosing ALAIA. For returns or queries, contact support@alaia.com', small_style))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="ALAIA-Invoice-{order.order_id}.pdf"'
        return response

    except ImportError:
        return HttpResponse(f"PDF generation requires reportlab.\nRun: pip install reportlab\n\nOrder: {order.order_id}", content_type='text/plain')