from django import forms
from django.forms import inlineformset_factory
from .models import Category, Product, Sale, SaleItem, InventoryStatement, InventoryStatementItem
from django.utils.text import slugify
from django.utils import timezone

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name').strip()
        if Category.objects.exclude(pk=self.instance.pk).filter(name__iexact=name).exists():
            raise forms.ValidationError(f'Category "{name}" already exists.')
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = slugify(instance.name)
        if commit:
            instance.save()
        return instance


class ProductCreateForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False)
    new_category = forms.CharField(max_length=200, required=False)

    class Meta:
        model = Product
        fields = ['category', 'name', 'regular_price', 'bulk_price', 'quantity', 'minimum_bulk_quantity', 'restock_level', 'available']

    def clean(self):
        cleaned_data = super().clean()
        category, new_category = cleaned_data.get('category'), cleaned_data.get('new_category')
        
        if not category and not new_category:
            raise forms.ValidationError('Select an existing category or create a new one.')
        
        if cleaned_data.get('bulk_price') > cleaned_data.get('regular_price'):
            raise forms.ValidationError('Bulk price cannot be greater than regular price.')
        
        if cleaned_data.get('minimum_bulk_quantity', 12) < 12:
            raise forms.ValidationError('Minimum bulk quantity must be at least 12.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = slugify(instance.name)
        
        if new_category := self.cleaned_data.get('new_category'):
            instance.category, _ = Category.objects.get_or_create(name=new_category, defaults={'slug': slugify(new_category)})
        
        # Update existing product or create a new one
        existing_product = Product.objects.filter(name=instance.name, category=instance.category).first()
        if existing_product:
            existing_product.quantity += instance.quantity
            for field in ['regular_price', 'bulk_price', 'minimum_bulk_quantity', 'restock_level', 'available']:
                setattr(existing_product, field, getattr(instance, field))
            if commit:
                existing_product.save()
            return existing_product
        
        if commit:
            instance.save()
        return instance

            
class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['user']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
        }


class SaleItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(quantity__gt=0)
        self.fields['product'].widget.attrs.update({
            'data-regular-price': lambda p: str(p.regular_price),
            'data-bulk-price': lambda p: str(p.bulk_price),
        })

    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'sale_type']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'sale_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        product = self.cleaned_data.get('product')
        
        if product and quantity:
            if quantity > product.quantity:
                raise forms.ValidationError("Not enough products in stock.")
            if self.cleaned_data.get('sale_type') == 'bulk' and quantity < product.minimum_bulk_quantity:
                raise forms.ValidationError(
                    f"Minimum {product.minimum_bulk_quantity} items required for bulk purchase."
                )
        return quantity

    def save(self, commit=True):
        """
        Override save method to update product stock.
        """
        sale_item = super().save(commit=False)
        
        # Reduce stock only when a new SaleItem is created
        if commit:
            sale_item.product.quantity -= sale_item.quantity
            sale_item.product.save()
            sale_item.save()
        
        return sale_item


SaleItemFormSet = inlineformset_factory(Sale, SaleItem, form=SaleItemForm, extra=1, can_delete=True)

class SearchProductCategory(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    search_term = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by product name'
        })
    )
    available_only = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    needs_restock = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class InventoryStatementForm(forms.ModelForm):
    """Form for creating and updating inventory statements"""
    
    class Meta:
        model = InventoryStatement
        fields = ['company_name', 'prepared_by', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        

class InventoryStatementItemForm(forms.ModelForm):
    """Form for updating inventory statement items"""
    
    class Meta:
        model = InventoryStatementItem
        fields = ['received_stock']
        widgets = {
            'received_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
        }
    
    def clean_received_stock(self):
        received_stock = self.cleaned_data.get('received_stock')
        if received_stock < 0:
            raise forms.ValidationError("Received stock cannot be negative")
        return received_stock


# Create a formset for updating received stock for multiple items at once
InventoryStatementItemFormSet = inlineformset_factory(
    InventoryStatement, 
    InventoryStatementItem,
    form=InventoryStatementItemForm,
    extra=0,
    can_delete=False
)