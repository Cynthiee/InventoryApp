from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from .models import ProductStockUpdate, InventoryStatement, InventoryStatementItem
from products.models import Product
from sales.models import Sale, SaleItem
from django.db.models import Sum
import logging

logger = logging.getLogger(__name__)

# Create a flag to prevent signal recursion
inventory_update_in_progress = False
product_update_in_progress = False

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


@receiver(post_save, sender=Product)
def update_product_in_statements(sender, instance, **kwargs):
    """Update inventory statement items when a product is updated"""
    global product_update_in_progress
    
    # Prevent signal recursion
    if product_update_in_progress:
        return
    
    try:
        product_update_in_progress = True
        
        # Find all inventory statement items related to this product
        statement_items = InventoryStatementItem.objects.filter(product=instance)
        
        for item in statement_items:
            # Update closing stock
            item.closing_stock = instance.quantity
            
            # Recalculate opening stock based on the relationship:
            # opening_stock = closing_stock + invoiced_stock - received_stock
            item.opening_stock = item.closing_stock + item.invoiced_stock - item.received_stock
            
            # Update remarks based on product's needs_restock flag
            if item.variance != 0:
                item.remarks = "Variance detected"
            elif instance.needs_restock or instance.quantity <= instance.restock_level:
                item.remarks = "Restock needed"
            else:
                item.remarks = "Normal"
                
            # Save the item without triggering other signals
            item.save()
            
            # Update the parent statement totals
            statement = item.inventory_statement
            statement.total_products_in_stock = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0
            statement.save(update_fields=['total_products_in_stock'])
            
    except Exception as e:
        logger.error(f"Error updating inventory statement items for product {instance.name}: {str(e)}")
    finally:
        product_update_in_progress = False