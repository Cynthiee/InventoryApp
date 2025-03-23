from django.contrib import admin
from .models import Category, Product, Sale, SaleItem, InventoryStatement, InventoryStatementItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'regular_price', 'bulk_price', 'dozen_price', 'quantity', 'quantity_per_carton', 'restock_level', 'minimum_bulk_quantity', 'needs_restock', 'created', 'updated')
    list_filter = ('category', 'created', 'updated', 'needs_restock')
    search_fields = ('name', 'category__name')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)
    readonly_fields = ('needs_restock',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'sale_date', 'created', 'updated')
    list_filter = ('sale_date', 'created', 'updated')
    search_fields = ('user__username', 'id')
    ordering = ('-sale_date',)


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'product', 'quantity', 'sale_type', 'price_per_unit', 'total_price_display')
    list_filter = ('sale_type',)
    search_fields = ('product__name', 'sale__id')

    @admin.display(description="Total Price")
    def total_price_display(self, obj):
        return f"${obj.total_price:.2f}" if hasattr(obj, 'total_price') else "N/A"


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