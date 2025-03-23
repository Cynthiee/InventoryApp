import json
from arrow import now
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, F
from django.http import HttpResponse
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from xhtml2pdf import pisa
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Category, Product, ProductStockUpdate, Sale, SaleItem, InventoryStatement
from .forms import (
    CategoryForm, InventoryStatementForm, InventoryStatementItemFormSet, ProductCreateForm, SaleItemFormSet, SearchProductCategory, 
    SaleForm, SaleItemForm
)
import csv
from datetime import date, timedelta
import base64

# Home View
def home(request):
    today = date.today()

    # Get counts and totals
    low_stock_count = Product.objects.filter(needs_restock=True).count()
    total_products = Product.objects.count()
    today_sales_count = Sale.objects.filter(sale_date__date=today).count()
    total_stock = Product.objects.aggregate(total=Sum('quantity'))['total'] or 0

    # Calculate today's sales data
    today_sales = Sale.objects.filter(sale_date__date=today)
    total_income = today_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    total_products_sold = SaleItem.objects.filter(sale__sale_date__date=today).aggregate(total=Sum('quantity'))['total'] or 0

    # Ensure only one statement per day
    statement, created = InventoryStatement.objects.get_or_create(
        date=today,  # Changed from generated_at to date
        defaults={
            'company_name': 'Your Company',  # Add appropriate default values
            'prepared_by': 'System',
            'notes': 'Automatically generated daily statement'
        }
    )
    
    # Call your existing method to generate statement items
    if created:
        statement.generate_statement_items()

    context = {
        'title': 'Welcome to the Inventory Management System',
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'today_sales': today_sales_count,
        'statement': statement
    }

    return render(request, 'home.html', context)


# Category Views
def category_list(request):
    categories_list = Category.objects.all()
    
    # Define page size as a constant
    PAGE_SIZE = 10
    
    paginator = Paginator(categories_list, PAGE_SIZE)
    page = request.GET.get('page')
    
    try:
        categories = paginator.page(page)
    except PageNotAnInteger:
        categories = paginator.page(1)
    except EmptyPage:
        categories = paginator.page(paginator.num_pages)

    context = {
        'title': 'Product Categories',
        'categories': categories,
    }
    return render(request, 'categories.html', context)


def product_list_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    # Use select_related to reduce database hits
    products = Product.objects.filter(category=category).select_related('category')
    
    context = {
        'title': f'Products in {category.name}',
        'category': category,
        'products': products,
    }
    return render(request, 'product_list_by_category.html', context)


def product_create(request):
    form = ProductCreateForm(request.POST or None)
    
    if form.is_valid():
        try:
            with transaction.atomic():
                product = form.save()
                messages.success(request, f'Product "{product.name}" {"updated" if getattr(product, "_updated", False) else "added"} successfully!')
                return redirect('product_list')
        except Exception as e:
            # Don't attempt any new queries here
            messages.error(request, f"Unable to save product: {str(e)}")
            # Create a new form instance rather than reusing the current one
            form = ProductCreateForm(request.POST)

    return render(request, 'product_form.html', {'title': 'Add Product', 'form': form})


