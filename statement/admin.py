from django.contrib import admin

from statement.models import InventoryStatement, InventoryStatementItem, ProductStockUpdate


@admin.register(ProductStockUpdate)
class ProductStockUpdateAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity_change', 'date', 'notes')
    list_filter = ('date', 'product')
    search_fields = ('product__name', 'notes')
    date_hierarchy = 'date'
    
class InventoryStatementItemInline(admin.TabularInline):
    model = InventoryStatementItem
    extra = 0
    readonly_fields = ['opening_stock', 'invoiced_stock', 'closing_stock', 'variance', 'remarks']
    fields = ['product', 'opening_stock', 'received_stock', 'invoiced_stock', 'closing_stock', 'variance', 'remarks']


@admin.register(InventoryStatement)
class InventoryStatementAdmin(admin.ModelAdmin):
    list_display = ['date', 'prepared_by', 'company_name']
    list_filter = ['date', 'prepared_by']
    search_fields = ['company_name', 'prepared_by', 'notes']
    date_hierarchy = 'date'
    inlines = [InventoryStatementItemInline]
    actions = ['regenerate_statements']
    
    def regenerate_statements(self, request, queryset):
        item_count = 0
        statement_count = queryset.count()
        
        for statement in queryset:
            item_count += statement.generate_statement_items()
            
        self.message_user(request, f"Regenerated {item_count} inventory items across {statement_count} statements.")
    
    regenerate_statements.short_description = "Regenerate inventory statements for selected dates"


@admin.register(InventoryStatementItem)
class InventoryStatementItemAdmin(admin.ModelAdmin):
    list_display = ['product', 'inventory_statement', 'opening_stock', 'received_stock', 'invoiced_stock', 'closing_stock', 'variance', 'remarks']
    list_filter = ['inventory_statement__date', 'remarks']
    search_fields = ['product__name', 'remarks']
    readonly_fields = ['opening_stock', 'invoiced_stock', 'closing_stock', 'variance', 'remarks']
    
    def has_add_permission(self, request):
        return False  # Prevent adding individual items directly