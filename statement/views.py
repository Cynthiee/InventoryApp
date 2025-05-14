from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponse
import csv
from .models import InventoryStatement
from .forms import InventoryStatementForm, InventoryStatementItemFormSet

# Inventory Statement Views
def inventory_statement_list(request):
    """View to list all inventory statements"""
    statements = InventoryStatement.objects.all()
    return render(request, 'statement/inventory_statement_list.html', {
        'statements': statements,
        'title': 'Inventory Statements'
    })

def create_inventory_statement(request):
    """View to create a new inventory statement."""
    today = timezone.now().date()
    existing_statement = InventoryStatement.objects.filter(date=today).first()
    
    if existing_statement:
        messages.info(request, f'An inventory statement for today ({today}) already exists.')
        return redirect('inventory_statement_detail', statement_id=existing_statement.id)
    
    if request.method == 'POST':
        form = InventoryStatementForm(request.POST)
        if form.is_valid():
            statement = form.save(commit=False)
            
            # Set default prepared_by if not provided
            if not statement.prepared_by and request.user.is_authenticated:
                statement.prepared_by = request.user.get_full_name() or request.user.username
            
            statement.save()
            
            # Generate inventory statement items
            item_count = statement.generate_statement_items()
            
            messages.success(request, f'Inventory statement for {statement.date} created with {item_count} items.')
            return redirect('inventory_statement_detail', statement_id=statement.id)
    else:
        form = InventoryStatementForm(initial={
            'date': today,
            'company_name': 'Your Company Name'  # Default company name
        })
    
    return render(request, 'statement/inventory_statement_form.html', {
        'form': form,
        'title': 'Create Inventory Statement'
    })

def inventory_statement_detail(request, statement_id):
    """View to display a detailed inventory statement."""
    statement = get_object_or_404(InventoryStatement, id=statement_id)
    
    # Keep your refresh logic
    if 'refresh' in request.GET:
        refreshed_count = statement.refresh_items()
        messages.success(request, f'Refreshed {refreshed_count} inventory items with current product data.')
        return redirect('inventory_statement_detail', statement_id=statement.id)
    
    # Generate statement items if needed
    if not statement.items.exists():
        statement.generate_statement_items()
    
    # Get all items
    items = statement.items.all()
    
    # Handle filtering
    filter_type = request.GET.get('filter')
    
    if filter_type == 'sold':
        display_items = items.filter(invoiced_stock__gt=0)
    elif filter_type == 'no_sales':
        display_items = items.filter(invoiced_stock=0)
    elif filter_type == 'restock':
        display_items = items.filter(remarks='Restock needed')
    elif filter_type == 'low_stock':
        display_items = items.filter(closing_stock__lte=10)
    else:
        display_items = items
        filter_type = None
    
    
    # Calculate totals
    item_totals = display_items.aggregate(
        total_opening=Sum('opening_stock'),
        total_received=Sum('received_stock'),
        total_invoiced=Sum('invoiced_stock'),
        total_closing=Sum('closing_stock'),
        total_variance=Sum('variance')
    )
    

    summary_totals = {
        'total_income': statement.total_income,
        'total_products_sold': statement.total_products_sold,
        'total_products_in_stock': statement.total_products_in_stock
    }
    
    return render(request, 'statement/inventory_statement_detail.html', {
        'statement': statement,
        'items': display_items,  # Just pass items directly
        'item_totals': item_totals,
        'summary_totals': summary_totals,
        'title': f'Inventory Statement: {statement.date}',
        'active_filter': filter_type
    })

def regenerate_inventory_statement(request, statement_id):
    """Regenerate inventory statement items"""
    statement = get_object_or_404(InventoryStatement, id=statement_id)
    
    if request.method == 'POST' or request.GET.get('confirm') == 'yes':
        # Regenerate all statement items
        item_count = statement.generate_statement_items()
        messages.success(request, f'Inventory statement regenerated with {item_count} items')
        return redirect('inventory_statement_detail', statement_id=statement.id)
    
    return render(request, 'inventory/regenerate_confirmation.html', {
        'statement': statement,
        'title': 'Regenerate Inventory Statement'
    })

def export_inventory_statement_csv(request, statement_id):
    """Export inventory statement as CSV"""
    statement = get_object_or_404(InventoryStatement, id=statement_id)
    items = statement.items.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="inventory_statement_{statement.date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Item Code', 'Item Name', 'Opening Stock', 'Received Stock', 
                     'Invoiced Stock', 'Closing Stock', 'Variance', 'Remarks'])
    
    for item in items:
        writer.writerow([
            item.product.id,
            item.product.name,
            item.opening_stock,
            item.received_stock,
            item.invoiced_stock,
            item.closing_stock,
            item.variance,
            item.remarks
        ])
    
    return response

def export_inventory_statement_pdf(request, statement_id):
    """Export inventory statement as PDF"""
    # This would require a PDF library like ReportLab or WeasyPrint
    # For now, we'll create a print-friendly HTML page that can be saved as PDF from the browser
    
    statement = get_object_or_404(InventoryStatement, id=statement_id)
    items = statement.items.all()
    
    # Calculate totals
    totals = items.aggregate(
        total_opening=Sum('opening_stock'),
        total_received=Sum('received_stock'),
        total_invoiced=Sum('invoiced_stock'),
        total_closing=Sum('closing_stock'),
        total_variance=Sum('variance')
    )
    
    return render(request, 'statement/inventory_statement_print.html', {
        'statement': statement,
        'items': items,
        'totals': totals,
        'title': f'Inventory Statement: {statement.date}'
    })