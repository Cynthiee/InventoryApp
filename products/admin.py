from django.contrib import admin
from products.models import Category, Product

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