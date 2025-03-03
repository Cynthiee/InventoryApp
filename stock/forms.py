from django import forms
from .models import Category, Product, RegularSale, BulkSale
from django.utils.text import slugify

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise forms.ValidationError('This field is required.')
        
        # Convert name to lowercase for case-insensitive comparison
        name_lower = name.lower()
        
        # Exclude current instance when editing
        query = Category.objects.filter(name__iexact=name_lower)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
            
        if query.exists():
            raise forms.ValidationError(f'Category "{name}" already exists.')
        return name
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = slugify(instance.name)
        if commit:
            instance.save()
        return instance

class ProductCreateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Select existing category'
        })
    )
    
    new_category = forms.CharField(
        max_length=200, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Or create new category',
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = Product
        fields = [
            'category', 'name', 'regular_price', 
            'bulk_price', 'quantity', 'minimum_bulk_quantity', 
            'restock_level', 'available'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Product name'
            }),
            'regular_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '0.01'
            }),
            'bulk_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '0.01'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'restock_level': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'help_text': 'Minimum quantity before restock alert'
            }),
            'minimum_bulk_quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '12',
                'help_text': 'Minimum quantity required for bulk pricing'
            }),
            'available': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category = cleaned_data.get('new_category')
        regular_price = cleaned_data.get('regular_price')
        bulk_price = cleaned_data.get('bulk_price')
        quantity = cleaned_data.get('quantity')
        restock_level = cleaned_data.get('restock_level')
        minimum_bulk_quantity = cleaned_data.get('minimum_bulk_quantity')
        
        # Validate category
        if not category and not new_category:
            raise forms.ValidationError('Please either select an existing category or create a new one.')
        
        if new_category:
            existing_category = Category.objects.filter(name__iexact=new_category).first()
            if existing_category:
                cleaned_data['category'] = existing_category
                cleaned_data['new_category'] = ''
            else:
                try:
                    new_cat = Category.objects.create(
                        name=new_category,
                        slug=slugify(new_category)
                    )
                    cleaned_data['category'] = new_cat
                    cleaned_data['new_category'] = ''
                except Exception as e:
                    raise forms.ValidationError(f'Error creating new category: {str(e)}')
        
        # Validate prices
        if bulk_price and regular_price and bulk_price > regular_price:
            raise forms.ValidationError('Bulk price cannot be greater than regular price.')
        
        # Validate quantities
        if quantity is not None and quantity < 0:
            raise forms.ValidationError('Quantity cannot be negative.')
            
        if restock_level is not None and restock_level < 0:
            raise forms.ValidationError('Restock level cannot be negative.')
        
        if minimum_bulk_quantity is not None and minimum_bulk_quantity < 12:
            raise forms.ValidationError('Minimum bulk quantity must be at least 12.')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = slugify(instance.name)
        
        # Check if a product with the same name and category already exists
        existing_product = Product.objects.filter(name=instance.name, category=instance.category).first()
        
        if existing_product:
            # Update the existing product's quantity and other fields
            existing_product.quantity += instance.quantity
            existing_product.regular_price = instance.regular_price
            existing_product.bulk_price = instance.bulk_price
            existing_product.minimum_bulk_quantity = instance.minimum_bulk_quantity
            existing_product.restock_level = instance.restock_level
            existing_product.available = instance.available
            if commit:
                existing_product.save()
            return existing_product
        else:
            # Save the new product
            if commit:
                instance.save()
            return instance

class SaleBaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(available=True)

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        product = self.cleaned_data.get('product')
        
        if product and quantity:
            if quantity > product.quantity:
                raise forms.ValidationError("Not enough products in stock.")
        return quantity

class RegularSaleForm(SaleBaseForm):
    class Meta:
        model = RegularSale
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            })
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.price_per_unit = instance.product.regular_price
        if commit:
            instance.save()
            # Update product quantity
            instance.product.quantity -= instance.quantity
            instance.product.save()
        return instance

class BulkSaleForm(SaleBaseForm):
    class Meta:
        model = BulkSale
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '12'
            })
        }

    def clean_quantity(self):
        quantity = super().clean_quantity()
        product = self.cleaned_data.get('product')
        
        if product and quantity:
            if quantity < product.minimum_bulk_quantity:
                raise forms.ValidationError(
                    f"Minimum {product.minimum_bulk_quantity} items required for bulk purchase."
                )
        return quantity

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.bulk_price_per_unit = instance.product.bulk_price
        if commit:
            instance.save()
            # Update product quantity
            instance.product.quantity -= instance.quantity
            instance.product.save()
        return instance

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
            'placeholder': 'Search by product name o'
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