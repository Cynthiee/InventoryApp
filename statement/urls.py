from django.urls import path
from .views import (inventory_statement_list, create_inventory_statement,
                   inventory_statement_detail, regenerate_inventory_statement,
                   export_inventory_statement_csv, export_inventory_statement_pdf)

urlpatterns = [
path('inventory/', inventory_statement_list, name='inventory_statement_list'),
    path('inventory/create/', create_inventory_statement, name='create_inventory_statement'),
    path('inventory/<int:statement_id>/', inventory_statement_detail, name='inventory_statement_detail'),
    path('inventory/<int:statement_id>/regenerate/', regenerate_inventory_statement, name='regenerate_inventory_statement'),
    path('inventory/<int:statement_id>/export/csv/', export_inventory_statement_csv, name='export_inventory_statement_csv'),
    path('inventory/<int:statement_id>/export/pdf/', export_inventory_statement_pdf, name='export_inventory_statement_pdf'),
]