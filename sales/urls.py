from django.urls import path
from .views import sale_create, sale_list, sale_detail, generate_receipt


urlpatterns = [
     # Sale URLs
    path('sales/create/', sale_create, name='sale_create'),
    path('sales/', sale_list, name='sale_list'),
    path('sales/<int:sale_id>/', sale_detail, name='sale_detail'),
    path('sales/<int:sale_id>/receipt/', generate_receipt, name='generate_receipt'),
]
