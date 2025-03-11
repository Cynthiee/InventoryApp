from django.urls import path
from .views import *

urlpatterns = [
    # Home URL
    path('', home, name='home'),

    # Category URLs
    path('category_list/', category_list, name='category_list'),
    path('categories/<int:category_id>/products/', product_list_by_category, name='product_list_by_category'),

    # Product URLs
    path('product_list/', product_list, name='product_list'),
    path('products/<slug:slug>/', product_detail, name='product_detail'),
    path('product_create/', product_create, name='product_create'),
    path('products/<slug:slug>/edit/', product_edit, name='product_edit'),
    path('products/<slug:slug>/delete/', product_delete, name='product_delete'),

    # Sale URLs
    path('sales/create/', sale_create, name='sale_create'),
    path('sales/', sale_list, name='sale_list'),
    # path('sales/export/', export_sales, name='export_sales'),
    path('sales/<int:sale_id>/', sale_detail, name='sale_detail'),
    path('sales/<int:sale_id>/receipt/', generate_receipt, name='generate_receipt'),

    # # Inventory Statement URLs
    path('inventory/', inventory_statement_list, name='inventory_statement_list'),
    path('inventory/create/', create_inventory_statement, name='create_inventory_statement'),
    path('inventory/<int:statement_id>/', inventory_statement_detail, name='inventory_statement_detail'),
    path('inventory/<int:statement_id>/regenerate/', regenerate_inventory_statement, name='regenerate_inventory_statement'),
    path('inventory/<int:statement_id>/export/csv/', export_inventory_statement_csv, name='export_inventory_statement_csv'),
    path('inventory/<int:statement_id>/export/pdf/', export_inventory_statement_pdf, name='export_inventory_statement_pdf'),
]