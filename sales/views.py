from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.db import transaction
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from products.models import Product
from sales.forms import SaleForm, SaleItemFormSet
from sales.models import Sale, SaleItem
from statement.models import ProductStockUpdate

# Sale Views
def sale_create(request):
    """Create a new sale with multiple sale items - optimized version with custom bulk minimum support."""
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
                        sale_type = form.cleaned_data.get('sale_type', 'regular')
                        custom_bulk_minimum = form.cleaned_data.get('custom_bulk_minimum')
                        
                        if not product or not quantity:
                            continue
                            
                        # Track the total quantity needed for each product
                        if product.id in product_quantities:
                            product_quantities[product.id] += quantity
                        else:
                            product_quantities[product.id] = quantity
                        
                        # Store complete item data for later creation
                        sale_items_data.append({
                            'product': product,
                            'quantity': quantity,
                            'sale_type': sale_type,
                            'custom_bulk_minimum': custom_bulk_minimum
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
                            custom_bulk_minimum = item_data.get('custom_bulk_minimum')
                            
                            # Set the price based on the sale type
                            if sale_type == 'bulk':
                                price_per_unit = product.bulk_price
                                
                                # Additional validation for bulk purchases with the custom minimum
                                effective_min_bulk_qty = product.minimum_bulk_quantity
                                if custom_bulk_minimum is not None and custom_bulk_minimum > 0:
                                    if custom_bulk_minimum < product.minimum_bulk_quantity:
                                        raise ValidationError(
                                            f"Custom bulk minimum ({custom_bulk_minimum}) for {product.name} cannot be less than the product's default minimum ({product.minimum_bulk_quantity})."
                                        )
                                    effective_min_bulk_qty = custom_bulk_minimum
                                
                                if quantity < effective_min_bulk_qty:
                                    raise ValidationError(
                                        f"Minimum {effective_min_bulk_qty} items required for bulk purchase of {product.name}."
                                    )
                                    
                            elif sale_type == 'dozen':
                                price_per_unit = product.dozen_price
                            else:
                                price_per_unit = product.regular_price
                            
                            # Create the sale item object (don't save yet)
                            sale_item = SaleItem(
                                sale=sale,
                                product=product,
                                quantity=quantity,
                                sale_type=sale_type,
                                price_per_unit=price_per_unit
                            )
                            
                            # If you want to store the custom bulk minimum in the database
                            # Assuming you've added a custom_bulk_minimum field to the SaleItem model
                            if custom_bulk_minimum is not None and custom_bulk_minimum > 0 and sale_type == 'bulk':
                                sale_item.custom_bulk_minimum = custom_bulk_minimum
                                
                            sale_items.append(sale_item)
                            
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
    
    return render(request, 'sales/sale_form.html', context)

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

    return render(request, 'sales/sale_list.html', {
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

    return render(request, 'sales/sale_detail.html', {'sale': sale})


def generate_receipt(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related('user').prefetch_related('items__product'),
        id=sale_id
    )

    html = render_to_string('sales/receipt.html', {'sale': sale, 'company_name': 'Modetex'})

    # Convert to PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{sale.id}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("Error generating receipt", status=500)

    return response
