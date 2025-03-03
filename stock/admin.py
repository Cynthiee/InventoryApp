from django.contrib import admin  
from .models import Category, Product, RegularSale, BulkSale, InventoryStatement  

@admin.register(Category)  
class CategoryAdmin(admin.ModelAdmin):  
    list_display = ('name', 'slug')  
    prepopulated_fields = {'slug': ('name',)}  
    search_fields = ('name',)  
    ordering = ('name',)  


@admin.register(Product)  
class ProductAdmin(admin.ModelAdmin):  
    list_display = ('name', 'category', 'regular_price', 'bulk_price', 'quantity', 'restock_level', 'minimum_bulk_quantity', 'needs_restock', 'created', 'updated')  
    list_filter = ('category', 'created', 'updated', 'needs_restock')  
    search_fields = ('name',)  
    prepopulated_fields = {'slug': ('name',)}  
    ordering = ('name',)  
    readonly_fields = ('needs_restock',)  


@admin.register(RegularSale)  
class RegularSaleAdmin(admin.ModelAdmin):  
    list_display = ('product', 'quantity', 'price_per_unit', 'total_amount', 'sale_date', 'seller', 'created', 'updated')  
    list_filter = ('sale_date', 'created', 'updated')  
    search_fields = ('product__name',)  
    ordering = ('-sale_date',)  


@admin.register(BulkSale)  
class BulkSaleAdmin(admin.ModelAdmin):  
    list_display = ('product', 'quantity', 'bulk_price_per_unit', 'total_amount', 'sale_date', 'seller', 'created', 'updated')  
    list_filter = ('sale_date', 'created', 'updated')  
    search_fields = ('product__name',)  
    ordering = ('-sale_date',)  


@admin.register(InventoryStatement)  
class InventoryStatementAdmin(admin.ModelAdmin):  
    list_display = ('date', 'total_income', 'total_products_sold', 'total_products_in_stock')  
    list_filter = ('date',)  
    ordering = ('-date',)  
    readonly_fields = ('total_income', 'total_products_sold', 'total_products_in_stock')  

    def has_add_permission(self, request):  
        """Prevent manual addition of inventory statements."""  
        return False