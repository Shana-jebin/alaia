from django import forms
from accounts.models import Address

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "full_name",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "phone",
        ]
