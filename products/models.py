from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ValidationError

from django.conf import settings

#  CATEGORY

class Category(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    is_deleted  = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    offer_percentage = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



#  BRAND

class Brand(models.Model):
    name      = models.CharField(max_length=100, unique=True)
    slug      = models.SlugField(unique=True, blank=True)
    logo      = models.ImageField(upload_to='brands/', blank=True, null=True)
    rating    = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



#  PRODUCT MANAGER  (hide deleted by default)

class ProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    

class Occasion(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name



class Product(models.Model):

    OCCASION_CHOICES = [
        ('casual',   'Casual'),
        ('formal',   'Formal'),
        ('sports',   'Sports'),
        ('party',    'Party'),
        ('wedding',  'Wedding'),
        ('ethnic',   'Ethnic'),
        ('beach',    'Beach'),
        ('office',   'Office'),
        ('outdoor',  'Outdoor'),
        ('festive',  'Festive'),
    ]

    name        = models.CharField(max_length=200)
    slug        = models.SlugField(unique=True, blank=True)
    description = models.TextField()

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='products'
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name='products'
    )

    occasions = models.ManyToManyField(Occasion, blank=True, related_name="products")
    is_active  = models.BooleanField(default=True)   
    is_featured= models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  
    deleted_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # default manager hides deleted; use all_objects to see everything
    objects     = ProductManager()
    all_objects = models.Manager()

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            n = 1
            while Product.all_objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    # ── Helpers used in templates ──────────
    @property
    def total_stock(self):
        return sum(v.stock for v in self.variants.filter(is_deleted=False))

    @property
    def min_price(self):
        prices = [v.final_price for v in self.variants.filter(is_deleted=False)]
        return min(prices) if prices else 0
    

    @property
    def unique_colors(self):
        return list(
            self.variants.filter(is_deleted=False, stock__gt=0)
            .values_list('color', flat=True)
            .distinct()
        )

    @property
    def unique_sizes(self):
        return list(
            self.variants.filter(is_deleted=False, stock__gt=0)
            .values_list('size', flat=True)
            .distinct()
        )

    def __str__(self):
        return self.name



#  PRODUCT VARIANT

class ProductVariant(models.Model):

    COLOR_CHOICES = [
        ('black',    'Black'),
        ('white',    'White'),
        ('nude',     'Nude'),
        ('beige',    'Beige'),
        ('brown',    'Brown'),
        ('tan',      'Tan'),
        ('gold',     'Gold'),
        ('silver',   'Silver'),
        ('rose_gold','Rose Gold'),
        ('maroon',   'Maroon'),
        ('navy',     'Navy'),
        ('olive',    'Olive'),
        ('peach',    'Peach'),
    ]

    product     = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color       = models.CharField(max_length=50, choices=COLOR_CHOICES)
    size        = models.CharField(max_length=10)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    sales_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock       = models.PositiveIntegerField(default=0)
    is_deleted  = models.BooleanField(default=False)


    @property
    def final_price(self):

        base_price = self.price

        # Variant sale price
        variant_price = self.sales_price if self.sales_price else base_price

        # Category offer only if category is active and not deleted
        category = self.product.category

        if category and category.is_active and not category.is_deleted and category.offer_percentage > 0:
            category_price = base_price - (base_price * category.offer_percentage / 100)
        else:
            category_price = base_price

        return min(variant_price, category_price)


    @property
    def discount_percentage(self):
        final = self.final_price
        if final < self.price:
            return round(((self.price - final) / self.price) * 100)
        return 0

    def clean(self):
        errors = {}
       
        if self.price is None or self.price <= 0:
            errors['price'] = "Price must be greater than 0."
    
        if self.sales_price is not None:

            if self.sales_price <= 0:
                errors['sales_price'] = "Sale price must be greater than 0."

            elif self.price and self.sales_price >= self.price:
                errors['sales_price'] = "Sale price must be less than regular price."

        if errors:
            raise ValidationError(errors)
            

    def save(self, *args, **kwargs):
        self.full_clean()   # this triggers clean()
        super().save(*args, **kwargs)


    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(sales_price__lt=models.F('price')) | models.Q(sales_price__isnull=True),
                name='sales_price_less_than_price'
            )
        ]

    def __str__(self):
        return f"{self.product.name} — {self.color} / {self.size}"




#  VARIANT IMAGE

class VariantImage(models.Model):
    variant    = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image      = models.ImageField(upload_to='variants/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.variant}"
    




class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart - {self.user.email}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)


    price_at_added = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.price_at_added * self.quantity

    def __str__(self):
        return f"{self.variant} x {self.quantity}"
    



# ── REVIEW ──────────────────────────────────────────────────────────
from django.contrib.auth import get_user_model
User = get_user_model()

class Review(models.Model):
    product     = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating      = models.PositiveSmallIntegerField()   # 1–5
    comment     = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    is_rejected = models.BooleanField(default=False)

    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} → {self.product.name} ({self.rating}★)"



    

class Coupon(models.Model):
    DISCOUNT_TYPES = [
        ('percent', 'Percentage (%)'),
        ('flat',    'Flat Amount (Rs.)'),
    ]

    code           = models.CharField(max_length=50, unique=True)
    description    = models.TextField(blank=True)
    discount_type  = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='percent')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_order      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_from     = models.DateTimeField()
    valid_to       = models.DateTimeField()
    usage_limit    = models.PositiveIntegerField(null=True, blank=True)
    used_count     = models.PositiveIntegerField(default=0)
    per_user_limit = models.PositiveIntegerField(default=1)
    is_one_time    = models.BooleanField(default=False)
    is_active      = models.BooleanField(default=True)
    products       = models.ManyToManyField(Product,  blank=True, related_name='coupons')
    categories     = models.ManyToManyField(Category, blank=True, related_name='coupons')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    @property
    def status(self):
        now = timezone.now()
        if not self.is_active:
            return 'inactive'
        if self.valid_from > now:
            return 'scheduled'
        if self.valid_to < now:
            return 'expired'
        if self.usage_limit and self.used_count >= self.usage_limit:
            return 'exhausted'
        return 'active'

    @property
    def is_valid(self):
        return self.status == 'active'

    def compute_discount(self, subtotal):
        subtotal = float(subtotal)
        if subtotal <= 0:
            return 0.0
        if self.discount_type == 'percent':
            disc = subtotal * float(self.discount_value) / 100
            if self.max_discount:
                disc = min(disc, float(self.max_discount))
        else:
            disc = float(self.discount_value)
        return round(min(disc, subtotal), 2)

    @property
    def usage_percent(self):
        if not self.usage_limit:
            return 0
        return min(round(self.used_count / self.usage_limit * 100), 100)