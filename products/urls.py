from django.urls import path
from .views import category_list, product_list_by_category, product_list, product_detail, product_create, product_edit, product_delete, home


urlpatterns = [
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

]
