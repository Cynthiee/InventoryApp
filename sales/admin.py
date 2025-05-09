from django.contrib import admin
from sales.models import Sale, SaleItem

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
