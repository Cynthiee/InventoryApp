from django.db import models
from django.db.models import Sum
from datetime import datetime, time
from products.models import Product
from sales.models import SaleItem

class ProductStockUpdate(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_updates')
    date = models.DateField(auto_now_add=True)
    quantity_change = models.IntegerField(help_text="Positive for received stock, negative for sold stock.")
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity_change} on {self.date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update product quantity after saving stock update
        if self.quantity_change != 0:
            self.product.update_quantity(self.quantity_change)

class InventoryStatement(models.Model):
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
        constraints = [models.UniqueConstraint(fields=['date'], name='unique_daily_statement')]

    def __str__(self):
        return f"Inventory Statement - {self.date}"

    def generate_statement_items(self):
        today = self.date
        self.items.all().delete()
        products = Product.objects.all()

        for product in products:
            closing_stock = product.quantity
            today_start = datetime.combine(today, time.min)
            today_end = datetime.combine(today, time.max)

            # Get invoiced stock (sold items)
            from sales.models import SaleItem
            invoiced_stock = SaleItem.objects.filter(
                sale__sale_date__gte=today_start,
                sale__sale_date__lte=today_end,
                product=product
            ).aggregate(total_sold=Sum('quantity'))['total_sold'] or 0

      
            received_stock = ProductStockUpdate.objects.filter(
                product=product,
                date__range=(today_start.date(), today_end.date()),  # safer than exact match
                quantity_change__gt=0
            ).aggregate(total_received=Sum('quantity_change'))['total_received'] or 0

            opening_stock = closing_stock + invoiced_stock - received_stock
            variance = 0

            if variance != 0:
                remarks = "Variance detected"
            elif product.needs_restock or closing_stock <= product.restock_level:
                remarks = "Restock needed"
            else:
                remarks = "Normal"

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


    def refresh_items(self):
        """Refresh all inventory statement items based on current product data"""
        items = self.items.select_related('product').all()
        
        for item in items:
            product = item.product
            
            # Update closing stock to match current product quantity
            item.closing_stock = product.quantity
            
            # Keep the relationship: opening_stock + received_stock - invoiced_stock = closing_stock
            # So recalculate opening stock based on this
            item.opening_stock = item.closing_stock + item.invoiced_stock - item.received_stock
            
            # Update remarks based on product state
            if item.variance != 0:
                item.remarks = "Variance detected"
            elif product.needs_restock or product.quantity <= product.restock_level:
                item.remarks = "Restock needed"
            else:
                item.remarks = "Normal"
                
            item.save()
            
        # Update statement totals
        self.total_products_in_stock = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0
        self.save(update_fields=['total_products_in_stock'])
        
        return items.count()

class InventoryStatementItem(models.Model):
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

    def save(self, *args, update_product=False, **kwargs):
        """
        Save the inventory statement item. If update_product is True,
        also update the related product's quantity.
        """
        if self.pk:
            orig = InventoryStatementItem.objects.get(pk=self.pk)
            if orig.received_stock != self.received_stock:
                self.closing_stock = self.opening_stock + self.received_stock - self.invoiced_stock
                
                # Update product quantity if requested
                if update_product and self.product.quantity != self.closing_stock:
                    quantity_change = self.closing_stock - self.product.quantity
                    self.product.update_quantity(quantity_change)
                
                # Update remarks based on product state
                if self.variance != 0:
                    self.remarks = "Variance detected"
                elif self.product.needs_restock or self.closing_stock <= self.product.restock_level:
                    self.remarks = "Restock needed"
                else:
                    self.remarks = "Normal"
        else:
            self.closing_stock = self.opening_stock + self.received_stock - self.invoiced_stock
            
        super().save(*args, **kwargs)