from django.contrib import admin

# admin.py
from django.contrib import admin
from .models import Product, ProductVariant, VariantImage, Category, Brand


class VariantImageInline(admin.TabularInline):
    model = VariantImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'brand', 'is_active', 'is_featured', 'is_deleted', 'created_at']
    list_filter = ['is_active', 'is_featured', 'is_deleted', 'category', 'brand']
    search_fields = ['name', 'description']
    inlines = [ProductVariantInline]
    readonly_fields = ['deleted_at', 'created_at', 'updated_at']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'rating')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'color', 'size', 'price', 'stock', 'is_deleted']
    inlines = [VariantImageInline]
