from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Category, Product, RegularSale, BulkSale, InventoryStatement
from .forms import (
    CategoryForm, ProductCreateForm, SearchProductCategory, 
    RegularSaleForm, BulkSaleForm
)
import csv
from datetime import date

# Home View
def home(request):
    today = date.today()
    context = {
        'title': 'Welcome to the Inventory Management System',
        'total_products': Product.objects.count(),
        'low_stock_count': Product.objects.filter(needs_restock=True).count(),
        'today_sales': RegularSale.objects.filter(sale_date__date=today).count() + 
                      BulkSale.objects.filter(sale_date__date=today).count(),
        'statement': InventoryStatement.objects.filter(date=today).first()
    }
    return render(request, 'home.html', context)

# Category Views
# @login_required
def category_list(request):
    categories_list = Category.objects.all()
    paginator = Paginator(categories_list, 10)  # Show 10 categories per page

    page = request.GET.get('page')
    try:
        categories = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver the first page
        categories = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver the last page
        categories = paginator.page(paginator.num_pages)

    context = {
        'title': 'Product Categories',
        'categories': categories,
    }
    return render(request, 'categories.html', context)

def product_list_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category)
    
    context = {
        'title': f'Products in {category.name}',
        'category': category,
        'products': products,
    }
    return render(request, 'product_list_by_category.html', context)

# @login_required
def product_create(request):
    form = ProductCreateForm(request.POST or None, request=request)
    
    if form.is_valid():
        product = form.save(commit=False)  # Don't save yet
        category = form.cleaned_data['category']
        print(f"Category: {category}")  # Debug statement
        product.category = category
        product.save()
        print(f"Product saved with category: {product.category}")  # Debug statement

        # Check for duplicate products
        duplicate_count = Product.objects.filter(name=product.name, category=product.category).count()
        print(f"Duplicate count: {duplicate_count}")  # Debug statement
        if duplicate_count > 1:
            messages.success(request, f'Product "{product.name}" already exists. Quantity updated!')
        else:
            messages.success(request, f'Product "{product.name}" added successfully!')
        
        return redirect('product_list')
    
    return render(request, 'product_form.html', {
        'title': 'Add Product',
        'form': form
    })

# @login_required
def product_list(request):
    queryset = Product.objects.all()
    form = SearchProductCategory(request.GET or None)
    restock_needed = queryset.filter(needs_restock=True)

    if form.is_valid():
        category = form.cleaned_data.get('category')
        search_term = form.cleaned_data.get('search_term')
        available_only = form.cleaned_data.get('available_only')
        needs_restock = form.cleaned_data.get('needs_restock')
        
        if category:
            queryset = queryset.filter(category=category)
        
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term) |
                Q(category__name__icontains=search_term)
            )
        
        if available_only:
            queryset = queryset.filter(available=True)
            
        if needs_restock:
            queryset = queryset.filter(needs_restock=True)
    
    context = {
        'title': 'Products Inventory',
        'form': form,
        'products': queryset,
        'restock_needed': restock_needed,
    }
    return render(request, 'product_list.html', context)


# @login_required
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    regular_sales = RegularSale.objects.filter(product=product)
    bulk_sales = BulkSale.objects.filter(product=product)
    
    context = {
        'title': f'Product: {product.name}',
        'product': product,
        'regular_sales': regular_sales,
        'bulk_sales': bulk_sales
    }
    return render(request, 'product_detail.html', context)

# @login_required
def product_edit(request, slug):
    product = get_object_or_404(Product, slug=slug)
    form = ProductCreateForm(request.POST or None, instance=product, request=request)
    
    if form.is_valid():
        form.save()
        messages.success(request, f'Product "{product.name}" updated successfully!')
        return redirect('product_list')
    
    return render(request, 'product_form.html', {
        'title': f'Edit Product: {product.name}',
        'form': form
    })

# @login_required
def product_delete(request, slug):
    product = get_object_or_404(Product, slug=slug)
    category = product.category  # Get the category before deleting the product

    if request.method == 'POST':
        product_name = product.name  # Store the product name for the success message
        product.delete()  # Delete the product
        messages.success(request, f'Product "{product_name}" deleted successfully!')

        # Check if the category is empty after deletion
        if category.products.count() == 0:
            category_name = category.name  # Store the category name for the info message
            category.delete()  # Delete the category if it has no products
            messages.info(request, f'Category "{category_name}" was also deleted because it has no products.')

        return redirect('product_list')
    
    return render(request, 'product_confirm_delete.html', {
        'product': product
    })

