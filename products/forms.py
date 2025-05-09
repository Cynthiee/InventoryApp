from django import forms
from django.utils.text import slugify
from .models import Category, Product

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
        fields = [
            'category', 'name', 'regular_price', 'bulk_price', 'dozen_price',
            'quantity', 'quantity_per_carton', 'minimum_bulk_quantity',
            'restock_level', 'available'
        ]

    def clean(self):
        cleaned_data = super().clean()
        category, new_category = cleaned_data.get('category'), cleaned_data.get('new_category')
        
        if not category and not new_category:
            raise forms.ValidationError('Select an existing category or create a new one.')

        if cleaned_data.get('bulk_price') > cleaned_data.get('regular_price'):
            raise forms.ValidationError('Bulk price cannot be greater than regular price.')

        if cleaned_data.get('minimum_bulk_quantity', 0) < 0:
            raise forms.ValidationError('Minimum bulk quantity cannot be negative.')

        if cleaned_data.get('quantity_per_carton', 0) < 0:
            raise forms.ValidationError('Quantity per carton cannot be negative.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if new_category := self.cleaned_data.get('new_category'):
            instance.category, _ = Category.objects.get_or_create(
                name=new_category,
                defaults={'slug': slugify(new_category)}
            )

        instance.slug = slugify(instance.name)

        try:
            existing_product = None
            if instance.category:
                existing_product = Product.objects.filter(
                    name=instance.name,
                    category=instance.category
                ).first()

            if existing_product:
                old_quantity = existing_product.quantity
                for field in self.Meta.fields:
                    if field != 'quantity':
                        setattr(existing_product, field, getattr(instance, field))
                existing_product.quantity = old_quantity + instance.quantity
                existing_product._updated = True
                if commit:
                    existing_product.save(form_edit=True)
                return existing_product
            else:
                if commit:
                    instance.save(form_edit=True)
                return instance
        except Exception as e:
            raise


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
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    needs_restock = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