def product_list(request):
    # Start with base queryset and apply filters as needed
    queryset = Product.objects.all().select_related('category')
    form = SearchProductCategory(request.GET or None)
    restock_needed = Product.objects.filter(needs_restock=True).count()
    
    if form.is_valid():
        category = form.cleaned_data.get('category')
        search_term = form.cleaned_data.get('search_term')
        available_only = form.cleaned_data.get('available_only')
        needs_restock = form.cleaned_data.get('needs_restock')
        
        # Build filters incrementally
        filters = Q()
        
        if category:
            filters &= Q(category=category)
        
        if search_term:
            search_filters = Q(name__icontains=search_term) | Q(category__name__icontains=search_term)
            filters &= search_filters
        
        if available_only:
            filters &= Q(available=True)
            
        if needs_restock:
            filters &= Q(needs_restock=True)
            
        # Apply all filters at once
        if filters:
            queryset = queryset.filter(filters)
    
    # Check if the request is for CSV export
    is_csv_export = request.GET.get('export') == 'csv'
    
    if is_csv_export:
        # Create a CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products.csv"'
        
        # Create CSV writer
        writer = csv.writer(response)
        
        # Write header row - matching the fields in your template
        writer.writerow(['Name', 'Regular Price', 'Bulk Price', 'Dozen Price', 'Quantity', 'Stock Level'])
        
        # Write data rows
        for product in queryset:
            # Determine stock level status text
            stock_status = "Low Stock" if product.quantity <= product.restock_level else "In Stock"
            
            writer.writerow([
                product.name,
                product.regular_price,
                product.bulk_price,
                product.dozen_price,
                product.quantity,
                stock_status
            ])
        
        return response
    else:
        # Standard HTML response
        context = {
            'title': 'Products Inventory',
            'form': form,
            'products': queryset,
            'restock_needed': restock_needed,
        }
        return render(request, 'product_list.html', context)


def product_detail(request, slug):
    # Use select_related to reduce queries
    product = get_object_or_404(Product.objects.select_related('category'), slug=slug)
    # Use select_related to get related sales data efficiently
    sales = SaleItem.objects.filter(product=product).select_related('sale')
    
    context = {
        'title': f'Product: {product.name}',
        'product': product,
        'sales': sales,
    }
    return render(request, 'product_detail.html', context)


def product_edit(request, slug):
    product = get_object_or_404(Product, slug=slug)
    
    if request.method == 'POST':
        form = ProductCreateForm(request.POST, instance=product)
        if form.is_valid():
            # Pass form_edit=True to the save method
            product = form.save(commit=False)
            product.save(form_edit=True)
            
            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('product_list')
    else:
        form = ProductCreateForm(instance=product)
    
    return render(request, 'product_form.html', {
        'title': f'Edit Product: {product.name}',
        'form': form
    })


def product_delete(request, slug):
    product = get_object_or_404(Product, slug=slug)
    category = product.category

    if request.method == 'POST':
        with transaction.atomic():
            product_name = product.name
            product.delete()
            messages.success(request, f'Product "{product_name}" deleted successfully!')

            # Check if category is now empty
            if not Product.objects.filter(category=category).exists():
                category_name = category.name
                category.delete()
                messages.info(request, f'Category "{category_name}" was also deleted because it has no products.')

        return redirect('product_list')
    
    return render(request, 'product_confirm_delete.html', {
        'product': product
    })


