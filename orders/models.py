import random
import string
from django.db import models
from django.conf import settings
from products.models import ProductVariant


def generate_order_id():
    """Generate a unique readable order ID like ALAIA-20240315-A3F9B2"""
    from django.utils import timezone
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    date_str = timezone.now().strftime('%Y%m%d')
    return f"ALAIA-{date_str}-{suffix}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',          'Pending'),
        ('confirmed',        'Confirmed'),
        ('shipped',          'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered',        'Delivered'),
        ('cancelled',        'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('returned',         'Returned'),
    ]

    PAYMENT_CHOICES = [
        ('cod',    'Cash on Delivery'),
        ('online', 'Online Payment'),
        ('wallet', 'Wallet'),
    ]

    order_id        = models.CharField(max_length=30, unique=True, editable=False)
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    # Address snapshot at time of order
    full_name       = models.CharField(max_length=150)
    address_line1   = models.CharField(max_length=255)
    address_line2   = models.CharField(max_length=255, blank=True)
    city            = models.CharField(max_length=100)
    state           = models.CharField(max_length=100)
    postal_code     = models.CharField(max_length=20)
    country         = models.CharField(max_length=100)
    phone           = models.CharField(max_length=20)

    payment_method  = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cod')
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    subtotal        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total           = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    coupon_code     = models.CharField(max_length=50, blank=True)
    notes           = models.TextField(blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_id:
            oid = generate_order_id()
            while Order.objects.filter(order_id=oid).exists():
                oid = generate_order_id()
            self.order_id = oid
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_id} — {self.user.email}"

    @property
    def can_cancel(self):
        return self.status in ('pending', 'confirmed')

    @property
    def can_return(self):
        return self.status == 'delivered'

    @property
    def active_items(self):
        return self.items.filter(status='active')

    @property
    def status_step(self):
        """Returns 1-5 for progress bar; cancelled/returned = 0"""
        steps = {
            'pending': 1,
            'confirmed': 2,
            'shipped': 3,
            'out_for_delivery': 4,
            'delivered': 5,
        }
        return steps.get(self.status, 0)


class OrderItem(models.Model):
    ITEM_STATUS_CHOICES = [
        ('active',           'Active'),
        ('cancelled',        'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('returned',         'Returned'),
    ]

    order           = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant         = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Snapshots so we keep info even if product is deleted
    product_name    = models.CharField(max_length=200)
    brand_name      = models.CharField(max_length=100, blank=True)
    color           = models.CharField(max_length=50)
    size            = models.CharField(max_length=10)
    image_url       = models.CharField(max_length=500, blank=True)

    quantity        = models.PositiveIntegerField()
    unit_price      = models.DecimalField(max_digits=10, decimal_places=2)

    status          = models.CharField(
        max_length=20, choices=ITEM_STATUS_CHOICES, default='active'
    )
    cancel_reason   = models.TextField(blank=True)
    return_reason   = models.TextField(blank=True)
    cancelled_at    = models.DateTimeField(null=True, blank=True)

    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


# ── WISHLIST ──────────────────────────────────────────────────────
from products.models import Product as _Product


class Wishlist(models.Model):
    user       = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wishlist — {self.user.email}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(_Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'product')
        ordering        = ['-added_at']

    def __str__(self):
        return f"{self.product.name} → {self.wishlist.user.email}"