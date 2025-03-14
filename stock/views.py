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
from .models import Category, Product, Sale, SaleItem, InventoryStatement
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
        writer.writerow(['Name', 'Regular Price', 'Bulk Price', 'Quantity', 'Stock Level'])
        
        # Write data rows
        for product in queryset:
            # Determine stock level status text
            stock_status = "Low Stock" if product.quantity <= product.restock_level else "In Stock"
            
            writer.writerow([
                product.name,
                product.regular_price,
                product.bulk_price,
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
    """Create a new sale with multiple sale items."""
    # Get all products with stock for JavaScript and the form
    products = Product.objects.filter(quantity__gt=0)
    
    if request.method == 'POST':
        sale_form = SaleForm(request.POST)
        sale_item_formset = SaleItemFormSet(request.POST)
        
        if sale_form.is_valid() and sale_item_formset.is_valid():
            try:
                with transaction.atomic():
                    # Create the sale
                    sale = sale_form.save(commit=False)
                    
                    # Set the user if authenticated
                    if request.user.is_authenticated:
                        sale.user = request.user
                    
                    # Save the sale to generate a primary key
                    sale.save()
                    
                    # Process each item in the formset
                    for form in sale_item_formset:
                        # Skip empty forms
                        if not form.has_changed() or not form.cleaned_data:
                            continue
                            
                        # Skip deleted forms
                        if form.cleaned_data.get('DELETE', False):
                            continue
                        
                        # Get the product and quantity
                        product = form.cleaned_data.get('product')
                        quantity = form.cleaned_data.get('quantity', 0)
                        
                        # Skip if no product or quantity
                        if not product or not quantity:
                            continue
                            
                        # Lock the product row to prevent race conditions
                        product = Product.objects.select_for_update().get(pk=product.pk)
                        
                        # Verify stock availability
                        if product.quantity < quantity:
                            raise ValidationError(
                                f"Not enough stock for {product.name}. Available: {product.quantity}"
                            )
                        
                        # Create the SaleItem but don't save it yet
                        sale_item = form.save(commit=False)
                        sale_item.sale = sale
                        
                        # Set the price based on the sale type
                        sale_type = form.cleaned_data.get('sale_type', 'regular')
                        sale_item.price_per_unit = (
                            product.bulk_price if sale_type == 'bulk' else product.regular_price
                        )
                        
                        # Save the SaleItem, which will trigger the stock update
                        sale_item.save()
                    
                    # Update the sale's total amount
                    sale.update_total_amount()
                    
                    messages.success(request, 'Sale recorded successfully!')
                    return redirect('sale_detail', sale_id=sale.id)
                    
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                # Handle unexpected errors gracefully
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            # Form validation errors
            errors = []
            if not sale_form.is_valid():
                errors.append("Sale information has errors.")
            
            for i, form in enumerate(sale_item_formset):
                if not form.is_valid():
                    form_errors = form.errors.as_text()
                    errors.append(f"Item #{i+1}: {form_errors}")
            
            error_message = "Please correct the errors: " + " ".join(errors)
            messages.error(request, error_message)
    else:
        # GET request - create new forms
        sale_form = SaleForm()
        
        # Initialize an empty formset with one form
        sale_item_formset = SaleItemFormSet(queryset=SaleItem.objects.none())
    
    # Pass the product data to the template context
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

#Inventory Statement
def generate_inventory_statement():
    """
    Generate an inventory statement with product stock levels and sales summary.
    """
    # Fetch all products
    products = Product.objects.all()

    # Calculate the date 30 days ago
    last_30_days = now() - timedelta(days=30)

    # Fetch sales summary for the last 30 days
    sales_summary = (
        SaleItem.objects.filter(sale__sale_date__gte=last_30_days)
        .values('product__name')
        .annotate(total_sold=Sum('quantity'))
    )

    # Convert sales summary to a dictionary for easy lookup
    sales_dict = {item['product__name']: item['total_sold'] for item in sales_summary}

    # Prepare inventory data
    inventory_data = []

    for product in products:
        inventory_data.append({
            'name': product.name,
            'category': product.category.name,
            'stock_quantity': product.quantity,
            'total_sold_last_30_days': sales_dict.get(product.name, 0),  # Default to 0 if no sales
            'restock_needed': 'Yes' if product.needs_restock else 'No',
            'regular_price': str(product.regular_price),
            'bulk_price': str(product.bulk_price),
        })

    return inventory_data

def save_inventory_statement():
    """Save the generated inventory statement to the database."""
    inventory_data = generate_inventory_statement()

    # Use DjangoJSONEncoder to handle datetime serialization
    inventory_data_json = json.dumps(inventory_data, cls=DjangoJSONEncoder)

    # Save the inventory statement in a transaction
    with transaction.atomic():
        InventoryStatement.objects.create(report_data=inventory_data_json)

def inventory_statement(request):
    """Fetch and display the latest inventory statement or export it as CSV."""
    # Get the latest inventory statement
    latest_statement = InventoryStatement.objects.order_by('-generated_at').first()

    # Load the report data if the statement exists
    if latest_statement:
        try:
            inventory_data = json.loads(latest_statement.report_data)
        except json.JSONDecodeError:
            inventory_data = []
    else:
        inventory_data = []

    # Check if the request is for CSV export
    if 'export' in request.GET:
        # Create the HttpResponse object with CSV headers
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory_statement.csv"'

        # Create a CSV writer
        writer = csv.writer(response)

        # Write the header row
        writer.writerow([
            'Product Name', 'Category', 'Stock Quantity', 'Total Sold (Last 30 Days)',
            'Restock Needed', 'Regular Price', 'Bulk Price'
        ])

        # Write the data rows
        for item in inventory_data:
            writer.writerow([
                item['name'],
                item['category'],
                item['stock_quantity'],
                item['total_sold_last_30_days'],
                item['restock_needed'],
                item['regular_price'],
                item['bulk_price'],
            ])

        return response

    # Render the template if not exporting
    return render(request, 'inventory_statement.html', {'inventory_data': inventory_data})


# Inventory Statement View
def inventory_statement_list(request):
    """View to list all inventory statements"""
    statements = InventoryStatement.objects.all()
    return render(request, 'inventory_statement_list.html', {
        'statements': statements,
        'title': 'Inventory Statements'
    })

# @login_required
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

# @login_required
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

# @login_required
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

# @login_required
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

# @login_required
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