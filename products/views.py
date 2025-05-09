import csv
from datetime import date
from django.contrib import messages
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from products.forms import ProductCreateForm, SearchProductCategory
from products.models import Category, Product
from sales.models import Sale, SaleItem
from statement.models import InventoryStatement




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
    return render(request, 'products/categories.html', context)


def product_list_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    # Use select_related to reduce database hits
    products = Product.objects.filter(category=category).select_related('category')
    
    context = {
        'title': f'Products in {category.name}',
        'category': category,
        'products': products,
    }
    return render(request, 'products/product_list_by_category.html', context)


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

    return render(request, 'products/product_form.html', {'title': 'Add Product', 'form': form})


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
        return render(request, 'products/product_list.html', context)


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
    return render(request, 'products/product_detail.html', context)


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
    
    return render(request, 'products/product_form.html', {
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
    
    return render(request, 'products/product_confirm_delete.html', {
        'product': product
    })