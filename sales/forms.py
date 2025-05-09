from django import forms
from django.db import transaction
from django.forms import inlineformset_factory, ValidationError
from products.models import Product
from .models import Sale, SaleItem

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['seller_name']
        widgets = {
            'seller_name': forms.TextInput(attrs={'class': 'form-control', 'id': 'seller_name'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seller_name'].label = "Seller Name"
        self.fields['seller_name'].required = True


class SaleItemForm(forms.ModelForm):
    custom_bulk_minimum = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'placeholder': 'Default minimum'
        }),
        help_text="Optional: Override minimum bulk quantity (cannot be less than product default)"
    )

    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'sale_type', 'custom_bulk_minimum']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'sale_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(quantity__gt=0)

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        sale_type = cleaned_data.get('sale_type')
        custom_bulk_minimum = cleaned_data.get('custom_bulk_minimum')

        if not all([product, quantity, sale_type]):
            return cleaned_data

        effective_min_bulk_qty = product.minimum_bulk_quantity
        if custom_bulk_minimum is not None and custom_bulk_minimum > 0:
            if custom_bulk_minimum < product.minimum_bulk_quantity:
                raise forms.ValidationError(
                    f"Custom bulk minimum ({custom_bulk_minimum}) cannot be less than the product's default minimum ({product.minimum_bulk_quantity})."
                )
            effective_min_bulk_qty = custom_bulk_minimum

        if sale_type == 'bulk' and quantity < effective_min_bulk_qty:
            raise forms.ValidationError(
                f"Minimum {effective_min_bulk_qty} items required for bulk purchase."
            )

        return cleaned_data

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        product = self.cleaned_data.get('product')
        if product and quantity and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity

    @transaction.atomic
    def save(self, commit=True):
        sale_item = super().save(commit=False)
        custom_bulk_minimum = self.cleaned_data.get('custom_bulk_minimum')

        if not sale_item.pk and commit:
            try:
                product = Product.objects.select_for_update().get(pk=sale_item.product.pk)

                if product.quantity < sale_item.quantity:
                    raise ValidationError(f"Not enough stock for {product.name}. Available: {product.quantity}")

                if not sale_item.price_per_unit:
                    if sale_item.sale_type == 'bulk':
                        sale_item.price_per_unit = product.bulk_price
                    elif sale_item.sale_type == 'dozen':
                        sale_item.price_per_unit = product.dozen_price
                    else:
                        sale_item.price_per_unit = product.regular_price

                product.update_quantity(-sale_item.quantity)
                sale_item.save()

                if sale_item.sale:
                    sale_item.sale.update_total_amount()

            except Product.DoesNotExist:
                raise ValidationError("The selected product is no longer available.")

        elif commit:
            sale_item.save()

        return sale_item


SaleItemFormSet = inlineformset_factory(Sale, SaleItem, form=SaleItemForm, extra=1, can_delete=True)