# Sale Views
def sale_create(request):
    """Create a new sale with multiple sale items - optimized version."""
    products = Product.objects.filter(quantity__gt=0)
    
    if request.method == 'POST':
        sale_form = SaleForm(request.POST)
        sale_item_formset = SaleItemFormSet(request.POST)
        
        if sale_form.is_valid() and sale_item_formset.is_valid():
            try:
                with transaction.atomic():
                    # Create the sale
                    sale = sale_form.save(commit=False)
                    sale.seller_name = sale_form.cleaned_data['seller_name']
                    
                    if request.user.is_authenticated:
                        sale.user = request.user
                    
                    sale.save()
                    
                    # Collect all product IDs and quantities in one pass
                    product_quantities = {}
                    sale_items_data = []
                    
                    for form in sale_item_formset:
                        if not form.has_changed() or not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                            continue
                        
                        product = form.cleaned_data.get('product')
                        quantity = form.cleaned_data.get('quantity', 0)
                        
                        if not product or not quantity:
                            continue
                            
                        # Track the total quantity needed for each product
                        if product.id in product_quantities:
                            product_quantities[product.id] += quantity
                        else:
                            product_quantities[product.id] = quantity
                        
                        # Store complete item data for later creation
                        sale_type = form.cleaned_data.get('sale_type', 'regular')
                        sale_items_data.append({
                            'product': product,
                            'quantity': quantity,
                            'sale_type': sale_type
                        })
                    
                    # Process products only if we have items
                    if product_quantities:
                        # Get all product IDs
                        product_ids = list(product_quantities.keys())
                        
                        # Fetch all products at once with lock for update
                        locked_products = {
                            p.id: p for p in Product.objects.select_for_update().filter(pk__in=product_ids)
                        }
                        
                        # Batch validate all stock in one pass
                        insufficient_stock = []
                        for product_id, needed_quantity in product_quantities.items():
                            product = locked_products.get(product_id)
                            if not product:
                                raise ValidationError(f"Product with ID {product_id} not found")
                                
                            if product.quantity < needed_quantity:
                                insufficient_stock.append(
                                    f"{product.name}: Available: {product.quantity}, Needed: {needed_quantity}"
                                )
                        
                        # If any product has insufficient stock, raise an error with all problematic products
                        if insufficient_stock:
                            raise ValidationError(
                                f"Not enough stock for the following products:\n" + "\n".join(insufficient_stock)
                            )
                        
                        # Prepare sale items for bulk creation
                        sale_items = []
                        for item_data in sale_items_data:
                            product = item_data['product']
                            product_instance = locked_products[product.id]
                            sale_type = item_data['sale_type']
                            quantity = item_data['quantity']
                            
                            # Set the price based on the sale type
                            if sale_type == 'bulk':
                                price_per_unit = product.bulk_price
                            elif sale_type == 'dozen':
                                price_per_unit = product.dozen_price
                            else:
                                price_per_unit = product.regular_price
                            
                            # Create the sale item object (don't save yet)
                            sale_items.append(SaleItem(
                                sale=sale,
                                product=product,
                                quantity=quantity,
                                sale_type=sale_type,
                                price_per_unit=price_per_unit
                            ))
                            
                            # Update product quantity directly
                            product_instance.quantity -= quantity
                            
                        # Bulk update all products at once
                        products_to_update = list(locked_products.values())
                        Product.objects.bulk_update(products_to_update, ['quantity'])
                        
                        # Create all sale items in a single database query
                        SaleItem.objects.bulk_create(sale_items)
                        
                        # Update sale total - use sum from python instead of another DB query
                        sale.total_amount = sum(item.quantity * item.price_per_unit for item in sale_items)
                        sale.save(update_fields=['total_amount'])
                        
                        # Create stock update records in bulk
                        stock_updates = []
                        for product_id, quantity_change in product_quantities.items():
                            product = locked_products[product_id]
                            stock_updates.append(ProductStockUpdate(
                                product=product,
                                quantity_change=-quantity_change,
                                notes=f"Sale ID: {sale.id} - Reduced stock by {quantity_change}"
                            ))
                        
                        if stock_updates:
                            ProductStockUpdate.objects.bulk_create(stock_updates)
                    
                    messages.success(request, 'Sale recorded successfully!')
                    return redirect('sale_detail', sale_id=sale.id)
                    
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                # Log the error
                import logging
                logging.error(f"Error creating sale: {str(e)}", exc_info=True)
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            # Form validation errors
            if sale_form.errors:
                messages.error(request, "Please correct errors in the sale information.")
            if sale_item_formset.errors:
                messages.error(request, "Please correct errors in the sale items.")
    else:
        sale_form = SaleForm()
        sale_item_formset = SaleItemFormSet(queryset=SaleItem.objects.none())
    
    context = {
        'title': 'Create Sale',
        'sale_form': sale_form,
        'sale_item_formset': sale_item_formset,
        'products': products,
    }
    
    return render(request, 'sale_form.html', context)


