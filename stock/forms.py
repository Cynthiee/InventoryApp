from django import forms
from django.db import IntegrityError, transaction
from django.forms import ValidationError, inlineformset_factory
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
        fields = ['category', 'name', 'regular_price', 'bulk_price', 'dozen_price', 
                 'quantity', 'quantity_per_carton', 'minimum_bulk_quantity', 
                 'restock_level', 'available']

    def clean(self):
        cleaned_data = super().clean()
        category, new_category = cleaned_data.get('category'), cleaned_data.get('new_category')
        
        if not category and not new_category:
            raise forms.ValidationError('Select an existing category or create a new one.')
        
        if cleaned_data.get('bulk_price') > cleaned_data.get('regular_price'):
            raise forms.ValidationError('Bulk price cannot be greater than regular price.')
            
        # CHANGE THIS CONDITION:
        if cleaned_data.get('dozen_price') <= cleaned_data.get('regular_price'):
            raise forms.ValidationError('Dozen price must be greater than regular price.')
        
        if cleaned_data.get('minimum_bulk_quantity', 0) < 0:
            raise forms.ValidationError('Minimum bulk quantity cannot be negative.')

        if cleaned_data.get('quantity_per_carton', 0) < 0:
            raise forms.ValidationError('Quantity per carton cannot be negative.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle category
        if new_category := self.cleaned_data.get('new_category'):
            # Get or create the category as part of the same transaction
            instance.category, _ = Category.objects.get_or_create(
                name=new_category, 
                defaults={'slug': slugify(new_category)}
            )
            
        # Generate slug for the product
        instance.slug = slugify(instance.name)
        
        # Using a single approach to handle duplicates - find or create
        # This leverages the database constraints rather than explicit locking
        try:
            existing_product = None
            if instance.category:
                existing_product = Product.objects.filter(
                    name=instance.name,
                    category=instance.category
                ).first()
                
            if existing_product:
                # Update existing product
                old_quantity = existing_product.quantity
                for field in self.Meta.fields:
                    if field != 'quantity':  # Skip quantity as we'll handle it specially
                        setattr(existing_product, field, getattr(instance, field))
                
                # Add the new quantity to the existing quantity
                existing_product.quantity = old_quantity + instance.quantity
                
                # Mark this as an update operation
                existing_product._updated = True
                
                if commit:
                    existing_product.save(form_edit=True)
                return existing_product
            else:
                # Create new product
                if commit:
                    instance.save(form_edit=True)
                return instance
        except Exception as e:
            # Let the view handle this exception
            raise


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['seller_name']  # Use the new field
        widgets = {
            'seller_name': forms.TextInput(attrs={'class': 'form-control', 'id': 'seller_name'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seller_name'].label = "Seller Name"
        self.fields['seller_name'].required = True


class SaleItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(quantity__gt=0)
        self.fields['product'].widget.attrs.update({
            'data-regular-price': lambda p: str(p.regular_price),
            'data-bulk-price': lambda p: str(p.bulk_price),
            'data-dozen-price': lambda p: str(p.dozen_price),
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
            if quantity <= 0:
                raise forms.ValidationError("Quantity must be greater than zero.")
            # Don't check against product.quantity here - we'll do it at save time
            if self.cleaned_data.get('sale_type') == 'bulk' and quantity < product.minimum_bulk_quantity:
                raise forms.ValidationError(
                    f"Minimum {product.minimum_bulk_quantity} items required for bulk purchase."
                )
        return quantity

    @transaction.atomic
    def save(self, commit=True):
        """
        Override save method to update product stock with proper locking.
        """
        sale_item = super().save(commit=False)
        
        # Only process new sale items, not updates
        if not sale_item.pk and commit:
            # Lock the product for update to prevent race conditions
            try:
                # Get the latest product data with a lock
                product = Product.objects.select_for_update().get(pk=sale_item.product.pk)
                
                # Verify again that there's enough stock
                if product.quantity < sale_item.quantity:
                    raise ValidationError(f"Not enough stock for {product.name}. Available: {product.quantity}")
                
                # Set the correct price based on sale type
                if not sale_item.price_per_unit:
                    if sale_item.sale_type == 'bulk':
                        sale_item.price_per_unit = product.bulk_price
                    elif sale_item.sale_type == 'dozen':
                        sale_item.price_per_unit = product.dozen_price
                    else:
                        sale_item.price_per_unit = product.regular_price
                
                # Use the product's update_quantity method to safely reduce stock
                product.update_quantity(-sale_item.quantity)
                
                # Save the sale item
                sale_item.save()
                
                # Update the sale's total
                if sale_item.sale:
                    sale_item.sale.update_total_amount()
                
            except Product.DoesNotExist:
                raise ValidationError("The selected product is no longer available.")
            
        elif commit:
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