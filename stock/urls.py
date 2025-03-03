from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name='home'),
    path('category_list/', category_list, name='category_list'),
    path('categories/<int:category_id>/products/', product_list_by_category, name='product_list_by_category'),

    #Product URLs
    path('product_list/', product_list, name='product_list'),
    path('products/<slug:slug>/', product_detail, name='product_detail'),
    path('product_create/', product_create, name='product_create'),
    path('products/<slug:slug>/edit/', product_edit, name='product_edit'),
    path('products/<slug:slug>/delete/', product_delete, name='product_delete'),

 # Regular Sale URLs
    path('sales/regular/create/', regular_sale_create, name='regular_sale_create'),
    path('sales/regular/', regular_sale_list, name='regular_sale_list'),
    path('sales/regular/export/', export_regular_sales, name='export_regular_sales'),

    # Bulk Sale URLs
    path('sales/bulk/create/', bulk_sale_create, name='bulk_sale_create'),
    path('sales/bulk/', bulk_sale_list, name='bulk_sale_list'),
    path('sales/bulk/export/', export_bulk_sales, name='export_bulk_sales'),

    # Inventory Statement URLs
    path('statements/', statement_list, name='statement_list'),
    path('statements/<int:pk>/', statement_detail, name='statement_detail'),
    path('statements/export/', export_inventory_statements, name='export_inventory_statements'),

]
