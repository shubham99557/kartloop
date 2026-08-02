from django import forms
from .models import Product, DeliveryMethod, Address, Order, Review, ProductImage
from .models import Product, ProductVariant
from django.forms import inlineformset_factory

class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['size', 'stock']
        widgets = {
            'size': forms.Select(attrs={'class': 'form-select'}),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': 'Available stock'
            }),
        }

ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=1,
    can_delete=True
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'category',
            'mrp_price',       # Original cost / MRP
            'selling_price',   # Selling price for customers
            'brand',
            'description',
            'image'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product Name'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'mrp_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'MRP Price'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Selling Price'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brand Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Product Description', 'rows': 4}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    class Media:
        js = ('js/product_discount_preview.js',)  # Optional: if you move the JS to separate file

class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image']

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        exclude = ['user', 'is_default']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 1'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 2 (optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PIN Code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
        }

class CheckoutForm(forms.Form):
    use_saved_address = forms.BooleanField(required=False, initial=True, label="Use a saved address")

    saved_address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select from saved addresses"
    )

    full_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}))
    phone = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}))
    address_line1 = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 1'}))
    address_line2 = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 2 (Optional)'}))
    city = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}))
    state = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State'}))
    postal_code = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PIN Code'}))
    country = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}))

    delivery_method = forms.ModelChoiceField(
        queryset=DeliveryMethod.objects.all(),
        widget=forms.RadioSelect,
        label="Delivery Method"
    )

    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_CHOICES,
        widget=forms.RadioSelect,
        label="Payment Method"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['saved_address'].queryset = Address.objects.filter(user=user)

    def clean(self):
        cleaned_data = super().clean()
        use_saved = cleaned_data.get('use_saved_address')

        if use_saved:
            if not cleaned_data.get('saved_address'):
                self.add_error('saved_address', "Please select a saved address.")
        else:
            required_fields = ['full_name', 'phone', 'address_line1', 'city', 'state', 'postal_code', 'country']
            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, "This field is required.")

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'review', 'image']
        widgets = {
            'rating': forms.Select(choices=[(i, i) for i in range(5, 0, -1)], attrs={'class': 'form-select'}),
            'review': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Share your experience...', 'rows': 4}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
