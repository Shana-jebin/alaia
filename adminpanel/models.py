from django.db import models
from django.utils import timezone
from django.db.models import Min


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    description = models.TextField(blank=True, null=True)
    offer_percentage = models.PositiveIntegerField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    



class Brand(models.Model):
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    is_active = models.BooleanField(default=True)

    @property
    def product_count(self):
        return self.products.count()

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    brand = models.ForeignKey(
    Brand,
    on_delete=models.CASCADE,
    related_name='products'
)


    OCCASION_CHOICES = [
    ('casual', 'Casual'),
    ('office', 'Office'),
    ('party', 'Party'),
    ('wedding', 'Wedding'),
]

    occasion = models.CharField(
    max_length=20,
    choices=OCCASION_CHOICES,
    blank=True
)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)


    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    @property
    def total_stock(self):
        return sum(v.stock for v in self.variants.filter(is_deleted=False))

    @property
    def base_price(self):
        return self.variants.filter(
        is_deleted=False,
        stock__gt=0
    ).aggregate(min_price=Min('price'))['min_price'] or 0


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color = models.CharField(max_length=100)
    size = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sales_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color', 'size'],
                name='unique_variant_per_product'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.color} / {self.size}"

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class VariantImage(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/variants/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.variant}"