# Sale Views
# @login_required
def regular_sale_create(request):
    if request.method == 'POST':
        form = RegularSaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.seller = request.user

            # Get the product and quantity sold
            product = sale.product
            quantity_sold = sale.quantity

            # Check if there's enough stock
            if product.quantity >= quantity_sold:
                # Reduce the product quantity
                product.quantity -= quantity_sold
                product.save()

                # Save the sale
                sale.save()
                messages.success(request, 'Regular sale recorded successfully!')
                return redirect('regular_sale_list')
            else:
                messages.error(request, 'Not enough stock to complete the sale.')
        else:
            messages.error(request, 'Invalid form submission. Please check the data.')
    else:
        form = RegularSaleForm()
    products = Product.objects.filter(quantity__gt=0)

    return render(request, 'sale_form.html', {
        'title': 'Create Regular Sale',
        'form': form,
         'products': products,
    })

# @login_required
def bulk_sale_create(request):
    if request.method == 'POST':
        form = BulkSaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.seller = request.user

            # Get the product and quantity sold
            product = sale.product
            quantity_sold = sale.quantity

            # Check if there's enough stock
            if product.quantity >= quantity_sold:
                # Reduce the product quantity
                product.quantity -= quantity_sold
                product.save()

                # Save the sale
                sale.save()
                messages.success(request, 'Bulk sale recorded successfully!')
                return redirect('bulk_sale_list')
            else:
                messages.error(request, 'Not enough stock to complete the sale.')
        else:
            messages.error(request, 'Invalid form submission. Please check the data.')
    else:
        form = BulkSaleForm()
    products = Product.objects.filter(quantity__gt=0)

    return render(request, 'sale_form.html', {
        'title': 'Create Bulk Sale',
        'form': form,
        'products': products,
    })

# @login_required
# Regular Sale List
def regular_sale_list(request):
    sales = RegularSale.objects.all().order_by('-sale_date')
    return render(request, 'sale_list.html', {
        'title': 'Regular Sales',
        'sales': sales,
        'sale_type': 'regular'
    })

# @login_required
# Bulk Sale List
def bulk_sale_list(request):
    sales = BulkSale.objects.all().order_by('-sale_date')
    return render(request, 'sale_list.html', {
        'title': 'Bulk Sales',
        'sales': sales,
        'sale_type': 'bulk'
    })

# Inventory Statement Views
# @login_required
def statement_list(request):
    statements = InventoryStatement.objects.all().order_by('-date')
    return render(request, 'statement_list.html', {
        'title': 'Modetex Ventures Nigeria Inventory Statements',
        'statements': statements
    })

# @login_required
def statement_detail(request, pk):
    statement = get_object_or_404(InventoryStatement, pk=pk)
    return render(request, 'statement_detail.html', {
        'title': f'Statement: {statement.date}',
        'statement': statement
    })

# Export Views
# @login_required
def export_regular_sales(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="regular_sales.csv"'

    writer = csv.writer(response)
    writer.writerow(['Product', 'Category', 'Quantity', 'Price Per Unit', 
                    'Total Amount', 'Sale Date', 'Seller'])

    sales = RegularSale.objects.all().select_related('product', 'product__category', 'seller')
    for sale in sales:
        writer.writerow([
            sale.product.name,
            sale.product.category.name,
            sale.quantity,
            sale.price_per_unit,
            sale.total_amount,
            sale.sale_date,
            sale.seller.username if sale.seller else 'N/A'
        ])

    return response

# @login_required
def export_bulk_sales(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="bulk_sales.csv"'

    writer = csv.writer(response)
    writer.writerow(['Product', 'Category', 'Quantity', 'Bulk Price Per Unit', 
                    'Total Amount', 'Sale Date', 'Seller'])

    sales = BulkSale.objects.all().select_related('product', 'product__category', 'seller')
    for sale in sales:
        writer.writerow([
            sale.product.name,
            sale.product.category.name,
            sale.quantity,
            sale.bulk_price_per_unit,
            sale.total_amount,
            sale.sale_date,
            sale.seller.username if sale.seller else 'N/A'
        ])

    return response

# @login_required
def export_inventory_statements(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_statements.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Total Income', 'Total Products Sold', 
                    'Total Products In Stock'])

    statements = InventoryStatement.objects.all()
    for statement in statements:
        writer.writerow([
            statement.date,
            statement.total_income,
            statement.total_products_sold,
            statement.total_products_in_stock
        ])

    return response