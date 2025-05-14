from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models import Sum, F
from products.models import Product  # adjust import path as necessary

class Sale(models.Model):
    seller_name = models.CharField(max_length=200, null=True, blank=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)
    sale_date = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sale {self.id} - User {self.user}"

    def update_total_amount(self):
        total = self.items.aggregate(total=Sum(F('quantity') * F('price_per_unit')))['total'] or 0
        self.total_amount = total
        self.save(update_fields=['total_amount'])

class SaleItem(models.Model):
    SALE_TYPE_CHOICES = [
        ('regular', 'Regular'),
        ('bulk', 'Bulk'),
        ('dozen', 'Dozen'),
    ]

    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES, default='regular')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    custom_bulk_minimum = models.PositiveIntegerField(null=True, blank=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.product:
            return
        if self.quantity is None:
            raise ValidationError("Quantity cannot be empty.")
        # Only validate that custom minimum isn't less than product default
        if self.custom_bulk_minimum and self.custom_bulk_minimum < self.product.minimum_bulk_quantity:
            raise ValidationError(
                f"Custom bulk minimum ({self.custom_bulk_minimum}) cannot be less than default minimum ({self.product.minimum_bulk_quantity})."
            )
        
    @property
    def total_price(self):
        return self.quantity * self.price_per_unit

    def __str__(self):
        return f"{self.quantity} x {self.product.name} ({self.sale_type})"
