from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.timezone import now
from .models import ProductStockUpdate, Sale, InventoryStatement, SaleItem, Product
from django.db.models import Sum

@receiver(post_save, sender=Sale)
def update_inventory_statement(sender, instance, created, **kwargs):
    today = now().date()

    # Use the correct field name (`date`) to filter by the date part
    statement, created = InventoryStatement.objects.get_or_create(date=today)
    
    # Only update these fields if necessary
    statement.total_income = Sale.objects.filter(sale_date__date=today).aggregate(total=Sum('total_amount'))['total'] or 0
    statement.total_products_sold = SaleItem.objects.filter(sale__sale_date__date=today).aggregate(total=Sum('quantity'))['total'] or 0
    statement.total_products_in_stock = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0

    # Use update_fields to only update these specific fields, not the date
    statement.save(update_fields=['total_income', 'total_products_sold', 'total_products_in_stock'])
    
    # Generate inventory statement items for the day
    statement.generate_statement_items()


@receiver(pre_save, sender=Product)
def track_quantity_change(sender, instance, **kwargs):
    """
    Track changes in the quantity field of the Product model.
    """
    if instance.pk:  # Only for existing products
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            quantity_change = instance.quantity - old_instance.quantity
            if quantity_change != 0:
                # Create a ProductStockUpdate record
                ProductStockUpdate.objects.create(
                    product=instance,
                    quantity_change=quantity_change,
                    notes=f"Quantity updated from {old_instance.quantity} to {instance.quantity}"
                )
        except Product.DoesNotExist:
            pass