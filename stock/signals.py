from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.timezone import now
from .models import ProductStockUpdate, Sale, InventoryStatement, SaleItem, Product
from django.db.models import Sum
import logging

logger = logging.getLogger(__name__)

# Create a flag to prevent signal recursion
inventory_update_in_progress = False

@receiver(post_save, sender=Sale)
def update_inventory_statement(sender, instance, created, **kwargs):
    global inventory_update_in_progress
    
    # Prevent signal recursion
    if inventory_update_in_progress:
        return
        
    today = now().date()
    if instance.sale_date.date() == today:
        try:
            inventory_update_in_progress = True
            
            # Get or create today's statement
            statement, _ = InventoryStatement.objects.get_or_create(date=today)
            
            # Use more efficient queries with subqueries where possible
            statement.total_income = Sale.objects.filter(sale_date__date=today).aggregate(total=Sum('total_amount'))['total'] or 0
            statement.total_products_sold = SaleItem.objects.filter(sale__sale_date__date=today).aggregate(total=Sum('quantity'))['total'] or 0
            statement.total_products_in_stock = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0
            
            # Only update the necessary fields
            statement.save(update_fields=['total_income', 'total_products_sold', 'total_products_in_stock'])
            
            # Generate statement items asynchronously if possible
            # You could use a task queue like Celery for this
            statement.generate_statement_items()
            
        finally:
            inventory_update_in_progress = False


@receiver(pre_save, sender=Product)
def track_quantity_change(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            quantity_change = instance.quantity - old_instance.quantity
            if quantity_change != 0:
                ProductStockUpdate.objects.create(
                    product=instance,
                    quantity_change=quantity_change,
                    notes=f"Quantity updated from {old_instance.quantity} to {instance.quantity}"
                )
        except Product.DoesNotExist:
            logger.error(f"Product with ID {instance.pk} does not exist.")
        except Exception as e:
            logger.error(f"Error tracking quantity change for product {instance.name}: {str(e)}")