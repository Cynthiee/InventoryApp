from django.db import models
from django.core.validators import MinValueValidator
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=200, blank=False)
    slug = models.SlugField(max_length=200, unique=True)

    class Meta:
        ordering = ['name'] 
        indexes = [models.Index(fields=['name'])]
        verbose_name = 'category'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, blank=False, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    bulk_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    dozen_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)], default=0)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    quantity_per_carton = models.PositiveIntegerField(default=0)
    minimum_bulk_quantity = models.IntegerField(default=0)
    restock_level = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    needs_restock = models.BooleanField(default=False)
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['id', 'slug']),
            models.Index(fields=['name']),
            models.Index(fields=['-created']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['category', 'name'], name='unique_product_per_category')
        ]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.bulk_price > self.regular_price:
            raise ValidationError("Bulk price cannot be greater than regular price.")

    def save(self, *args, form_edit=False, **kwargs):
        if self.pk and not form_edit:
            current_quantity = Product.objects.filter(pk=self.pk).values_list('quantity', flat=True).first()
            if current_quantity is not None:
                self.quantity = current_quantity
        self.needs_restock = self.quantity <= self.restock_level
        self.clean()
        super().save(*args, **kwargs)

    def update_quantity(self, amount, save=True):
        from django.db.models import F
        Product.objects.filter(pk=self.pk).update(quantity=F('quantity') + amount)
        self.refresh_from_db()
        current_quantity = Product.objects.filter(pk=self.pk).values_list('quantity', flat=True).first()
        needs_restock = current_quantity <= self.restock_level
        Product.objects.filter(pk=self.pk).update(needs_restock=needs_restock)
        self.refresh_from_db(fields=['quantity'])
        return self.quantity
