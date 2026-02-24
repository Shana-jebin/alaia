from django import forms
from .models import Product, ProductVariant, VariantImage, Category, Brand


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'brand', 'occasion', 'is_active', 'is_featured']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter product name', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'placeholder': 'Enter product description', 'class': 'form-input', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'brand': forms.Select(attrs={'class': 'form-input'}),
            'occasion': forms.TextInput(attrs={'placeholder': 'e.g. Casual, Formal, Sports', 'class': 'form-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False



class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['color', 'size', 'price', 'sales_price', 'stock']
        widgets = {
            'color': forms.TextInput(attrs={'placeholder': 'e.g. Midnight Blue', 'class': 'form-input'}),
            'size': forms.TextInput(attrs={'placeholder': 'e.g. 42', 'class': 'form-input'}),
            'price': forms.NumberInput(attrs={'placeholder': '0.00', 'class': 'form-input', 'step': '0.01'}),
            'sales_price': forms.NumberInput(attrs={'placeholder': 'Optional', 'class': 'form-input', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'placeholder': '0', 'class': 'form-input'}),
        }


VariantImageFormSet = forms.inlineformset_factory(
    ProductVariant,
    VariantImage,
    fields=['image', 'is_primary'],
    extra=1,
    can_delete=True,
)