def sale_list(request):
    query = request.GET.get('q', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    # Fetch sales with related items in a single query
    sales = Sale.objects.prefetch_related('items__product').select_related('user').order_by('-sale_date')

    # Filtering logic
    filters = Q()
    if query:
        filters |= Q(user__username__icontains=query) | Q(id__icontains=query)
    if start_date and end_date:
        filters &= Q(sale_date__date__range=[start_date, end_date])
    if filters:
        sales = sales.filter(filters)

    # Pagination
    PAGE_SIZE = 10
    paginator = Paginator(sales, PAGE_SIZE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'sale_list.html', {
        'title': 'Sales',
        'sales': page_obj,
        'query': query,
        'start_date': start_date,
        'end_date': end_date,
    })


def sale_detail(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related('user').prefetch_related('items__product'),
        id=sale_id
    )

    return render(request, 'sale_detail.html', {'sale': sale})


def generate_receipt(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related('user').prefetch_related('items__product'),
        id=sale_id
    )

    # Render template with sale data
    html = render_to_string('receipt.html', {'sale': sale, 'company_name': 'Modetex'})

    # Convert to PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{sale.id}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("Error generating receipt", status=500)

    return response


# Inventory Statement Views
def inventory_statement_list(request):
    """View to list all inventory statements"""
    statements = InventoryStatement.objects.all()
    return render(request, 'inventory_statement_list.html', {
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
    
    return render(request, 'inventory_statement_form.html', {
        'form': form,
        'title': 'Create Inventory Statement'
    })


def inventory_statement_detail(request, statement_id):
    """View to display a detailed inventory statement."""
    statement = get_object_or_404(InventoryStatement, id=statement_id)
    
    # Check if items need to be generated
    if not statement.items.exists():
        statement.generate_statement_items()
    
    # Get all items first (used for the form)
    all_items = statement.items.all()
    
    # Get filter type from query parameters
    filter_type = request.GET.get('filter')
    
    # Create a filtered queryset for display
    if filter_type == 'sold':
        display_items = all_items.filter(invoiced_stock__gt=0)  # Products sold
    elif filter_type == 'no_sales':
        display_items = all_items.filter(invoiced_stock=0)  # Products with no sales
    elif filter_type == 'restock':
        display_items = all_items.filter(remarks='Restock needed')  # Products needing restock
    elif filter_type == 'low_stock':
        display_items = all_items.filter(closing_stock__lte=10)  # Products with low stock
    else:
        # If no valid filter is provided, show all items
        display_items = all_items
        filter_type = None  # Reset filter_type to None for template display
    
    # Handle form submission for updating received stock
    if request.method == 'POST':
        formset = InventoryStatementItemFormSet(request.POST, instance=statement)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Inventory statement updated successfully.')
            
            # Preserve filter parameter in redirect
            redirect_url = reverse('inventory_statement_detail', kwargs={'statement_id': statement.id})
            if filter_type:
                redirect_url += f'?filter={filter_type}'
            return redirect(redirect_url)
    else:
        formset = InventoryStatementItemFormSet(instance=statement)
    
    # Calculate totals for the filtered inventory items
    item_totals = display_items.aggregate(
        total_opening=Sum('opening_stock'),
        total_received=Sum('received_stock'),
        total_invoiced=Sum('invoiced_stock'),
        total_closing=Sum('closing_stock'),
        total_variance=Sum('variance')
    )
    
    # Add statement summary totals
    summary_totals = {
        'total_income': statement.total_income,
        'total_products_sold': statement.total_products_sold,
        'total_products_in_stock': statement.total_products_in_stock
    }
    
    # Create a list of form/item pairs for the template to iterate over
    form_item_pairs = []
    
    # Match formset forms with display items
    item_ids = [item.id for item in display_items]
    for form in formset:
        # Only include forms for items that should be displayed
        if form.instance.id in item_ids:
            form_item_pairs.append((form, form.instance))
    
    return render(request, 'inventory_statement_detail.html', {
        'statement': statement,
        'form_item_pairs': form_item_pairs,  # This is what the template should iterate over
        'formset': formset,  # Still need this for the management form
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
    
    return render(request, 'inventory_statement_print.html', {
        'statement': statement,
        'items': items,
        'totals': totals,
        'title': f'Inventory Statement: {statement.date}'
    })