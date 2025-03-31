from datetime import timezone
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models import Sum, F
from django.db.models.signals import pre_delete
from django.utils.timezone import now
from datetime import datetime, time

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
    dozen_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)], default=0,
                                     help_text="Price when purchasing a dozen of this product.")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    quantity_per_carton = models.PositiveIntegerField(default=0, 
                                                     help_text="Number of items contained in one carton (constant).")
    minimum_bulk_quantity = models.IntegerField(default=0, help_text="Minimum quantity required for bulk pricing.")
    restock_level = models.IntegerField(validators=[MinValueValidator(0)], default=0, help_text="Minimum quantity before restock is needed.")
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
        # Ensure quantity is a plain integer before comparison
        if self.pk and not form_edit:
            # Get the raw numerical value if this is an existing object
            current_quantity = Product.objects.filter(pk=self.pk).values_list('quantity', flat=True).first()
            if current_quantity is not None:
                self.quantity = current_quantity
        
        # Now we can safely compare
        self.needs_restock = self.quantity <= self.restock_level
        self.clean()
        super().save(*args, **kwargs)

    def update_quantity(self, amount, save=True):
        """Safely update product quantity using F expressions to avoid race conditions"""
        Product.objects.filter(pk=self.pk).update(quantity=F('quantity') + amount)
        # Refresh from db to get the updated quantity
        self.refresh_from_db()
        
        # Update needs_restock directly in the database to avoid F expression issues
        current_quantity = Product.objects.filter(pk=self.pk).values_list('quantity', flat=True).first()
        needs_restock = current_quantity <= self.restock_level
        Product.objects.filter(pk=self.pk).update(needs_restock=needs_restock)
        
        # Refresh again to get the updated values
        self.refresh_from_db(fields=['quantity'])
        return self.quantity


class Sale(models.Model):
    seller_name = models.CharField(max_length=200,null=True, blank=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0)
    sale_date = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sale {self.id} - User {self.user}"

    def update_total_amount(self):
        """Update total amount using database aggregation"""
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
    # Add field to store the custom minimum bulk quantity if set
    custom_bulk_minimum = models.PositiveIntegerField(null=True, blank=True, 
                                                    help_text="Custom minimum bulk quantity for this sale item")

    def clean(self):
        """Validate the sale item before saving."""
        from django.core.exceptions import ValidationError
        
        # First check if product exists
        if not self.product:
            return
        
        # Now check if quantity exists and is a valid number
        if self.quantity is None:
            raise ValidationError("Quantity cannot be empty.")
        
        # Determine the effective minimum bulk quantity
        effective_min_bulk_qty = self.product.minimum_bulk_quantity
        if self.custom_bulk_minimum is not None and self.custom_bulk_minimum > 0:
            if self.custom_bulk_minimum < self.product.minimum_bulk_quantity:
                raise ValidationError(
                    f"Custom bulk minimum ({self.custom_bulk_minimum}) cannot be less than the product's default minimum ({self.product.minimum_bulk_quantity})."
                )
            effective_min_bulk_qty = self.custom_bulk_minimum
        
        # Validate based on sale type
        if self.sale_type == 'bulk' and self.quantity < effective_min_bulk_qty:
            raise ValidationError(f"Minimum {effective_min_bulk_qty} items required for bulk purchase.")
    
    @property
    def total_price(self):
        """Calculate the total price for this item."""
        return self.quantity * self.price_per_unit

    def __str__(self):
        """String representation of the sale item."""
        return f"{self.quantity} x {self.product.name} ({self.sale_type})"


class ProductStockUpdate(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_updates')
    date = models.DateField(auto_now_add=True)
    quantity_change = models.IntegerField(help_text="Positive for received stock, negative for sold stock.")
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity_change} on {self.date}"
    

class InventoryStatement(models.Model):
    """Daily inventory statement"""
    date = models.DateField(unique=True)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    prepared_by = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    total_income = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_products_sold = models.PositiveIntegerField(default=0)
    total_products_in_stock = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Inventory Statement'
        verbose_name_plural = 'Inventory Statements'
        constraints = [
            models.UniqueConstraint(fields=['date'], name='unique_daily_statement')
        ]
    
    def __str__(self):
        return f"Inventory Statement - {self.date}"
    
    def generate_statement_items(self):
        """Generate or update inventory statement items with the latest data."""
        today = self.date
        
        # Delete existing statement items for this date to avoid duplicates
        self.items.all().delete()
        
        # Get all products
        products = Product.objects.all()
        
        for product in products:
            # For a daily statement, we'll use the actual product quantities
            
            # The current quantity is the closing stock
            closing_stock = product.quantity
            
            # Calculate invoiced stock (total quantity sold on this date)
            today_start = datetime.combine(today, time.min)
            today_end = datetime.combine(today, time.max)
            
            invoiced_stock = SaleItem.objects.filter(
                sale__sale_date__gte=today_start,
                sale__sale_date__lte=today_end,
                product=product
            ).aggregate(total_sold=Sum('quantity'))['total_sold'] or 0
            
            # Calculate received stock from ProductStockUpdate records
            received_stock = ProductStockUpdate.objects.filter(
                product=product,
                date=today,  # Use date directly
                quantity_change__gt=0  # Only consider positive changes (received stock)
            ).aggregate(total_received=Sum('quantity_change'))['total_received'] or 0
            
            # Calculate opening stock
            opening_stock = closing_stock + invoiced_stock - received_stock
            
            # Calculate variance (difference between actual and calculated closing stock)
            variance = 0  # For now, we assume no variance
            
            # Determine remarks based on variance or stock levels
            if variance != 0:
                remarks = "Variance detected"
            elif closing_stock <= product.restock_level:
                remarks = "Restock needed"
            else:
                remarks = "Normal"
            
            # Create inventory statement item
            InventoryStatementItem.objects.create(
                inventory_statement=self,
                product=product,
                opening_stock=opening_stock,
                received_stock=received_stock,
                invoiced_stock=invoiced_stock,
                closing_stock=closing_stock,
                variance=variance,
                remarks=remarks
            )
        
        return self.items.count()


class InventoryStatementItem(models.Model):
    """Individual line item in an inventory statement"""
    inventory_statement = models.ForeignKey(InventoryStatement, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    opening_stock = models.PositiveIntegerField(default=0)
    received_stock = models.PositiveIntegerField(default=0)
    invoiced_stock = models.PositiveIntegerField(default=0)
    closing_stock = models.PositiveIntegerField(default=0)
    variance = models.IntegerField(default=0)
    remarks = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['product__name']
        verbose_name = 'Inventory Statement Item'
        verbose_name_plural = 'Inventory Statement Items'
    
    def __str__(self):
        return f"{self.product.name} - {self.inventory_statement.date}"
    
    def save(self, *args, **kwargs):
        # If received_stock is manually updated, recalculate closing stock
        if self.pk:
            orig = InventoryStatementItem.objects.get(pk=self.pk)
            if orig.received_stock != self.received_stock:
                # Update closing stock based on the new received stock value
                self.closing_stock = self.opening_stock + self.received_stock - self.invoiced_stock
        else:
            # For new items, closing stock = opening_stock + received_stock - invoiced_stock
            self.closing_stock = self.opening_stock + self.received_stock - self.invoiced_stock
        
        super().save(*args, **kwargs)